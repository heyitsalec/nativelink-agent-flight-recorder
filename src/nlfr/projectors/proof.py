"""Proof packet projection."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from nlfr.projectors.common import generated_at, rows, run_rows, status_counts, truth
from nlfr.projectors.remote_execution import (
    UNSUPPORTED_REMOTE_EXECUTION_CLAIMS,
    remote_execution_endpoint_summaries,
    remote_execution_invocations,
    remote_execution_metrics,
)


def export_proof_packet(conn: Connection, *, run_group: str) -> dict[str, Any]:
    runs = run_rows(conn, run_group)
    run_ids = [run["id"] for run in runs]
    invocations = rows(conn, "invocations", run_ids)
    artifacts = rows(conn, "artifacts", run_ids)
    targets = rows(conn, "targets", run_ids)
    actions = rows(conn, "actions", run_ids)
    cache_events = rows(conn, "cache_events", run_ids)
    failures = rows(conn, "failures", run_ids)
    stored_blocks = rows(conn, "proof_blocks", run_ids)

    blocks = [
        _block(
            "scope",
            "Proof Scope",
            _scope_summary(runs),
            runs,
            claims=[
                "This packet can prove recorded commands, artifacts, statuses, and cache events present in the local evidence spine.",
                "This packet does not claim remote worker assignment, queue timing, or opaque SaaS telemetry.",
            ],
        ),
        _block(
            "invocations",
            "Invocation Results",
            "NativeLink and Bazel command outcomes captured by the recorder.",
            invocations,
            metrics=status_counts(invocations),
        ),
        _block(
            "cache",
            "Cache Evidence",
            "Cache hit/miss records extracted from available Bazel evidence.",
            cache_events,
            metrics=_cache_metrics(cache_events),
        ),
        _remote_execution_block(invocations),
        _block(
            "validation",
            "Validation Surface",
            "Targets, actions, and failures visible to the recorder.",
            [*targets, *actions, *failures],
            metrics={
                "targets": len(targets),
                "actions": len(actions),
                "failures": len(failures),
            },
        ),
        _block(
            "artifacts",
            "Artifact Chain",
            "Immutable files referenced by the proof packet.",
            artifacts,
            metrics={"artifacts": len(artifacts)},
        ),
    ]
    for item in stored_blocks:
        blocks.append(
            {
                "id": item["id"],
                "kind": item.get("block_kind"),
                "title": item.get("title") or item.get("block_key"),
                "summary": item.get("summary"),
                "payload": item.get("payload"),
                **truth(item),
            }
        )

    return {
        "schema_version": 1,
        "projection_kind": "proof_packet",
        "generated_at": generated_at(),
        "run_group": run_group,
        "summary": {
            "runs": len(runs),
            "artifacts": len(artifacts),
            "targets": len(targets),
            "actions": len(actions),
            "cache_events": len(cache_events),
            "failures": len(failures),
        },
        "blocks": blocks,
    }


def _block(
    block_id: str,
    title: str,
    summary: str,
    rows_for_truth: list[dict[str, Any]],
    *,
    claims: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": block_id,
        "kind": "derived_summary",
        "title": title,
        "summary": summary,
        "claims": claims or [],
        "metrics": metrics or {},
        "source_kind": _dominant_source_kind(rows_for_truth),
        "confidence": _confidence(rows_for_truth),
        "evidence_refs": _evidence_refs(rows_for_truth),
        "redaction_state": _redaction_state(rows_for_truth),
    }


def _remote_execution_block(invocations: list[dict[str, Any]]) -> dict[str, Any]:
    remote_items = remote_execution_invocations(invocations)
    evidence_rows = [item["invocation"] for item in remote_items]
    if remote_items:
        summary = (
            "Bazel invocation evidence shows remote execution was configured. "
            "Worker identity, queue time, and scheduler assignment remain unproven."
        )
        claims = [
            f"Observed Bazel --remote_executor on {len(remote_items)} invocation(s).",
            "This proves configuration intent, not successful worker execution.",
            "This packet does not claim worker identity, queue timing, or scheduler assignment.",
        ]
    else:
        summary = "No Bazel remote execution configuration was observed in recorded invocations."
        claims = [
            "Remote execution configuration evidence requires a recorded invocation with --remote_executor.",
            "Worker proof requires direct worker log or admin evidence.",
        ]
    return {
        **_block(
            "remote_execution",
            "Remote Execution Boundary",
            summary,
            evidence_rows,
            claims=claims,
            metrics=remote_execution_metrics(invocations),
        ),
        "payload": {
            "remote_executor_endpoints": remote_execution_endpoint_summaries(invocations),
            "unsupported_claims": list(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS),
        },
    }


def _scope_summary(runs: list[dict[str, Any]]) -> str:
    modes = sorted({str(run.get("mode")) for run in runs if run.get("mode")})
    if modes:
        return f"Local recorded evidence for AI-generated code validation ({', '.join(modes)} mode)."
    return "Local recorded evidence for AI-generated code validation."


def _cache_metrics(cache_events: list[dict[str, Any]]) -> dict[str, Any]:
    hits = sum(1 for item in cache_events if item.get("hit") == 1)
    misses = sum(1 for item in cache_events if item.get("hit") == 0)
    unknown = len(cache_events) - hits - misses
    total_known = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "unknown": unknown,
        "hit_rate": hits / total_known if total_known else None,
    }


def _dominant_source_kind(rows_for_truth: list[dict[str, Any]]) -> str:
    if not rows_for_truth:
        return "future"
    kinds = [
        str(row.get("source_kind"))
        for row in rows_for_truth
        if row.get("source_kind")
    ]
    if not kinds:
        return "derived_v1"
    priority = {
        "collectable_v1": 0,
        "derived_v1": 1,
        "simulated_v1": 2,
        "future": 3,
        "unknown": 4,
    }
    return min(kinds, key=lambda kind: priority.get(kind, 99))


def _confidence(rows_for_truth: list[dict[str, Any]]) -> str:
    if not rows_for_truth:
        return "unknown"
    values = {row.get("confidence") for row in rows_for_truth}
    if values == {"high"}:
        return "high"
    if "low" in values:
        return "low"
    return "medium"


def _evidence_refs(rows_for_truth: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for row in rows_for_truth:
        for ref in row.get("evidence_refs") or []:
            if ref not in refs:
                refs.append(ref)
    return refs


def _redaction_state(rows_for_truth: list[dict[str, Any]]) -> str:
    values = {row.get("redaction_state") for row in rows_for_truth}
    if not values:
        return "unknown"
    if values == {"safe"}:
        return "safe"
    if "blocked" in values:
        return "blocked"
    if "redacted" in values:
        return "redacted"
    return "unknown"
