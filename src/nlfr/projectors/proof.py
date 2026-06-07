"""Proof packet projection."""

from __future__ import annotations

from datetime import UTC, datetime
from sqlite3 import Connection
from typing import Any

from nlfr.projectors.common import generated_at, rows, run_rows, status_counts, truth
from nlfr.projectors.remote_execution import (
    remote_execution_endpoint_summaries,
    remote_execution_invocations,
    remote_execution_metrics,
    unsupported_claims_for_group,
    worker_identity_events_for_run,
)


def export_proof_packet(conn: Connection, *, run_group: str) -> dict[str, Any]:
    """Build the proof packet projection for a run group."""

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
        *_cache_economics_blocks(runs, invocations, cache_events),
        _remote_execution_block(invocations, stored_blocks),
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


def _remote_execution_block(
    invocations: list[dict[str, Any]],
    proof_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    remote_items = remote_execution_invocations(invocations)
    evidence_rows = [item["invocation"] for item in remote_items]
    worker_identity_observed = any(
        worker_identity_events_for_run(str(item["invocation"].get("run_id") or ""), proof_blocks)
        for item in remote_items
    )
    if remote_items:
        if worker_identity_observed:
            summary = (
                "Bazel invocation evidence shows remote execution was configured and "
                "direct worker admin stdout records worker identity. Queue time and "
                "scheduler assignment remain unproven."
            )
            claims = [
                f"Observed Bazel --remote_executor on {len(remote_items)} invocation(s).",
                "Direct worker admin stdout evidence records worker identity for this run group.",
                "This packet does not claim queue timing or scheduler assignment.",
            ]
        else:
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
            metrics=remote_execution_metrics(invocations, proof_blocks),
        ),
        "payload": {
            "remote_executor_endpoints": remote_execution_endpoint_summaries(invocations),
            "unsupported_claims": unsupported_claims_for_group(invocations, proof_blocks),
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


def _cache_economics_blocks(
    runs: list[dict[str, Any]],
    invocations: list[dict[str, Any]],
    cache_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    legs = _per_run_cache_legs(runs, invocations, cache_events)
    if not legs:
        return []

    comparison = _cold_warm_comparison(legs)
    summary = (
        "Per-run cache economics from recorded Bazel evidence. "
        "Durations come from run or invocation timestamps when present."
    )
    claims = [
        "Hit rates and durations are derived from ingested cache events and run timestamps.",
        "This block does not claim dollar savings or fleet-wide cache performance.",
    ]
    if comparison:
        if comparison.get("warm_hit_rate_higher"):
            claims.append(
                "Warm leg recorded a higher cache hit_rate than the cold leg in this run_group."
            )
        if comparison.get("warm_duration_lower"):
            claims.append(
                "Warm leg recorded a lower duration than the cold leg in this run_group."
            )
        if not comparison.get("warm_hit_rate_higher") and not comparison.get("warm_duration_lower"):
            claims.append(
                "No collectable warm-over-cold improvement in hit_rate or duration for this run_group."
            )

    block = {
        **_block(
            "cache_economics",
            "Cache Economics",
            summary,
            cache_events,
            claims=claims,
            metrics={
                "legs": len(legs),
                **(comparison or {}),
            },
        ),
        "payload": {
            "legs": legs,
            "comparison": comparison,
        },
    }
    return [block]


def _per_run_cache_legs(
    runs: list[dict[str, Any]],
    invocations: list[dict[str, Any]],
    cache_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(runs) < 2:
        return []

    events_by_run: dict[str, list[dict[str, Any]]] = {}
    for event in cache_events:
        run_id = str(event.get("run_id") or "")
        events_by_run.setdefault(run_id, []).append(event)

    invocations_by_run: dict[str, list[dict[str, Any]]] = {}
    for invocation in invocations:
        run_id = str(invocation.get("run_id") or "")
        invocations_by_run.setdefault(run_id, []).append(invocation)

    legs: list[dict[str, Any]] = []
    for run in runs:
        run_id = str(run["id"])
        leg_cache = _cache_metrics(events_by_run.get(run_id, []))
        duration_seconds = _run_duration_seconds(run, invocations_by_run.get(run_id, []))
        legs.append(
            {
                "run_id": run_id,
                "scenario": run.get("scenario"),
                "mode": run.get("mode"),
                "status": run.get("status"),
                "duration_seconds": duration_seconds,
                **leg_cache,
            }
        )
    return legs


def _cold_warm_comparison(legs: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_scenario = {str(leg.get("scenario")): leg for leg in legs if leg.get("scenario")}
    cold = by_scenario.get("cold-cache")
    warm = by_scenario.get("warm-cache")
    if not cold or not warm:
        return None

    cold_rate = cold.get("hit_rate")
    warm_rate = warm.get("hit_rate")
    cold_duration = cold.get("duration_seconds")
    warm_duration = warm.get("duration_seconds")

    warm_hit_rate_higher = (
        cold_rate is not None
        and warm_rate is not None
        and warm_rate > cold_rate
    )
    warm_duration_lower = (
        cold_duration is not None
        and warm_duration is not None
        and warm_duration < cold_duration
    )
    return {
        "cold_scenario": "cold-cache",
        "warm_scenario": "warm-cache",
        "cold_hit_rate": cold_rate,
        "warm_hit_rate": warm_rate,
        "cold_duration_seconds": cold_duration,
        "warm_duration_seconds": warm_duration,
        "warm_hit_rate_higher": warm_hit_rate_higher,
        "warm_duration_lower": warm_duration_lower,
        "hit_rate_delta": (
            warm_rate - cold_rate
            if cold_rate is not None and warm_rate is not None
            else None
        ),
        "duration_delta_seconds": (
            warm_duration - cold_duration
            if cold_duration is not None and warm_duration is not None
            else None
        ),
    }


def _run_duration_seconds(
    run: dict[str, Any],
    invocations: list[dict[str, Any]],
) -> float | None:
    run_duration = _duration_seconds(run.get("started_at"), run.get("ended_at"))
    if run_duration is not None:
        return run_duration

    invocation_durations = [
        value
        for invocation in invocations
        if (value := _duration_seconds(invocation.get("started_at"), invocation.get("ended_at")))
        is not None
    ]
    if not invocation_durations:
        return None
    return max(invocation_durations)


def _duration_seconds(started_at: str | None, ended_at: str | None) -> float | None:
    if not started_at or not ended_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    delta = (end - start).total_seconds()
    return delta if delta >= 0 else None


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
