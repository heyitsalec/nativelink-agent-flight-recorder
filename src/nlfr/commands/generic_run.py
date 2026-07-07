"""Generic (non-Bazel) command recording for nlfr run --mode generic."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nlfr.agent_receipt import (
    is_live_receipt,
    load_receipt,
    receipt_provenance_summary,
    receipt_sha256,
)
from nlfr.artifacts import ArtifactManifestEntry, write_artifact
from nlfr.change_evidence import (
    NOTE_BASELINE_MISMATCH_PREFIX as _NOTE_BASELINE_MISMATCH_PREFIX,
    NOTE_BASELINE_UNVERIFIABLE as _NOTE_BASELINE_UNVERIFIABLE,
    NOTE_MATCHES_BASELINE_PREFIX as _NOTE_MATCHES_HEAD_PREFIX,
    NOTE_NEVER_OBSERVED as _NOTE_NEVER_OBSERVED,
    NOTE_UNOBSERVABLE as _NOTE_UNOBSERVABLE,
    derive_change_details,
    note_baseline_mismatch as _note_baseline_mismatch,
    patch_applied_from,
)
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
    # A sidecar git_baseline is a public-interface ASSERTION: re-verify every one
    # against this workspace's git object store BEFORE it can wear the verified
    # git_baseline label. Forged/unverifiable baselines are refused here and fall
    # back to recorder-window semantics with an honest note (see R2).
    git_baselines, baseline_rejections = _verify_git_baselines(
        workspace, _git_baselines_from_sidecar(args.provenance_sidecar)
    )

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
    change_details = derive_change_details(
        change_paths,
        before_hashes,
        after_hashes,
        git_baselines=git_baselines,
        baseline_rejections=baseline_rejections,
    )
    _warn_unobservable_paths(change_details)
    _record_changes(
        conn,
        run_key=run_key,
        run_row_id=run_row_id,
        change_paths=change_paths,
        before_hashes=before_hashes,
        after_hashes=after_hashes,
        git_baselines=git_baselines,
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
                git_baselines=git_baselines,
                baseline_rejections=baseline_rejections,
                terminal_status=terminal_status,
                receipt_path=(
                    Path(args.agent_receipt).resolve() if args.agent_receipt else None
                ),
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
    parser.add_argument(
        "--agent-receipt",
        help=(
            "nlfr.agent_receipt.v1 JSON from nlfr agent-invoke; recorded as an immutable "
            "artifact and verifies the agent provenance leg (collectable_v1 when live)"
        ),
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


def _extract_git_baselines(
    sidecar: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Pull attestable git baselines out of a provenance sidecar.

    The sidecar's optional ``git_baseline`` block maps a change path to its
    PRE-EDIT state captured from the git object store. This is verifiable
    evidence — the committed bytes survive a working-tree edit, so a skeptic can
    recompute it with ``git show <commit>:<path> | sha256sum``. Only paths git
    could attest appear here; untracked or non-repo paths are absent and fall
    back to the recorder's own before/after observation window.
    """

    if not isinstance(sidecar, dict):
        return {}
    raw = sidecar.get("git_baseline")
    if not isinstance(raw, dict):
        return {}
    baselines: dict[str, dict[str, Any]] = {}
    for path, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        if not isinstance(source, dict) or source.get("kind") != "git_head":
            continue
        baselines[path] = {
            "baseline_sha256": entry.get("baseline_sha256"),
            "source": source,
        }
    return baselines


def _git_baselines_from_sidecar(
    sidecar_path: str | None,
) -> dict[str, dict[str, Any]]:
    """Read git baselines from a sidecar path without full validation.

    Full sidecar validation happens later in ``_record_agent_provenance``; this
    tolerant read only needs the (optional) ``git_baseline`` block so the change
    derivation and the stderr warnings can run at the recorded-hashes stage.
    """

    if not sidecar_path:
        return {}
    try:
        sidecar = json.loads(Path(sidecar_path).read_text())
    except (OSError, ValueError):
        return {}
    return _extract_git_baselines(sidecar)


def _baseline_evidence_ref(source: dict[str, Any]) -> str | None:
    """A commit-pinned, directly verifiable evidence ref for a git baseline.

    ``source.ref`` is symbolic (``git:HEAD:<path>``) because HEAD is what the
    adapter read at record time; HEAD moves, so the evidence ref pins the
    resolved commit as ``git:<commit>:<path>`` — verifiable with
    ``git show <commit>:<path> | sha256sum``.
    """

    ref = source.get("ref")
    commit = source.get("commit")
    if not isinstance(ref, str) or not commit:
        return None
    parts = ref.split(":", 2)
    if len(parts) == 3 and parts[0] == "git":
        return f"git:{commit}:{parts[2]}"
    return ref


def _baseline_relpath(source: Any) -> str | None:
    """The repo-relative path a git baseline is pinned to (from ``source.ref``).

    ``git show <commit>:<path>`` resolves ``<path>`` against the repo root, not
    the process cwd, so re-verification must use the repo-relative path the
    adapter recorded in ``source.ref`` (``git:<ref>:<repo_rel>``) — never the
    workspace-relative ``--change-path``, which can differ.
    """

    if not isinstance(source, dict):
        return None
    ref = source.get("ref")
    if not isinstance(ref, str):
        return None
    parts = ref.split(":", 2)
    if len(parts) == 3 and parts[0] == "git":
        return parts[2]
    return None


def _git_show_object(
    workspace: Path, commit: str, relpath: str
) -> tuple[str, bytes | None]:
    """Resolve ``git show <commit>:<relpath>`` in ``workspace``.

    Returns one of:

    - ``("present", bytes)`` — the object exists at that commit; bytes returned;
    - ``("missing", None)`` — the commit resolves but the path is absent there;
    - ``("unresolvable", None)`` — not a git repo, git binary absent, or the
      commit itself does not resolve.

    Uses subprocess git (stdlib only). A git-absent host is a non-fatal
    ``unresolvable`` — the sidecar generator already assumes git, so a missing
    git here is just an unverifiable baseline, not a crash.
    """

    def _run(*args: str, capture_bytes: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(workspace), *args],
            capture_output=True,
            text=not capture_bytes,
            check=False,
        )

    try:
        inside = _run("rev-parse", "--is-inside-work-tree")
    except (OSError, ValueError):
        return ("unresolvable", None)  # git binary absent / unusable
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return ("unresolvable", None)
    resolved = _run("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    if resolved.returncode != 0:
        return ("unresolvable", None)  # commit does not resolve in this workspace
    shown = _run("show", f"{commit}:{relpath}", capture_bytes=True)
    if shown.returncode != 0:
        return ("missing", None)  # path absent at that commit
    return ("present", shown.stdout)


def _verify_git_baselines(
    workspace: Path,
    git_baselines: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Re-verify every sidecar git_baseline against the workspace git objects.

    ``--provenance-sidecar`` is a PUBLIC interface, so a supplied ``git_baseline``
    is an ASSERTION until proven — a forged ``baseline_sha256`` must not wear the
    verified ``git_baseline`` label. For each path we recompute
    ``git show <commit>:<relpath>`` here and hash the bytes:

    - **match** — keep the baseline (``changed_basis`` stays ``git_baseline``);
    - **mismatch** (object present but the hash differs, or ``null`` claimed yet
      the object exists) — refuse it, note ``sidecar git_baseline did not match``;
    - **unverifiable** (not a git repo, git absent, or the commit/object is
      missing) — refuse it, note ``baseline unverifiable in this workspace``.

    A ``null`` baseline (absent-at-commit) verifies when git confirms the path is
    absent at that commit. Refused paths are dropped from the returned baselines
    and fall back to recorder-window semantics. The conflict is recorded honestly
    (per-path note + stderr warning); the run is never hard-failed.

    Returns ``(verified_baselines, rejection_notes)``.
    """

    verified: dict[str, dict[str, Any]] = {}
    rejections: dict[str, str] = {}
    for path, baseline in git_baselines.items():
        source = baseline.get("source")
        commit = source.get("commit") if isinstance(source, dict) else None
        relpath = _baseline_relpath(source)
        if not isinstance(commit, str) or not commit or relpath is None:
            rejections[path] = _NOTE_BASELINE_UNVERIFIABLE
            continue
        status, data = _git_show_object(workspace, commit, relpath)
        expected = baseline.get("baseline_sha256")
        if status == "present":
            actual = hashlib.sha256(data or b"").hexdigest()
            if expected is not None and actual == expected:
                verified[path] = baseline
            else:
                # Hash differs, or the sidecar claimed a null baseline yet the
                # object exists — either way the assertion is refuted.
                rejections[path] = _note_baseline_mismatch(commit)
        elif status == "missing":
            if expected is None:
                verified[path] = baseline  # git confirms absent-at-commit
            else:
                # Sidecar claims specific pre-edit bytes but git has no such
                # object at that commit — unverifiable in this workspace.
                rejections[path] = _NOTE_BASELINE_UNVERIFIABLE
        else:  # unresolvable
            rejections[path] = _NOTE_BASELINE_UNVERIFIABLE
    return verified, rejections


def _warn_unobservable_paths(change_details: dict[str, dict[str, Any]]) -> None:
    """Emit an honest stderr warning for each path the recorder could not attest."""

    for path, entry in change_details.items():
        note = entry.get("note")
        if not note:
            continue
        if note == _NOTE_NEVER_OBSERVED:
            print(
                f"warning: --change-path {path!r} was never observed on disk "
                "(before and after hashes both absent); recorded as changed=false",
                file=sys.stderr,
            )
        elif note == _NOTE_UNOBSERVABLE:
            print(
                f"warning: --change-path {path!r} was already at its final state "
                "when recording began and no git baseline is available, so the "
                "recorder cannot attest whether the agent changed it (recorded as "
                "changed=false). Record inside a git-tracked workspace so the "
                "pre-edit state is captured from HEAD, or perform the edit inside "
                "--command.",
                file=sys.stderr,
            )
        elif note.startswith(_NOTE_MATCHES_HEAD_PREFIX):
            print(
                f"warning: --change-path {path!r} matches its git baseline, so "
                "changed=false — but the recorder CANNOT tell a genuine no-op from "
                "a change that was already committed before recording began. Pass "
                "--baseline-ref <pre-edit-ref> (e.g. HEAD~1 or the pre-edit commit "
                "sha) to attest a committed change.",
                file=sys.stderr,
            )
        elif note.startswith(_NOTE_BASELINE_MISMATCH_PREFIX):
            print(
                f"warning: --change-path {path!r} supplied a git baseline whose "
                "recorded hash did not match the git object at the referenced "
                "commit; the baseline was forged or stale and has been IGNORED. "
                "The change was derived from the recorder's own before/after "
                "window instead.",
                file=sys.stderr,
            )
        elif note == _NOTE_BASELINE_UNVERIFIABLE:
            print(
                f"warning: --change-path {path!r} supplied a git baseline that "
                "could not be verified in this workspace (not a git repo, git "
                "absent, or the commit/object is missing); the baseline was "
                "IGNORED and the change was derived from the recorder's own "
                "before/after window instead.",
                file=sys.stderr,
            )


def _record_changes(
    conn: Any,
    *,
    run_key: str,
    run_row_id: str,
    change_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    run_id: str,
    git_baselines: dict[str, dict[str, Any]] | None = None,
) -> None:
    git_baselines = git_baselines or {}
    for path in change_paths:
        evidence_refs = [f"run:{run_id}", f"path:{path}"]
        baseline = git_baselines.get(path)
        if baseline is not None and isinstance(baseline.get("source"), dict):
            ref = _baseline_evidence_ref(baseline["source"])
            if ref:
                evidence_refs.append(ref)
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
            evidence_refs=evidence_refs,
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
    git_baselines: dict[str, dict[str, Any]] | None = None,
    baseline_rejections: dict[str, str] | None = None,
    receipt: dict[str, Any] | None = None,
    mode: str = "generic",
) -> dict[str, Any]:
    agent_side = sidecar["agent"]
    # Only RE-VERIFIED baselines reach here (forged/unverifiable ones were refused
    # in run_generic and moved into baseline_rejections). Never re-extract raw
    # sidecar baselines — that would re-trust the very assertion R2 guards against.
    git_baselines = git_baselines or {}
    baseline_rejections = baseline_rejections or {}
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
    # Verifiable pre-edit evidence: a skeptic can recompute each git baseline via
    # `git show <commit>:<path> | sha256sum` and match it against baseline_sha256.
    for baseline in git_baselines.values():
        source = baseline.get("source")
        if isinstance(source, dict):
            ref = _baseline_evidence_ref(source)
            if ref and ref not in evidence_refs:
                evidence_refs.append(ref)

    # Receipt-verified agent provenance: a live Claude CLI receipt upgrades the
    # agent leg to collectable_v1 with the SERVER-resolved model id. Without a
    # receipt the model label stays operator-asserted, exactly as before.
    model_label = agent_side["model"]
    provenance_class = "operator_asserted_v1"
    agent_source_kind = "collectable_v1"
    agent_confidence = "high"
    receipt_summary: dict[str, Any] | None = None
    if receipt is not None:
        receipt_summary = receipt_provenance_summary(receipt)
        evidence_refs.append("artifact:agent-receipt.json")
        evidence_refs.append(f"receipt:sha256:{receipt_summary['receipt_sha256']}")
        if receipt_summary.get("session_id"):
            evidence_refs.append(f"session:{receipt_summary['session_id']}")
        if is_live_receipt(receipt):
            provenance_class = "receipt_verified_v1"
            model_label = receipt_summary.get("model_resolved") or model_label
        else:
            provenance_class = "stub_receipt_v1"
            agent_source_kind = "simulated_v1"
            agent_confidence = "medium"

    # patch_applied is DERIVED, never asserted, and by OBSERVATION MODE: against
    # the RE-VERIFIED git baseline (pre-edit bytes) when the adapter captured one
    # — which makes the documented edit-first flow evidence-backed — else against
    # the recorder's own before/after window. Identical hashes with no baseline are
    # an honest, LOUD changed=false (unobservable), not a silent one; a baseline
    # equal to after is flagged as an ambiguous commit-before-record case.
    change_details = derive_change_details(
        change_paths,
        before_hashes,
        after_hashes,
        git_baselines=git_baselines,
        baseline_rejections=baseline_rejections,
    )
    patch_applied = patch_applied_from(change_details)

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
            "model": model_label,
            "model_label_operator": agent_side["model"],
            "prompt_sha256": prompt_sha,
            "provenance_class": provenance_class,
            "receipt": receipt_summary,
        },
        "change": {
            "change_class": sidecar.get("change_class", "bounded_agent_v1"),
            "affected_paths": change_paths,
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
            "paths": change_details,
            "patch_applied": patch_applied,
        },
        "workspace": str(workspace),
        "build": {
            "run_id": run_id,
            "run_key": run_key,
            "status": terminal_status,
            "artifact_root": str(artifact_root),
        },
        "run_group": run_group,
        "mode": mode,
        "source_kind": agent_source_kind,
        "confidence": agent_confidence,
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
    git_baselines: dict[str, dict[str, Any]] | None = None,
    baseline_rejections: dict[str, str] | None = None,
    receipt_path: Path | None = None,
    mode: str = "generic",
) -> list[ArtifactManifestEntry]:
    sidecar = _load_provenance_sidecar(sidecar_path)
    entries: list[ArtifactManifestEntry] = []
    receipt: dict[str, Any] | None = None
    if receipt_path is not None:
        receipt = load_receipt(receipt_path)
        receipt_entry = write_artifact(
            artifact_root,
            artifact_key="agent-receipt.json",
            data=json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            producer_command=["nlfr", "agent-invoke"],
            config_hash=None,
            redaction_state="redacted",
            source_kind=str(receipt.get("source_kind") or "collectable_v1"),
            confidence=str(receipt.get("confidence") or "high"),
            evidence_refs=[
                f"run:{run_id}",
                f"receipt:sha256:{receipt_sha256(receipt)}",
                *[str(ref) for ref in receipt.get("evidence_refs") or []],
            ],
        )
        entries.append(receipt_entry)
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
        git_baselines=git_baselines,
        baseline_rejections=baseline_rejections,
        receipt=receipt,
        mode=mode,
    )
    scenario_id = str(provenance["scenario_id"])
    entry = write_artifact(
        artifact_root,
        artifact_key="agent-provenance.json",
        data=json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "run", "--mode", mode],
        config_hash=None,
        redaction_state="safe",
        source_kind=str(provenance["source_kind"]),
        confidence=str(provenance["confidence"]),
        evidence_refs=provenance["evidence_refs"],
    )
    entries.append(entry)
    upsert_proof_block(
        conn,
        stable_key=f"{run_key}:proof:agent-provenance:{scenario_id}",
        run_id=run_row_id,
        block_key=f"agent-provenance:{scenario_id}",
        block_kind="agent_provenance",
        title=f"Agent Provenance: {provenance['agent']['name']}",
        summary=f"{scenario_id} change recorded with status {terminal_status}.",
        payload=provenance,
        source_kind=str(provenance["source_kind"]),
        confidence=str(provenance["confidence"]),
        evidence_refs=provenance["evidence_refs"],
        redaction_state="safe",
    )
    return entries
