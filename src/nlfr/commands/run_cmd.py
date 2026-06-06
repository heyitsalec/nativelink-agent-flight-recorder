"""Run a Bazel workload and record local evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from nlfr.artifacts import ArtifactManifestEntry, write_artifact
from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_artifact, upsert_invocation, upsert_run
from nlfr.ids import stable_id
from nlfr.runners import BazelRunner, NativeLinkRunner, ProcessResult


def run(args: argparse.Namespace) -> int:
    if args.mode not in ("cache-only", "local-exec"):
        print(f"unsupported run mode: {args.mode}", file=sys.stderr)
        return 2

    workspace = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    nativelink_config = args.nativelink_config or str(_default_nativelink_config(args.mode))
    run_key = _run_key(args.scenario, args.mode)
    run_id = stable_id("run", run_key)
    run_dir = output_dir / "runs" / run_id
    artifact_root = run_dir / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    run_row_id = upsert_run(
        conn,
        stable_key=run_key,
        run_group=args.run_group,
        scenario=args.scenario,
        mode=args.mode,
        status="running",
        started_at=_timestamp(),
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_id}"],
        redaction_state="safe",
    )

    nativelink = NativeLinkRunner(
        config_path=nativelink_config,
        artifact_dir=artifact_root,
        executable=args.nativelink_executable,
    )
    bazel = BazelRunner(
        workspace=workspace,
        artifact_dir=artifact_root,
        bazel_executable=args.bazel_executable,
        startup_args=args.bazel_startup_arg,
        remote_cache_url=args.remote_cache,
        remote_executor_url=args.remote_executor if args.mode == "local-exec" else None,
    )

    results: list[ProcessResult] = []
    if not args.skip_nativelink:
        results.append(
            nativelink.run_cache_server(
                cwd=workspace,
                timeout_seconds=args.nativelink_timeout,
                evidence_refs=[f"run:{run_id}", f"config:{Path(nativelink_config).name}"],
            )
        )
    results.append(
        bazel.run_tests(
            args.target,
            extra_args=args.bazel_arg,
            evidence_refs=[f"run:{run_id}", "bazel:bep-profile-execution-log"],
        )
    )

    manifest_entries = _record_process_artifacts(
        artifact_root,
        results,
        run_id=run_id,
        config_hash=None,
    )
    run_payload = {
        "run_id": run_id,
        "run_key": run_key,
        "scenario": args.scenario,
        "run_group": args.run_group,
        "mode": args.mode,
        "workspace": str(workspace),
        "nativelink_config": nativelink_config,
        "artifact_root": str(artifact_root),
        "bazel_args": list(args.bazel_arg),
        "results": [result.to_metadata() for result in results],
        "artifacts": [entry.to_manifest() for entry in manifest_entries],
    }
    summary_entry = write_artifact(
        artifact_root,
        artifact_key="run.json",
        data=json.dumps(run_payload, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "run", "--mode", args.mode],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_id}"],
    )
    manifest_entries.append(summary_entry)

    terminal_status = _terminal_status(results)
    with conn:
        conn.execute(
            """
            UPDATE runs
            SET status = ?,
                ended_at = ?,
                evidence_refs = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                terminal_status,
                _timestamp(),
                json.dumps([f"artifact:{summary_entry.artifact_key}"]),
                run_row_id,
            ),
        )
    for result in results:
        invocation_id = upsert_invocation(
            conn,
            stable_key=f"{run_key}:invocation:{_label_for_result(result)}",
            run_id=run_row_id,
            invocation_kind=_label_for_result(result),
            command=result.command,
            cwd=result.cwd,
            exit_code=result.exit_code,
            started_at=result.started_at,
            ended_at=result.ended_at,
            source_kind=result.source_kind,
            confidence=result.confidence,
            evidence_refs=result.evidence_refs,
            redaction_state=result.redaction_state,
        )
        for path in (result.stdout_path, result.stderr_path):
            if path.exists():
                artifact_key = path.relative_to(artifact_root).as_posix()
                upsert_artifact(
                    conn,
                    stable_key=f"{run_key}:artifact:{artifact_key}",
                    run_id=run_row_id,
                    artifact_key=artifact_key,
                    artifact_path=artifact_key,
                    manifest_path="artifact_manifest.json",
                    sha256=_sha_from_manifest(manifest_entries, artifact_key),
                    size_bytes=path.stat().st_size,
                    content_type="text/plain",
                    producer_command=result.command,
                    config_hash=None,
                    source_kind=result.source_kind,
                    confidence=result.confidence,
                    evidence_refs=[f"invocation:{invocation_id}"],
                    redaction_state=result.redaction_state,
                )
    upsert_artifact(
        conn,
        stable_key=f"{run_key}:artifact:{summary_entry.artifact_key}",
        run_id=run_row_id,
        artifact_key=summary_entry.artifact_key,
        artifact_path=summary_entry.path,
        manifest_path="artifact_manifest.json",
        sha256=summary_entry.sha256,
        size_bytes=summary_entry.size_bytes,
        content_type="application/json",
        producer_command=summary_entry.producer_command,
        config_hash=summary_entry.config_hash,
        source_kind=summary_entry.source_kind,
        confidence=summary_entry.confidence,
        evidence_refs=summary_entry.evidence_refs,
        redaction_state=summary_entry.redaction_state,
    )

    if args.json:
        print(json.dumps(run_payload | {"status": terminal_status}, indent=2, sort_keys=True))
    else:
        print(f"nlfr run {terminal_status}: {run_id}")
        print(f"artifacts: {artifact_root}")
        for result in results:
            detail = f" ({result.detail})" if result.detail else ""
            print(f"[{result.status}] {' '.join(result.command)}{detail}")

    return 0 if terminal_status == "completed" else 1


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "run",
        help="run a Bazel workload through a recorder mode",
        description="Run a Bazel workload through a recorder mode.",
    )
    parser.add_argument("--scenario", help="demo or workload scenario name")
    parser.add_argument(
        "--run-group",
        default="latest",
        help="group label used by projection exporters",
    )
    parser.add_argument(
        "--mode",
        choices=("cache-only", "local-exec"),
        default="cache-only",
        help="recorder execution mode",
    )
    parser.add_argument(
        "--workspace",
        default=str(_repo_root() / "demo" / "bazel-monorepo"),
        help="Bazel workspace directory",
    )
    parser.add_argument(
        "--output-dir",
        default="data/nlfr",
        help="directory for SQLite and run artifacts",
    )
    parser.add_argument(
        "--nativelink-config",
        help="NativeLink config path; defaults by mode",
    )
    parser.add_argument(
        "--nativelink-executable",
        default="nativelink",
        help="NativeLink executable name or path",
    )
    parser.add_argument(
        "--nativelink-timeout",
        type=float,
        default=2.0,
        help="seconds to let the cache server process run before recording a timeout",
    )
    parser.add_argument(
        "--bazel-executable",
        default="bazel",
        help="Bazel executable name or path",
    )
    parser.add_argument(
        "--bazel-startup-arg",
        action="append",
        default=[],
        help="Bazel startup argument emitted before the test command; repeatable",
    )
    parser.add_argument(
        "--bazel-arg",
        action="append",
        default=[],
        help=(
            "Bazel test argument emitted after NLFR artifact/cache/executor flags; "
            "repeatable. Use --bazel-arg=--config=lre for flags beginning with --."
        ),
    )
    parser.add_argument(
        "--remote-cache",
        default="grpc://127.0.0.1:50051",
        help="Bazel remote cache endpoint",
    )
    parser.add_argument(
        "--remote-executor",
        default="grpc://127.0.0.1:50051",
        help="Bazel remote execution endpoint for local-exec mode",
    )
    parser.add_argument(
        "--skip-nativelink",
        action="store_true",
        help="record only the Bazel side of a cache-only run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable run metadata",
    )
    parser.add_argument("target", nargs="?", default="//...", help="Bazel target pattern")
    parser.set_defaults(handler=run)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_nativelink_config(mode: str) -> Path:
    config_name = "local-execution.json5" if mode == "local-exec" else "cache-only.json"
    return _repo_root() / "demo" / "nativelink" / config_name


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_key(scenario: str | None, mode: str) -> str:
    scenario_key = scenario or "ad-hoc"
    return f"{scenario_key}:{mode}:{_timestamp()}"


def _terminal_status(results: list[ProcessResult]) -> str:
    if any(result.status == "environment_blocker" for result in results):
        return "environment_blocker"
    if any(result.status == "configuration_blocker" for result in results):
        return "configuration_blocker"
    if any(result.status == "timeout" for result in results):
        return "timeout"
    if any(result.exit_code not in (0, None) for result in results):
        return "failed"
    return "completed"


def _record_process_artifacts(
    artifact_root: Path,
    results: list[ProcessResult],
    *,
    run_id: str,
    config_hash: str | None,
) -> list[ArtifactManifestEntry]:
    entries: list[ArtifactManifestEntry] = []
    for result in results:
        for stream_path in (result.stdout_path, result.stderr_path):
            if not stream_path.exists():
                continue
            artifact_key = stream_path.relative_to(artifact_root).as_posix()
            entries.append(
                write_artifact(
                    artifact_root,
                    artifact_key=artifact_key,
                    data=stream_path.read_bytes(),
                    producer_command=result.command,
                    config_hash=config_hash,
                    redaction_state=result.redaction_state,
                    source_kind=result.source_kind,
                    confidence=result.confidence,
                    evidence_refs=_dedupe([f"run:{run_id}", *result.evidence_refs]),
                )
            )
    return entries


def _label_for_result(result: ProcessResult) -> str:
    executable = Path(result.command[0]).name if result.command else "process"
    if "nativelink" in executable or "native-link" in executable:
        return "nativelink"
    if "bazel" in executable:
        return "bazel"
    return executable or "process"


def _sha_from_manifest(entries: list[ArtifactManifestEntry], artifact_key: str) -> str:
    for entry in entries:
        if entry.artifact_key == artifact_key:
            return entry.sha256
    raise RuntimeError(f"missing artifact manifest entry for {artifact_key}")


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
