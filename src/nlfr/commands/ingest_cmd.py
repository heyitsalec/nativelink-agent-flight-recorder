"""Evidence ingest command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_proof_block, upsert_run
from nlfr.ingest.bazel import (
    parse_bazel_bep,
    parse_bazel_execution_log,
    parse_bazel_profile,
    extract_bep_tool_version,
)
from nlfr.ingest.models import EvidenceBundle
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.ingest.worker_admin_stdout import parse_worker_admin_stdout


def run(args: argparse.Namespace) -> int:
    """Parse Bazel evidence files and ingest them into SQLite."""

    try:
        run_metadata = _run_metadata(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    evidence_files = _evidence_files(args)
    if not any(evidence_files.values()):
        print("no Bazel evidence files found for ingest", file=sys.stderr)
        return 2

    bundle = EvidenceBundle()
    if evidence_files["bep"] is not None:
        bundle.extend(
            parse_bazel_bep(
                evidence_files["bep"],
                source_kind=args.source_kind,
                evidence_ref=_evidence_ref(args.source_kind, evidence_files["bep"]),
            )
        )
    if evidence_files["execution_log"] is not None:
        bundle.extend(
            parse_bazel_execution_log(
                evidence_files["execution_log"],
                source_kind=args.source_kind,
                evidence_ref=_evidence_ref(args.source_kind, evidence_files["execution_log"]),
            )
        )
    if evidence_files["profile"] is not None:
        bundle.extend(
            parse_bazel_profile(
                evidence_files["profile"],
                evidence_ref=_evidence_ref(args.source_kind, evidence_files["profile"]),
            )
        )

    conn = initialize(connect(args.database))
    run_stable_key = (
        args.run_key
        or _metadata_string(run_metadata, "run_key")
        or _default_run_key(args.path)
    )
    run_id = upsert_run(
        conn,
        stable_key=run_stable_key,
        run_group=args.run_group or _metadata_string(run_metadata, "run_group") or "ingest",
        scenario=(
            args.scenario
            or _metadata_string(run_metadata, "scenario")
            or "fixture-ingest"
        ),
        mode=args.mode or _metadata_string(run_metadata, "mode") or "cache-only",
        status="ingested",
        source_kind=args.source_kind,
        confidence="high",
        evidence_refs=_bundle_evidence_refs(bundle),
        redaction_state="safe",
    )
    counts = ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key=run_stable_key,
        bundle=bundle,
    )
    readiness_path = _worker_readiness_path(args.path)
    if readiness_path is not None:
        counts["proof_blocks"] = counts.get("proof_blocks", 0) + _ingest_worker_readiness(
            conn,
            run_id=run_id,
            run_stable_key=run_stable_key,
            path=readiness_path,
        )
    worker_stdout_path = _worker_admin_stdout_path(args.path)
    if worker_stdout_path is not None:
        counts["proof_blocks"] = counts.get("proof_blocks", 0) + _ingest_worker_admin_stdout(
            conn,
            run_id=run_id,
            run_stable_key=run_stable_key,
            path=worker_stdout_path,
            source_kind=args.source_kind,
        )
    if evidence_files["bep"] is not None:
        counts["proof_blocks"] = counts.get("proof_blocks", 0) + _ingest_build_tool_identity(
            conn,
            run_id=run_id,
            run_stable_key=run_stable_key,
            bep_path=evidence_files["bep"],
            source_kind=args.source_kind,
        )

    payload = {
        "database": str(args.database),
        "run_id": run_id,
        "run_key": run_stable_key,
        "counts": counts,
    }
    if run_metadata:
        payload["run_metadata"] = {
            key: run_metadata[key]
            for key in (
                "run_id",
                "run_key",
                "run_group",
                "scenario",
                "mode",
                "artifact_root",
            )
            if key in run_metadata
        }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"ingested {sum(counts.values())} evidence records into {args.database}")
        print(f"run: {run_stable_key}")
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``ingest`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "ingest",
        help="ingest recorded evidence into SQLite",
        description="Ingest recorded evidence into SQLite.",
    )
    parser.add_argument("path", nargs="?", help="artifact manifest or evidence directory")
    parser.add_argument(
        "--database",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path",
    )
    parser.add_argument("--run-key", help="stable run key for idempotent ingest")
    parser.add_argument("--run-group", help="run group for inserted run")
    parser.add_argument("--scenario", help="scenario name")
    parser.add_argument("--mode", help="recorder mode label")
    parser.add_argument("--bep", help="Bazel BEP JSON or JSONL file")
    parser.add_argument("--execution-log", help="Bazel execution log JSON or JSONL file")
    parser.add_argument("--profile", help="Bazel profile JSON file")
    parser.add_argument(
        "--source-kind",
        choices=("collectable_v1", "simulated_v1"),
        default="collectable_v1",
        help="truth source label for directly parsed fixture or artifact records",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable summary")
    parser.set_defaults(handler=run)


def _evidence_files(args: argparse.Namespace) -> dict[str, Path | None]:
    files = {
        "bep": _path_or_none(args.bep),
        "execution_log": _path_or_none(args.execution_log),
        "profile": _path_or_none(args.profile),
    }
    if args.path is None:
        return files

    root = Path(args.path)
    if root.is_file():
        if root.name.endswith(".bep.json") or root.suffix == ".jsonl":
            files["bep"] = root
        elif "execution-log" in root.name:
            files["execution_log"] = root
        elif "profile" in root.name:
            files["profile"] = root
        return files

    if root.is_dir():
        candidates = {
            "bep": ("bazel.bep.json", "bep.jsonl"),
            "execution_log": ("bazel.execution-log.json", "execution-log.json"),
            "profile": ("bazel.profile.json", "profile.json"),
        }
        for key, names in candidates.items():
            if files[key] is not None:
                continue
            for name in names:
                candidate = root / name
                if candidate.exists():
                    files[key] = candidate
                    break
    return files


def _run_metadata(path: str | None) -> dict[str, object]:
    if path is None:
        return {}

    root = Path(path)
    if root.is_file():
        return {}

    run_metadata_path = root / "run.json"
    if not run_metadata_path.exists():
        return {}

    try:
        metadata = json.loads(run_metadata_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid run metadata at {run_metadata_path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"invalid run metadata at {run_metadata_path}: expected object")
    return metadata


def _worker_readiness_path(path: str | None) -> Path | None:
    if path is None:
        return None
    root = Path(path)
    if not root.is_dir():
        return None
    candidate = root / "worker-readiness.json"
    return candidate if candidate.exists() else None


def _worker_admin_stdout_path(path: str | None) -> Path | None:
    if path is None:
        return None
    root = Path(path)
    if not root.is_dir():
        return None
    candidate = root / "nativelink.stdout.txt"
    return candidate if candidate.exists() else None


def _ingest_worker_admin_stdout(
    conn,
    *,
    run_id: str,
    run_stable_key: str,
    path: Path,
    source_kind: str,
) -> int:
    evidence_ref = _evidence_ref(source_kind, path)
    events = parse_worker_admin_stdout(path, evidence_ref=evidence_ref)
    if not events:
        return 0

    payload = {
        "events": [
            {
                "worker_name": event.worker_name,
                "line_number": event.line_number,
                "evidence_ref": event.evidence_ref,
            }
            for event in events
        ],
        "source_kind": source_kind,
        "confidence": "high",
        "redaction_state": "safe",
    }
    worker_names = sorted({event.worker_name for event in events})
    upsert_proof_block(
        conn,
        stable_key=f"{run_stable_key}:proof:worker-admin-identity",
        run_id=run_id,
        block_key="worker-admin-identity",
        block_kind="worker_admin_identity_v1",
        title="Worker Admin Identity",
        summary=(
            f"NativeLink admin stdout records {len(events)} worker identity line(s) "
            f"for {', '.join(worker_names)}."
        ),
        payload=payload,
        source_kind=source_kind,
        confidence="high",
        evidence_refs=_dedupe([evidence_ref, f"artifact:{path.name}"]),
        redaction_state="safe",
    )
    return 1


def _ingest_build_tool_identity(
    conn,
    *,
    run_id: str,
    run_stable_key: str,
    bep_path: Path,
    source_kind: str,
) -> int:
    """Record which Bazel produced the BEP as a ``build_tool_identity_v1`` proof block.

    The BEP ``started`` event's ``buildToolVersion`` is the build tool's
    self-reported release string. NLFR stores it verbatim — evidence-carried, not
    fabricated — so an exported proof packet can state which Bazel produced the
    evidence. Returns 0 and stores nothing when the BEP declares no build tool
    version; the packet then reports the tool version as unknown rather than
    inventing one.
    """

    tool_version = extract_bep_tool_version(bep_path)
    if tool_version is None:
        return 0

    evidence_ref = _evidence_ref(source_kind, bep_path)
    upsert_proof_block(
        conn,
        stable_key=f"{run_stable_key}:proof:build-tool-identity",
        run_id=run_id,
        block_key="build-tool-identity",
        block_kind="build_tool_identity_v1",
        title="Build Tool Identity",
        summary=(
            f"BEP started event reports build tool version {tool_version}. This is "
            "the build tool's self-reported release string, recorded verbatim from "
            "the started event's buildToolVersion field — not fabricated."
        ),
        payload={
            "build_tool": "bazel",
            "build_tool_version": tool_version,
            "field": "started.buildToolVersion",
            "source_kind": source_kind,
            "confidence": "high",
            "redaction_state": "safe",
        },
        source_kind=source_kind,
        confidence="high",
        evidence_refs=_dedupe([evidence_ref, f"artifact:{bep_path.name}"]),
        redaction_state="safe",
    )
    return 1


def _ingest_worker_readiness(
    conn,
    *,
    run_id: str,
    run_stable_key: str,
    path: Path,
) -> int:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"invalid worker readiness evidence at {path}: expected object")
    evidence_refs = _dedupe(
        [
            f"artifact:{path.name}",
            *[
                str(ref)
                for ref in payload.get("evidence_refs", [])
                if isinstance(ref, str)
            ],
        ]
    )
    upsert_proof_block(
        conn,
        stable_key=f"{run_stable_key}:proof:worker-readiness",
        run_id=run_id,
        block_key="worker-readiness",
        block_kind="worker_readiness_boundary",
        title="Worker Readiness Boundary",
        summary=_worker_readiness_summary(payload),
        payload=payload,
        source_kind=str(payload.get("source_kind") or "collectable_v1"),
        confidence=str(payload.get("confidence") or "high"),
        evidence_refs=evidence_refs,
        redaction_state=str(payload.get("redaction_state") or "safe"),
    )
    return 1


def _worker_readiness_summary(payload: dict[str, object]) -> str:
    status = payload.get("status")
    configured_workers = payload.get("configured_workers")
    expected_workers = payload.get("expected_workers")
    if status == "worker_endpoints_ready":
        return (
            "NativeLink worker smoke endpoints opened for the configured worker "
            "boundary. Worker identity, queue time, scheduler assignment, and "
            "action placement remain unproven."
        )
    if status == "configuration_ready":
        return (
            f"NativeLink config declares {configured_workers} worker(s) for "
            f"expected worker gate {expected_workers}. Runtime endpoint readiness "
            "and action execution remain unproven."
        )
    return (
        "NativeLink worker smoke is blocked before worker-readiness evidence. "
        "No remote action execution claim is available."
    )


def _metadata_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value)
    return text or None


def _path_or_none(value: str | None) -> Path | None:
    return Path(value) if value else None


def _evidence_ref(source_kind: str, path: Path) -> str:
    return f"{source_kind}:{path.name}"


def _default_run_key(path: str | None) -> str:
    if path is None:
        return "ingest:cache-only"
    return f"ingest:{Path(path).resolve()}:cache-only"


def _bundle_evidence_refs(bundle: EvidenceBundle) -> list[str]:
    refs: list[str] = []
    records = [
        *bundle.targets,
        *bundle.actions,
        *bundle.cache_events,
        *bundle.failures,
    ]
    for record in records:
        for ref in record.evidence_refs:
            if ref not in refs:
                refs.append(ref)
    return refs


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
