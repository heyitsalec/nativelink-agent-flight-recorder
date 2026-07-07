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
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from nlfr.artifacts import ArtifactManifestEntry, write_artifact
from nlfr.config import BAZEL_MARKERS as _BAZEL_MARKERS
from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_artifact,
    upsert_failure,
    upsert_invocation,
    upsert_run,
)
from nlfr.ids import stable_id
from nlfr.ingest.bazel import (
    extract_bep_tool_version,
    out_of_range_bazel_warning,
    parse_bazel_bep,
)
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.projectors import export_action_graph, export_proof_packet
from nlfr.projectors.common import write_or_print
from nlfr.runners import ProcessResult, ProcessRunner

_BEP_FLAG = "--build_event_json_file"
_BEP_ARTIFACT_KEY = "bazel-bep.json"

# Known Bazel command verbs. The verb is matched against this fixed set rather
# than guessed as "the first non-``--`` token", because Bazel startup options
# accept *space-separated* values (e.g. ``--bazelrc /path``,
# ``--output_base /path``) whose value would otherwise be mistaken for the verb —
# corrupting the injected ``--build_event_json_file`` into the startup segment,
# which real Bazel rejects (exit 2) so the user's command never runs.
_BAZEL_VERBS = frozenset(
    {
        "build",
        "test",
        "run",
        "query",
        "cquery",
        "aquery",
        "coverage",
        "fetch",
        "sync",
        "vendor",
        "mod",
        "info",
        "clean",
        "shutdown",
        "version",
        "dump",
        "canonicalize-flags",
        "config",
        "license",
        "print_action",
        "mobile-install",
        "analyze-profile",
        "help",
    }
)

# Bazel startup options that consume a SEPARATE following token as their value
# when written without ``=`` (unary options, per Bazel's own
# startup_options.cc GetUnaryOption). Their space-separated values must be
# skipped while scanning for the verb — otherwise a value that happens to
# equal a verb string (e.g. ``--output_base test``) is misdetected as the verb.
_UNARY_STARTUP_OPTIONS = frozenset(
    {
        "--bazelrc",
        "--command_port",
        "--connect_timeout_secs",
        "--digest_function",
        "--failure_detail_out",
        "--host_jvm_args",
        "--host_jvm_profile",
        "--install_base",
        "--invocation_policy",
        "--io_nice_level",
        "--local_startup_timeout_secs",
        "--macos_qos_class",
        "--max_idle_secs",
        "--output_base",
        "--output_root",
        "--output_user_root",
        "--server_javabase",
        "--server_jvm_out",
        "--unix_digest_hash_attribute_name",
    }
)

# Boolean (nullary) startup options, matched by base name so both ``--home_rc``
# and ``--nohome_rc`` forms resolve. These never consume a following token.
_NULLARY_STARTUP_BASE = frozenset(
    {
        "autodetect_server_javabase",
        "batch",
        "batch_cpu_scheduling",
        "block_for_lock",
        "client_debug",
        "expand_configs_in_place",
        "home_rc",
        "host_jvm_debug",
        "idle_server_tasks",
        "ignore_all_rc_files",
        "preemptible",
        "shutdown_on_low_sys_mem",
        "system_rc",
        "unlimit_coredumps",
        "watchfs",
        "windows_enable_symlinks",
        "workspace_rc",
        "write_command_log",
    }
)


def _is_nullary_startup_option(token: str) -> bool:
    name = token.lstrip("-")
    if name.startswith("no"):
        name = name[2:]
    return name in _NULLARY_STARTUP_BASE


# Exit codes for nlfr's *own* failures, chosen to never collide with Bazel's
# codes (which we mirror faithfully whenever Bazel actually ran).
_EX_USAGE = 64  # BSD sysexits EX_USAGE: nlfr record was invoked incorrectly.
_EX_NOTFOUND = 127  # shell convention: the bazel/bazelisk executable was not found.


def run(args: argparse.Namespace) -> int:
    """Wrap a user's Bazel command, record evidence, and export projections."""

    command = _resolve_command(args.command)
    if not command:
        return _reject(
            args,
            status="no_command",
            message=(
                "nlfr record requires a command to wrap, e.g.\n"
                "  nlfr record -- bazel test //foo:bar"
            ),
            exit_code=_EX_USAGE,
        )

    if not _is_bazel_command(command):
        return _reject(
            args,
            status="non_bazel_command",
            message=(
                f"nlfr record v1 wraps bazel/bazelisk commands only, got: {command[0]!r}\n"
                "For other commands record them with:\n"
                "  nlfr run --mode generic --command '<your command>'"
            ),
            exit_code=_EX_USAGE,
        )

    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd().resolve()
    marker = _bazel_marker(workspace)
    if marker is None:
        return _reject(
            args,
            status="no_workspace_marker",
            message=(
                f"no Bazel workspace marker found in {workspace}\n"
                f"expected one of: {', '.join(_BAZEL_MARKERS)}\n"
                "Run nlfr record from your Bazel repo root, or pass --workspace PATH."
            ),
            exit_code=_EX_USAGE,
        )

    # Decide where the BEP will land: a user-supplied ``--build_event_json_file``
    # is honored verbatim and *bypasses verb detection entirely*. Otherwise we
    # must locate the Bazel verb so we can inject our own flag immediately after
    # it — and we refuse to guess when no known verb is present.
    user_bep = _user_bep_path(command, workspace)
    verb_index: int | None = None
    if user_bep is None:
        verb_index = _verb_index(command)
        if verb_index is None:
            return _reject(
                args,
                status="no_bazel_verb",
                message=(
                    "nlfr record could not find a known Bazel command verb "
                    "(build, test, run, query, coverage, ...) in:\n"
                    f"  {' '.join(command)}\n"
                    "nlfr will not guess which token is the verb: injecting "
                    "--build_event_json_file into Bazel's startup options would "
                    "corrupt your command and Bazel would reject it.\n"
                    "Fix: use a supported bazel verb (e.g. bazel test //your:target), "
                    "or pass your own --build_event_json_file=PATH, which nlfr "
                    "ingests directly and which bypasses verb detection."
                ),
                exit_code=_EX_USAGE,
            )

    if shutil.which(command[0]) is None:
        return _reject(
            args,
            status="bazel_not_found",
            message=(
                f"bazel executable not found on PATH: {command[0]!r}\n"
                "Install bazel/bazelisk (or add it to PATH), then re-run nlfr record."
            ),
            exit_code=_EX_NOTFOUND,
        )

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

    if user_bep is not None:
        bep_source = user_bep
        final_command = list(command)
    else:
        assert verb_index is not None  # guaranteed: no user_bep -> verb found above
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
        # Recorded evidence is local SQLite; the row keeps its record-time label.
        # The SHARING boundary is the projection: graph/runway recompute
        # redaction_state at projection time (nlfr.projectors.common.
        # redact_projection_node) so any local abs path scrubbed there is
        # labelled ``redacted``, never ``safe`` (issue #60).
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
            # Record-time label on local evidence; projection-time recomputation
            # is the honest sharing boundary (see the run upsert above, #60).
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

    # Out-of-range Bazel version signal (GitHub issue #85), grounded in the BEP's
    # OWN self-reported buildToolVersion — the honest, evidence-backed version, not
    # a separate `bazel version` guess. Non-blocking: it never changes record's exit
    # code (which mirrors Bazel's) and never alters the recorded evidence; it only
    # tells the operator this Bazel major is outside NLFR's tested matrix anchors.
    recorded_bazel_version = (
        extract_bep_tool_version(bep_source) if bep_captured else None
    )
    bazel_version_warning = out_of_range_bazel_warning(recorded_bazel_version)
    if bazel_version_warning is not None:
        print(f"nlfr record: {bazel_version_warning}", file=sys.stderr)

    terminal_status = _terminal_status(result)
    # nlfr mirrors Bazel's exit code whenever Bazel actually ran. If Bazel never
    # produced an exit code (executable vanished after the preflight PATH check,
    # or timed out), that is an nlfr-side blocker, not a Bazel result: surface it
    # as 127 with an honest record_error rather than masquerading as Bazel's 1.
    if result.exit_code is not None:
        process_exit = int(result.exit_code)
        record_error: str | None = None
    else:
        process_exit = _EX_NOTFOUND
        record_error = result.detail or "bazel did not run"
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
        "exit_code": process_exit,
        "record_error": record_error,
        "bep_captured": bep_captured,
        "bep_path": str(bep_source),
        "status": terminal_status,
        "bazel_version": recorded_bazel_version,
        # Advisory only; null unless the recorded Bazel major is outside the tested
        # matrix anchors (docs/wiki/reference/bazel-version-matrix.md).
        "bazel_version_warning": bazel_version_warning,
        "ingest_counts": bundle_counts,
        "results": [result.to_metadata()],
        "artifacts": [entry.to_manifest() for entry in manifest_entries],
        "source_kind": "collectable_v1",
        "confidence": "high",
        # run.json is local recorded evidence and legitimately carries the raw
        # command/workspace/bep_path. Label stays record-time; the shared
        # graph/runway projections scrub + relabel at projection time (#60).
        "redaction_state": "safe",
    }
    summary_entry = write_artifact(
        artifact_root,
        artifact_key="run.json",
        data=json.dumps(run_payload, indent=2, sort_keys=True) + "\n",
        producer_command=["nlfr", "record"],
        config_hash=None,
        # Record-time label on the local run.json artifact; projection layer is
        # the sharing boundary that recomputes redaction_state (#60).
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

    return process_exit


def _reject(
    args: argparse.Namespace,
    *,
    status: str,
    message: str,
    exit_code: int,
) -> int:
    """Emit an nlfr-side preflight failure and return its (non-Bazel) exit code.

    Under ``--json`` the failure is a structured object on stdout (so a CI
    pipeline parsing stdout JSON never gets empty output); otherwise the
    human-readable message goes to stderr. Field names align with the summary
    JSON: consumers read ``status`` / ``record_error`` / ``exit_code``.
    """

    if args.json:
        print(
            json.dumps(
                {
                    "status": status,
                    "record_error": message,
                    "exit_code": exit_code,
                    "bep_captured": False,
                    "source_kind": "collectable_v1",
                    "confidence": "high",
                    "redaction_state": "safe",
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(message, file=sys.stderr)
    return exit_code


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


def _verb_index(command: list[str]) -> int | None:
    """Index of the Bazel verb, found by an arity-aware left-to-right scan.

    Bazel invocations look like ``bazel [startup opts] VERB [opts] targets``.
    Startup options may take *space-separated* values (``--bazelrc /path``,
    ``--output_base /path``) — and such a value can even be the literal string
    of a verb (``--output_base test``), so neither "first non-``--`` token" nor
    "first token that matches a verb" is safe. Instead, walk the startup
    segment consuming options by arity: ``=``-form and nullary options take one
    token, known unary options take two. The first bare token reached this way
    must be the verb; if it isn't a known verb, or an unknown startup option
    makes the scan ambiguous, return ``None`` — the caller must not guess.
    """

    index = 1
    while index < len(command):
        token = command[index]
        if not token.startswith("-"):
            # First non-option token reached by arity-aware scanning: this is
            # the verb position. A target can never precede the verb.
            return index if token in _BAZEL_VERBS else None
        if "=" in token or _is_nullary_startup_option(token):
            index += 1
            continue
        if token in _UNARY_STARTUP_OPTIONS:
            index += 2  # skip the option's separated value, verb or not
            continue
        # Unknown startup option written without ``=``: unary vs nullary is
        # undecidable from the token alone.
        nxt = command[index + 1] if index + 1 < len(command) else None
        if nxt is not None and nxt.startswith("-"):
            # A separated value starting with ``-`` only occurs for jvm-arg
            # style options, which are all in the unary table — treat as
            # nullary and keep scanning.
            index += 1
            continue
        if nxt in _BAZEL_VERBS:
            # ``--unknown-flag test //x``: reading ``test`` as the verb matches
            # intent overwhelmingly more often than an unknown unary option
            # whose value is literally a verb string followed by another verb.
            index += 1
            continue
        return None
    return None


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
            # Record-time label; graph/runway scrub + relabel at the sharing
            # boundary (nlfr.projectors.common.redact_projection_node, #60).
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
