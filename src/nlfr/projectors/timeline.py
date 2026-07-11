"""Timeline projection: the flight record as a replayable event stream.

Renders recorded evidence — runs, ``evaluation`` verdict blocks, agent-receipt
provenance blocks — as one chronological, truth-labeled event list plus
derived "repair loop" chapters (a ``dispatch_fix_with_evidence`` verdict
through the next ``ok`` verdict). The canvas Replay lens renders ONLY this
projection; nothing here invents state:

* every event carries the truth quad copied from the row/block it was read
  from — a run event is as collectable as its ``runs`` row, a verdict event is
  as derived as its recorded verdict block;
* chapters are ``derived_v1`` by construction (a synthesis over verdict
  events), with ``evidence_refs`` naming the events they span;
* timestamps are the RECORDED ones (``started_at`` / ``generated_at`` /
  ``captured_at``) — never wall-clock at export time.

Multiple evidence databases merge into one stream (a development campaign
spans many ``nlfr record`` run groups); each event names its source database
by label so provenance survives the merge.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from nlfr.projectors.common import generated_at, row_to_dict, rows
from nlfr.redaction import RedactionConfig, redact_payload

TIMELINE_KINDS = ("run", "verdict", "receipt")

#: Chapter vocabulary. ``repair_loop`` is the only derived chapter kind in v1:
#: a recorded dispatch verdict opening, closed by the next ok verdict (or
#: honestly left ``open`` when the record contains no green close).
CHAPTER_KINDS = ("repair_loop",)


def build_timeline_projection(
    sources: list[tuple[str, sqlite3.Connection]],
) -> dict[str, Any]:
    """Build the timeline projection from ``(label, connection)`` sources."""

    events: list[dict[str, Any]] = []
    consulted: list[dict[str, Any]] = []
    source_labels: list[str] = []

    for label, conn in sources:
        source_labels.append(label)
        run_rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at, created_at, id"
        ).fetchall()
        run_dicts = [row_to_dict(row) for row in run_rows]
        run_ids = [row["id"] for row in run_dicts]
        block_rows = rows(conn, "proof_blocks", run_ids)
        consulted.extend(run_dicts)
        consulted.extend(block_rows)

        for run in run_dicts:
            ts = run.get("started_at") or run.get("created_at")
            if not ts:
                continue
            events.append(
                _event(
                    ts=ts,
                    kind="run",
                    label=f"{run.get('run_group') or 'run'} · {run.get('status')}",
                    source=label,
                    detail={
                        "run_group": run.get("run_group"),
                        "status": run.get("status"),
                        "mode": run.get("mode"),
                        "scenario": run.get("scenario"),
                    },
                    row=run,
                )
            )

        for block in block_rows:
            payload = block.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = block.get("block_kind")
            if kind == "evaluation":
                status = (payload.get("status") or {}).get("status")
                steps = payload.get("next_steps") or [{}]
                next_action = steps[0].get("action")
                classification = (payload.get("classification") or {}).get(
                    "classification"
                )
                ts = payload.get("generated_at")
                if not ts:
                    continue
                events.append(
                    _event(
                        ts=ts,
                        kind="verdict",
                        label=f"verdict · {status} · {next_action}",
                        source=label,
                        detail={
                            "status": status,
                            "next_action": next_action,
                            "classification": classification,
                            "run_group": payload.get("run_group"),
                        },
                        row=block,
                    )
                )
            elif kind == "agent_provenance":
                agent = payload.get("agent") if isinstance(payload.get("agent"), dict) else {}
                receipt = agent.get("receipt") if isinstance(agent.get("receipt"), dict) else None
                if not receipt:
                    continue
                ts = receipt.get("captured_at") or payload.get("generated_at")
                if not ts:
                    continue
                events.append(
                    _event(
                        ts=ts,
                        kind="receipt",
                        label=(
                            f"agent receipt · {receipt.get('model_resolved') or agent.get('model')}"
                            f" · {agent.get('provenance_class')}"
                        ),
                        source=label,
                        detail={
                            "model": receipt.get("model_resolved") or agent.get("model"),
                            "provenance_class": agent.get("provenance_class"),
                            "status": receipt.get("status"),
                            "output_tokens": (receipt.get("usage") or {}).get("output_tokens"),
                            "session_id": receipt.get("session_id"),
                        },
                        row=block,
                    )
                )

    events.sort(key=lambda item: item["ts"])
    for index, event in enumerate(events):
        event["index"] = index

    chapters = _derive_repair_chapters(events)

    projection = {
        "schema_version": 1,
        "projection_kind": "timeline",
        "generated_at": generated_at(),
        "sources": source_labels,
        "span": {
            "start": events[0]["ts"] if events else None,
            "end": events[-1]["ts"] if events else None,
        },
        "summary": {
            "events": len(events),
            "runs": sum(1 for event in events if event["kind"] == "run"),
            "verdicts": sum(1 for event in events if event["kind"] == "verdict"),
            "receipts": sum(1 for event in events if event["kind"] == "receipt"),
            "repair_loops": len(chapters),
        },
        "events": events,
        "chapters": chapters,
        "source_kind": "derived_v1",
        "confidence": _weakest(consulted),
        "evidence_refs": [f"db:{label}" for label in source_labels],
        "redaction_state": "safe",
    }
    result = redact_payload(projection, RedactionConfig())
    return result.payload  # type: ignore[return-value]


def _event(
    *,
    ts: str,
    kind: str,
    label: str,
    source: str,
    detail: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ts": ts,
        "kind": kind,
        "label": label,
        "source": source,
        "detail": detail,
        "source_kind": row.get("source_kind") or "derived_v1",
        "confidence": row.get("confidence") or "unknown",
        "evidence_refs": list(row.get("evidence_refs") or []),
        "redaction_state": row.get("redaction_state") or "unknown",
    }


def _derive_repair_chapters(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chapters spanning a dispatch verdict through the next ok verdict.

    Purely a synthesis over recorded verdict events: opens at
    ``next_action == dispatch_fix_with_evidence``, closes at the next verdict
    whose status is ``ok``. A dispatch with no recorded green close stays an
    honestly ``open`` chapter rather than being dropped or auto-closed.
    """

    chapters: list[dict[str, Any]] = []
    open_chapter: dict[str, Any] | None = None
    for event in events:
        if event["kind"] != "verdict":
            if open_chapter is not None:
                open_chapter["event_indexes"].append(event["index"])
            continue
        action = (event.get("detail") or {}).get("next_action")
        status = (event.get("detail") or {}).get("status")
        if open_chapter is None:
            if action == "dispatch_fix_with_evidence":
                open_chapter = {
                    "kind": "repair_loop",
                    "label": "verdict-driven repair",
                    "start_ts": event["ts"],
                    "end_ts": None,
                    "open": True,
                    "event_indexes": [event["index"]],
                    "source_kind": "derived_v1",
                    "confidence": "medium",
                    "evidence_refs": [f"event:{event['index']}"],
                    "redaction_state": "safe",
                }
        else:
            open_chapter["event_indexes"].append(event["index"])
            open_chapter["evidence_refs"].append(f"event:{event['index']}")
            if status == "ok":
                open_chapter["end_ts"] = event["ts"]
                open_chapter["open"] = False
                chapters.append(open_chapter)
                open_chapter = None
    if open_chapter is not None:
        chapters.append(open_chapter)
    return chapters


def _weakest(consulted: list[dict[str, Any]]) -> str:
    if not consulted:
        return "unknown"
    values = {row.get("confidence") for row in consulted}
    if values == {"high"}:
        return "high"
    if "low" in values:
        return "low"
    return "medium"
