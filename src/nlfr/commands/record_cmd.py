"""One-command evidence capture for a user's own Bazel build.

``nlfr record`` wraps a user's own ``bazel``/``bazelisk`` invocation in any
Bazel repository. It injects Build Event Protocol (BEP) capture, runs the
command, hashes the captured artifacts into the immutable manifest, ingests the
BEP into SQLite, and exports the action-graph and proof-packet projections for
the run group. No NLFR configuration and no NativeLink deployment are required.

Design note: this command deliberately reuses the existing recorder machinery
as libraries (``ProcessRunner``, ``write_artifact``, the Bazel BEP parser, the
SQLite ingest, and the projection exporters) rather than shelling back out to
other ``nlfr`` subcommands. A non-zero Bazel exit is a *valid* recording — the
failure evidence is the product — so the status is recorded honestly and the
process exit code mirrors Bazel's own.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from nlfr.artifacts import ArtifactManifestEntry, write_artifact
from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_artifact,
    upsert_failure,
    upsert_invocation,
    upsert_run,
)
from nlfr.ids import stable_id
from nlfr.ingest.bazel import parse_bazel_bep
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.projectors import export_action_graph, export_proof_packet
from nlfr.projectors.common import write_or_print
from nlfr.runners import ProcessResult, ProcessRunner

_BAZEL_MARKERS = ("MODULE.bazel", "WORKSPACE.bazel", "WORKSPACE")
_BEP_FLAG = "--build_event_json_file"
_BEP_ARTIFACT_KEY = "bazel-bep.json"


def run(args: argparse.Namespace) -> int:
    """Wrap a user's Bazel command, record evidence, and export projections."""

    command = _resolve_command(args.command)
    if not command:
        print(
            "nlfr record requires a command to wrap, e.g.\n"
            "  nlfr record -- bazel test //foo:bar",
            file=sys.stderr,
        )
        return 2

    if not _is_bazel_command(command):
        print(
            f"nlfr record v1 wraps bazel/bazelisk commands only, got: {command[0]!r}\n"
            "For other commands record them with:\n"
            "  nlfr run --mode generic --command '<your command>'",
            file=sys.stderr,
        )
        return 2

    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd().resolve()
    marker = _bazel_marker(workspace)
    if marker is None:
        print(
            f"no Bazel workspace marker found in {workspace}\n"
            f"expected one of: {', '.join(_BAZEL_MARKERS)}\n"
            "Run nlfr record from your Bazel repo root, or pass --workspace PATH.",
            file=sys.stderr,
        )
        return 2

    run_group = args.run_group or _default_run_group()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else workspace / "data" / "nlfr-record" / run_group
    )
    run_key = _run_key(run_group)
    run_id = stable_id("run", run_key)
    artifact_root = output_dir / "runs" / run_id / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    # Decide where the BEP will land: honor a user-supplied flag, otherwise
    # inject our own immediately after the Bazel verb.
    verb_index = _verb_index(command)
    user_bep = _user_bep_path(command, workspace)
    if user_bep is not None:
        bep_source = user_bep
        final_command = list(command)
    else:
        bep_source = artifact_root / _BEP_ARTIFACT_KEY
        final_command = _inject_bep_flag(command, verb_index, bep_source)

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    run_row_id = upsert_run(
        conn,
        stable_key=run_key,
        run_group=run_group,
        scenario="record",
        mode="record",
        status="running",
        started_at=_timestamp(),
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_id}", f"workspace-marker:{marker}"],
        redaction_state="safe",
    )

    runner = ProcessRunner(artifact_dir=artifact_root)
    result = runner.run(
        final_command,
        cwd=workspace,
        label="bazel",
        evidence_refs=[f"run:{run_id}", "bazel:bep"],
    )

    manifest_entries = _record_stream_artifacts(artifact_root, result, run_id=run_id)

    # Hash the captured BEP into the immutable manifest (copying it into the
    # evidence dir when the user directed Bazel to write it elsewhere), then
    # parse + ingest it into the SQLite spine.
    bundle_counts: dict[str, int] = {}
    bep_entry: ArtifactManifestEntry | None = None
    bep_captured = bep_source.is_file()
    if bep_captured:
        bep_bytes = bep_source.read_bytes()
        bep_entry = write_artifact(
            artifact_root,
            artifact_key=_BEP_ARTIFACT_KEY,
            data=bep_bytes,
            producer_command=final_command,
            config_hash=None,
            redaction_state="safe",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"run:{run_id}", "bazel:bep"],
        )
        manifest_entries.append(bep_entry)
        evidence_ref = f"collectable_v1:{_BEP_ARTIFACT_KEY}"
        bundle = parse_bazel_bep(
            bep_source,
            source_kind="collectable_v1",
            evidence_ref=evidence_ref,
        )
        bundle_counts = ingest_evidence_bundle(
            conn,
            run_id=run_row_id,
            run_stable_key=run_key,
            bundle=bundle,
        )

    terminal_status = _terminal_status(result)
    run_payload = {
        "run_id": run_id,
        "run_key": run_key,
        "run_group": run_group,
        "mode": "record",
        "scenario": "record",
        "workspace": str(workspace),
        "artifact_root": str(artifact_root),
        "command": final_command,
        "user_command": command,
        "bazel_exit_code": result.exit_code,
        "bep_captured": bep_captured,
        "bep_path": str(bep_source),
        "status": terminal_status,
        "ingest_counts": bundle_counts,
        "results": [result.to_metadata()],
        "artifacts": [entry.to_manifest() for entry in manifest_entries],
        "source_kind": "collectable_v1",
        "confidence": "high",
        "redaction_state": "safe",
    }
    summary_entry = write_artifact(
        artifact_root,
        artifact_key="run.json",
        data=json.dumps(run_payload, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "record"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_id}"],
    )
    manifest_entries.append(summary_entry)

    _persist_run_rows(
        conn,
        artifact_root=artifact_root,
        run_row_id=run_row_id,
        run_key=run_key,
        result=result,
        manifest_entries=manifest_entries,
        summary_entry=summary_entry,
        terminal_status=terminal_status,
        run_id=run_id,
    )

    projections = _export_projections(
        conn,
        output_dir=output_dir,
        run_group=run_group,
    )

    _emit_summary(
        args,
        run_payload=run_payload,
        output_dir=output_dir,
        artifact_root=artifact_root,
        projections=projections,
        result=result,
    )

    if result.exit_code is None:
        return 1
    return int(result.exit_code)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``record`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "record",
        help="wrap your own bazel command and capture evidence in one step",
        description=(
            "Wrap a bazel/bazelisk command in any Bazel repo, capture BEP + "
            "stdout evidence immutably, ingest it, and export projections."
        ),
    )
    parser.add_argument(
        "--workspace",
        help="Bazel workspace directory (default: current directory)",
    )
    parser.add_argument(
        "--run-group",
        help="run group label for projections (default: record-<UTC date>)",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "directory for SQLite, artifacts, and projections "
            "(default: <workspace>/data/nlfr-record/<run-group>)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable summary instead of the human summary",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="the bazel command to wrap, e.g. -- bazel test //foo:bar",
    )
    parser.set_defaults(handler=run)


def _resolve_command(raw: list[str] | None) -> list[str]:
    """Return the user's command, dropping a single leading ``--`` separator."""

    command = list(raw or [])
    if command and command[0] == "--":
        command = command[1:]
    return command


def _is_bazel_command(command: list[str]) -> bool:
    """True when the command's executable basename names bazel or bazelisk."""

    return "bazel" in Path(command[0]).name.lower()


def _bazel_marker(workspace: Path) -> str | None:
    """Return the Bazel workspace marker filename present in ``workspace``."""

    for marker in _BAZEL_MARKERS:
        if (workspace / marker).exists():
            return marker
    return None


def _verb_index(command: list[str]) -> int:
    """Index of the Bazel verb: the first post-executable token not starting ``--``.

    Bazel invocations look like ``bazel [startup opts] VERB [opts] targets`` and
    every startup option begins with ``--``. The verb is the first token after
    the executable that is not a ``--`` startup option.
    """

    for index in range(1, len(command)):
        if not command[index].startswith("--"):
            return index
    return len(command) - 1


def _user_bep_path(command: list[str], workspace: Path) -> Path | None:
    """Return the user-supplied ``--build_event_json_file`` path, if any.

    Supports both ``--build_event_json_file=PATH`` and the space-separated
    ``--build_event_json_file PATH`` forms. Relative paths resolve against the
    workspace, where Bazel writes them.
    """

    for index, token in enumerate(command):
        value: str | None = None
        if token.startswith(f"{_BEP_FLAG}="):
            value = token.split("=", 1)[1]
        elif token == _BEP_FLAG and index + 1 < len(command):
            value = command[index + 1]
        if value:
            path = Path(value)
            return path if path.is_absolute() else (workspace / path)
    return None


def _inject_bep_flag(command: list[str], verb_index: int, bep_path: Path) -> list[str]:
    """Insert ``--build_event_json_file`` immediately after the Bazel verb."""

    flag = f"{_BEP_FLAG}={bep_path}"
    return [*command[: verb_index + 1], flag, *command[verb_index + 1 :]]


def _record_stream_artifacts(
    artifact_root: Path,
    result: ProcessResult,
    *,
    run_id: str,
) -> list[ArtifactManifestEntry]:
    entries: list[ArtifactManifestEntry] = []
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
                config_hash=None,
                redaction_state=result.redaction_state,
                source_kind=result.source_kind,
                confidence=result.confidence,
                evidence_refs=_dedupe([f"run:{run_id}", *result.evidence_refs]),
            )
        )
    return entries


def _persist_run_rows(
    conn: object,
    *,
    artifact_root: Path,
    run_row_id: str,
    run_key: str,
    result: ProcessResult,
    manifest_entries: list[ArtifactManifestEntry],
    summary_entry: ArtifactManifestEntry,
    terminal_status: str,
    run_id: str,
) -> None:
    with conn:  # type: ignore[union-attr]
        conn.execute(  # type: ignore[union-attr]
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

    invocation_id = upsert_invocation(
        conn,
        stable_key=f"{run_key}:invocation:bazel",
        run_id=run_row_id,
        invocation_kind="bazel",
        command=result.command,
        cwd=str(result.cwd),
        exit_code=result.exit_code,
        started_at=result.started_at,
        ended_at=result.ended_at,
        source_kind=result.source_kind,
        confidence=result.confidence,
        evidence_refs=result.evidence_refs,
        redaction_state=result.redaction_state,
    )

    if result.exit_code not in (0, None):
        message = result.detail or f"bazel exited with code {result.exit_code}"
        upsert_failure(
            conn,
            stable_key=f"{run_key}:failure:bazel-exit",
            run_id=run_row_id,
            failure_kind="command_exit",
            message=message,
            span={"command": result.command, "exit_code": result.exit_code},
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"run:{run_id}", f"invocation:{invocation_id}"],
            redaction_state="safe",
        )

    seen_keys: set[str] = set()
    for stream_path in (result.stdout_path, result.stderr_path):
        if not stream_path.exists():
            continue
        rel_key = stream_path.relative_to(artifact_root).as_posix()
        if rel_key in seen_keys:
            continue
        seen_keys.add(rel_key)
        upsert_artifact(
            conn,
            stable_key=f"{run_key}:artifact:{rel_key}",
            run_id=run_row_id,
            artifact_key=rel_key,
            artifact_path=rel_key,
            manifest_path="artifact_manifest.json",
            sha256=_sha_from_manifest(manifest_entries, rel_key),
            size_bytes=stream_path.stat().st_size,
            content_type="text/plain",
            producer_command=result.command,
            config_hash=None,
            source_kind=result.source_kind,
            confidence=result.confidence,
            evidence_refs=[f"invocation:{invocation_id}"],
            redaction_state=result.redaction_state,
        )

    for entry in manifest_entries:
        if entry.artifact_key in seen_keys:
            continue
        seen_keys.add(entry.artifact_key)
        upsert_artifact(
            conn,
            stable_key=f"{run_key}:artifact:{entry.artifact_key}",
            run_id=run_row_id,
            artifact_key=entry.artifact_key,
            artifact_path=entry.path,
            manifest_path="artifact_manifest.json",
            sha256=entry.sha256,
            size_bytes=entry.size_bytes,
            content_type=_content_type_for(entry.artifact_key),
            producer_command=entry.producer_command,
            config_hash=entry.config_hash,
            source_kind=entry.source_kind,
            confidence=entry.confidence,
            evidence_refs=entry.evidence_refs,
            redaction_state=entry.redaction_state,
        )


def _export_projections(
    conn: object,
    *,
    output_dir: Path,
    run_group: str,
) -> dict[str, Path]:
    projections_dir = output_dir / "projections"
    graph_path = projections_dir / f"graph-{run_group}.json"
    proof_path = projections_dir / f"proof-{run_group}.json"
    write_or_print(export_action_graph(conn, run_group=run_group), str(graph_path))
    write_or_print(export_proof_packet(conn, run_group=run_group), str(proof_path))
    return {"graph": graph_path, "proof": proof_path}


def _emit_summary(
    args: argparse.Namespace,
    *,
    run_payload: dict[str, object],
    output_dir: Path,
    artifact_root: Path,
    projections: dict[str, Path],
    result: ProcessResult,
) -> None:
    if args.json:
        payload = dict(run_payload)
        payload["output_dir"] = str(output_dir)
        payload["projections"] = {key: str(path) for key, path in projections.items()}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    status = run_payload["status"]
    exit_code = result.exit_code if result.exit_code is not None else "n/a"
    print(f"nlfr record: {status} (bazel exit code {exit_code})")
    print(f"run group:   {run_payload['run_group']}")
    print(f"evidence:    {artifact_root}")
    if not run_payload["bep_captured"]:
        print("bep:         not captured (bazel produced no build event file)")
    print(f"graph:       {projections['graph']}")
    print(f"proof:       {projections['proof']}")
    if result.detail:
        print(f"note:        {result.detail}")


def _terminal_status(result: ProcessResult) -> str:
    if result.status in ("environment_blocker", "configuration_blocker", "timeout"):
        return result.status
    if result.exit_code not in (0, None):
        return "failed"
    return "completed"


def _default_run_group() -> str:
    return f"record-{datetime.now(UTC).strftime('%Y-%m-%d')}"


def _run_key(run_group: str) -> str:
    return f"record:{run_group}:{_timestamp()}"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _content_type_for(artifact_key: str) -> str:
    if artifact_key.endswith(".json"):
        return "application/json"
    if artifact_key.endswith(".txt"):
        return "text/plain"
    return "application/octet-stream"


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
