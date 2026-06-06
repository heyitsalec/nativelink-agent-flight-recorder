"""Validation Runway projection."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Any

from nlfr.projectors.common import generated_at, rows, run_rows, status_counts, truth
from nlfr.projectors.remote_execution import sanitize_remote_endpoint_args


def export_validation_runway(conn: Connection, *, run_group: str) -> dict[str, Any]:
    runs = run_rows(conn, run_group)
    run_ids = [run["id"] for run in runs]
    invocations = rows(conn, "invocations", run_ids)
    cache_events = rows(conn, "cache_events", run_ids)
    targets = rows(conn, "targets", run_ids)
    failures = rows(conn, "failures", run_ids)
    artifacts = rows(conn, "artifacts", run_ids)

    events: list[dict[str, Any]] = []
    for run in runs:
        events.append(_event("run", run.get("scenario") or run["stable_key"], run))
    for item in invocations:
        events.append(_event(item.get("invocation_kind") or "invocation", item["stable_key"], item))
    for item in cache_events:
        lane = "cache-hit" if item.get("hit") == 1 else "cache-miss" if item.get("hit") == 0 else "cache"
        events.append(_event(lane, item.get("event_key") or item["stable_key"], item))
    for item in targets:
        events.append(_event("target", item.get("label") or item["stable_key"], item))
    for item in failures:
        events.append(_event("failure", item.get("message") or item["stable_key"], item))
    for item in artifacts:
        events.append(_event("artifact", item.get("artifact_key") or item["stable_key"], item))

    events.sort(key=lambda event: (event.get("started_at") or event.get("created_at") or "", event["id"]))

    return {
        "schema_version": 1,
        "projection_kind": "validation_runway",
        "generated_at": generated_at(),
        "run_group": run_group,
        "lanes": [
            {"id": "run", "label": "Run"},
            {"id": "nativelink", "label": "NativeLink"},
            {"id": "bazel", "label": "Bazel"},
            {"id": "cache", "label": "Cache"},
            {"id": "target", "label": "Targets"},
            {"id": "failure", "label": "Failures"},
            {"id": "artifact", "label": "Artifacts"},
        ],
        "summary": {
            "runs": len(runs),
            "events": len(events),
            "invocation_statuses": status_counts(invocations),
            "cache_events": status_counts(cache_events),
            "failures": len(failures),
        },
        "events": events,
    }


def _event(lane: str, label: object, row: dict[str, Any]) -> dict[str, Any]:
    normalized_lane = _lane(lane)
    return {
        "id": row["id"],
        "lane": normalized_lane,
        "label": str(label),
        "status": row.get("status") or row.get("event_kind"),
        "started_at": row.get("started_at") or row.get("created_at"),
        "ended_at": row.get("ended_at"),
        "payload": _payload(row),
        **truth(row),
    }


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in row.items()
        if key
        not in {
            "id",
            "source_kind",
            "confidence",
            "evidence_refs",
            "redaction_state",
            "created_at",
            "updated_at",
        }
        and value is not None
    }
    if "command" in payload:
        payload["command"] = sanitize_remote_endpoint_args(payload["command"])
    return payload


def _lane(value: str) -> str:
    if "nativelink" in value:
        return "nativelink"
    if "bazel" in value:
        return "bazel"
    if value.startswith("cache"):
        return "cache"
    return value
