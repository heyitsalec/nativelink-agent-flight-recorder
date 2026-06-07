"""Generic (non-Bazel) command recording for nlfr run --mode generic."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nlfr.artifacts import ArtifactManifestEntry, write_artifact
from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_artifact,
    upsert_change,
    upsert_failure,
    upsert_invocation,
    upsert_proof_block,
    upsert_run,
)
from nlfr.ids import stable_id
from nlfr.runners import ProcessResult, ProcessRunner


def run_generic(args: argparse.Namespace) -> int:
    """Record arbitrary shell commands and optional agent provenance."""

    if not args.command:
        print("generic mode requires at least one --command", file=sys.stderr)
        return 2

    workspace = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    run_key = _run_key(args.scenario, "generic")
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
        mode="generic",
        status="running",
        started_at=_timestamp(),
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_id}"],
        redaction_state="safe",
    )

    change_paths = list(args.change_path or [])
    before_hashes = _file_hashes(workspace, change_paths)

    runner = ProcessRunner(artifact_dir=artifact_root)
    results: list[ProcessResult] = []
    parsed_commands = [_parse_command(item) for item in args.command]
    for index, command in enumerate(parsed_commands):
        label = _label_for_command(command, index)
        results.append(
            runner.run(
                command,
                cwd=workspace,
                label=label,
                timeout_seconds=args.timeout,
                evidence_refs=[f"run:{run_id}", f"command:{index}"],
            )
        )

    after_hashes = _file_hashes(workspace, change_paths)
    _record_changes(
        conn,
        run_key=run_key,
        run_row_id=run_row_id,
        change_paths=change_paths,
        before_hashes=before_hashes,
        after_hashes=after_hashes,
        run_id=run_id,
    )

    manifest_entries = _record_process_artifacts(
        artifact_root,
        results,
        run_id=run_id,
    )
    manifest_entries.extend(
        _record_named_artifacts(
            artifact_root,
            workspace,
            args.artifact or [],
            run_id=run_id,
            producer_command=["nlfr", "run", "--mode", "generic"],
        )
    )

    run_payload = {
        "run_id": run_id,
        "run_key": run_key,
        "scenario": args.scenario,
        "run_group": args.run_group,
        "mode": "generic",
        "workspace": str(workspace),
        "artifact_root": str(artifact_root),
        "commands": parsed_commands,
        "results": [result.to_metadata() for result in results],
        "artifacts": [entry.to_manifest() for entry in manifest_entries],
        "source_kind": "collectable_v1",
        "confidence": "high",
        "redaction_state": "safe",
    }
    summary_entry = write_artifact(
        artifact_root,
        artifact_key="run.json",
        data=json.dumps(run_payload, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "run", "--mode", "generic"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_id}"],
    )
    manifest_entries.append(summary_entry)

    terminal_status = _terminal_status(results)
    if args.provenance_sidecar:
        manifest_entries.extend(
            _record_agent_provenance(
                conn,
                sidecar_path=Path(args.provenance_sidecar).resolve(),
                artifact_root=artifact_root,
                run_key=run_key,
                run_row_id=run_row_id,
                run_id=run_id,
                scenario=args.scenario,
                run_group=args.run_group,
                workspace=workspace,
                change_paths=change_paths,
                before_hashes=before_hashes,
                after_hashes=after_hashes,
                terminal_status=terminal_status,
            )
        )
    _record_failures(conn, run_key, run_row_id, results, run_id)
    _persist_sqlite(
        conn,
        artifact_root=artifact_root,
        run_row_id=run_row_id,
        run_key=run_key,
        results=results,
        manifest_entries=manifest_entries,
        summary_entry=summary_entry,
        terminal_status=terminal_status,
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


def register_generic_args(parser: argparse.ArgumentParser) -> None:
    """Attach CLI flags used by ``nlfr run --mode generic``."""

    parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="shell command to record; repeatable; parsed with shlex",
    )
    parser.add_argument(
        "--change-path",
        action="append",
        default=[],
        help="relative path under workspace to record as a change (before/after hash)",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="extra artifact as PATH:LABEL relative to workspace; repeatable",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="optional per-command timeout in seconds",
    )
    parser.add_argument(
        "--provenance-sidecar",
        help="JSON sidecar with agent.model and agent.prompt_sha256 only (never raw prompt)",
    )


def _parse_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=True)
    if not parts:
        raise ValueError(f"empty command: {command!r}")
    return parts


def _run_key(scenario: str | None, mode: str) -> str:
    scenario_key = scenario or "ad-hoc"
    return f"{scenario_key}:{mode}:{_timestamp()}"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _file_hashes(workspace: Path, paths: list[str]) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for relative in paths:
        path = workspace / relative
        hashes[relative] = _sha256_file(path) if path.is_file() else None
    return hashes


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_changes(
    conn: Any,
    *,
    run_key: str,
    run_row_id: str,
    change_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    run_id: str,
) -> None:
    for path in change_paths:
        upsert_change(
            conn,
            stable_key=f"{run_key}:change:{path}",
            run_id=run_row_id,
            change_kind="generic_path",
            path=path,
            before_hash=before_hashes.get(path),
            after_hash=after_hashes.get(path),
            summary=f"generic run touched {path}",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"run:{run_id}", f"path:{path}"],
            redaction_state="safe",
        )


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


def _record_failures(
    conn: Any,
    run_key: str,
    run_row_id: str,
    results: list[ProcessResult],
    run_id: str,
) -> None:
    for index, result in enumerate(results):
        if result.exit_code in (0, None):
            continue
        message = result.detail or f"command exited with code {result.exit_code}"
        upsert_failure(
            conn,
            stable_key=f"{run_key}:failure:command:{index}",
            run_id=run_row_id,
            failure_kind="command_exit",
            message=message,
            span={"command": result.command, "exit_code": result.exit_code},
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"run:{run_id}", f"invocation:{index}"],
            redaction_state="safe",
        )


def _record_process_artifacts(
    artifact_root: Path,
    results: list[ProcessResult],
    *,
    run_id: str,
    config_hash: str | None = None,
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


def _record_named_artifacts(
    artifact_root: Path,
    workspace: Path,
    artifact_specs: list[str],
    *,
    run_id: str,
    producer_command: list[str],
) -> list[ArtifactManifestEntry]:
    entries: list[ArtifactManifestEntry] = []
    for spec in artifact_specs:
        if ":" not in spec:
            raise ValueError(f"artifact spec must be PATH:LABEL, got {spec!r}")
        relative_path, label = spec.rsplit(":", 1)
        source = (workspace / relative_path).resolve()
        if not source.is_file():
            continue
        artifact_key = f"outputs/{label}{source.suffix or ''}"
        entries.append(
            write_artifact(
                artifact_root,
                artifact_key=artifact_key,
                data=source.read_bytes(),
                producer_command=producer_command,
                config_hash=None,
                redaction_state="safe",
                source_kind="collectable_v1",
                confidence="high",
                evidence_refs=[f"run:{run_id}", f"artifact:{label}"],
            )
        )
    return entries


def _persist_sqlite(
    conn: Any,
    *,
    artifact_root: Path,
    run_row_id: str,
    run_key: str,
    results: list[ProcessResult],
    manifest_entries: list[ArtifactManifestEntry],
    summary_entry: ArtifactManifestEntry,
    terminal_status: str,
) -> None:
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
    seen_keys: set[str] = set()
    for index, result in enumerate(results):
        invocation_id = upsert_invocation(
            conn,
            stable_key=f"{run_key}:invocation:{_label_for_result(result, index)}",
            run_id=run_row_id,
            invocation_kind=_label_for_result(result, index),
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
            if not path.exists():
                continue
            rel_key = path.relative_to(artifact_root).as_posix()
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
                size_bytes=path.stat().st_size,
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


def _content_type_for(artifact_key: str) -> str:
    if artifact_key.endswith(".json"):
        return "application/json"
    if artifact_key.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


def _label_for_command(command: list[str], index: int) -> str:
    if not command:
        return f"command-{index}"
    executable = Path(command[0]).name
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in executable)
    return f"{safe}-{index}"


def _label_for_result(result: ProcessResult, index: int) -> str:
    if not result.command:
        return f"process-{index}"
    executable = Path(result.command[0]).name
    return executable or f"process-{index}"


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


def _load_provenance_sidecar(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        raise ValueError(f"provenance sidecar missing agent object: {path}")
    if agent.get("prompt"):
        raise ValueError(f"provenance sidecar must not contain raw prompt: {path}")
    if not agent.get("model"):
        raise ValueError(f"provenance sidecar missing agent.model: {path}")
    if not agent.get("prompt_sha256"):
        raise ValueError(f"provenance sidecar missing agent.prompt_sha256: {path}")
    return payload


def _agent_provenance_payload(
    *,
    sidecar: dict[str, Any],
    scenario: str | None,
    workspace: Path,
    change_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    run_key: str,
    run_id: str,
    run_group: str,
    terminal_status: str,
    artifact_root: Path,
) -> dict[str, Any]:
    agent_side = sidecar["agent"]
    scenario_id = scenario or "agent-change"
    agent_name = str(agent_side.get("name") or "cursor-agent-change")
    prompt_sha = str(agent_side["prompt_sha256"])
    evidence_refs = [
        f"scenario:{scenario_id}",
        f"agent:{agent_name}",
        f"run:{run_id}",
        f"prompt:sha256:{prompt_sha}",
    ]
    adapter = sidecar.get("adapter")
    if isinstance(adapter, str) and adapter:
        evidence_refs.append(f"adapter:{adapter}")

    return {
        "schema_version": "nlfr.agent_provenance.v1",
        "generated_at": _timestamp(),
        "scenario_id": scenario_id,
        "title": "Bounded agent change with hashed prompt provenance",
        "agent": {
            "kind": agent_side.get("kind", "cursor_adapter_v1"),
            "name": agent_name,
            "input_signal": agent_side.get(
                "input_signal",
                "redacted: prompt withheld, hash retained",
            ),
            "model": agent_side["model"],
            "prompt_sha256": prompt_sha,
        },
        "change": {
            "change_class": sidecar.get("change_class", "bounded_agent_v1"),
            "affected_paths": change_paths,
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
            "patch_applied": True,
        },
        "workspace": str(workspace),
        "build": {
            "run_id": run_id,
            "run_key": run_key,
            "status": terminal_status,
            "artifact_root": str(artifact_root),
        },
        "run_group": run_group,
        "mode": "generic",
        "source_kind": "collectable_v1",
        "confidence": "high",
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }


def _record_agent_provenance(
    conn: Any,
    *,
    sidecar_path: Path,
    artifact_root: Path,
    run_key: str,
    run_row_id: str,
    run_id: str,
    scenario: str | None,
    run_group: str,
    workspace: Path,
    change_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    terminal_status: str,
) -> list[ArtifactManifestEntry]:
    sidecar = _load_provenance_sidecar(sidecar_path)
    provenance = _agent_provenance_payload(
        sidecar=sidecar,
        scenario=scenario,
        workspace=workspace,
        change_paths=change_paths,
        before_hashes=before_hashes,
        after_hashes=after_hashes,
        run_key=run_key,
        run_id=run_id,
        run_group=run_group,
        terminal_status=terminal_status,
        artifact_root=artifact_root,
    )
    scenario_id = str(provenance["scenario_id"])
    entry = write_artifact(
        artifact_root,
        artifact_key="agent-provenance.json",
        data=json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "run", "--mode", "generic"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=provenance["evidence_refs"],
    )
    upsert_proof_block(
        conn,
        stable_key=f"{run_key}:proof:agent-provenance:{scenario_id}",
        run_id=run_row_id,
        block_key=f"agent-provenance:{scenario_id}",
        block_kind="agent_provenance",
        title=f"Agent Provenance: {provenance['agent']['name']}",
        summary=f"{scenario_id} change recorded with status {terminal_status}.",
        payload=provenance,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=provenance["evidence_refs"],
        redaction_state="safe",
    )
    return [entry]
