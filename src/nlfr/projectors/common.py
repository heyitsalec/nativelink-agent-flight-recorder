"""Shared projection helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from sqlite3 import Connection, Row
from typing import Any

TRUTH_DEFAULTS = {
    "source_kind": "unknown",
    "confidence": "unknown",
    "evidence_refs": [],
    "redaction_state": "unknown",
}


def generated_at() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def rows(conn: Connection, table: str, run_ids: list[str]) -> list[dict[str, Any]]:
    if not run_ids:
        return []
    placeholders = ", ".join("?" for _ in run_ids)
    result = conn.execute(
        f"SELECT * FROM {table} WHERE run_id IN ({placeholders}) ORDER BY created_at, id",
        run_ids,
    ).fetchall()
    return [row_to_dict(row) for row in result]


def run_rows(conn: Connection, run_group: str) -> list[dict[str, Any]]:
    result = conn.execute(
        """
        SELECT * FROM runs
        WHERE run_group = ?
        ORDER BY started_at, created_at, id
        """,
        (run_group,),
    ).fetchall()
    return [row_to_dict(row) for row in result]


def row_to_dict(row: Row) -> dict[str, Any]:
    value = dict(row)
    for key in ("command", "evidence_refs", "payload", "producer_command", "span"):
        if key in value and isinstance(value[key], str):
            value[key] = parse_json(value[key])
    return value


def parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def truth(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": row.get("source_kind") or TRUTH_DEFAULTS["source_kind"],
        "confidence": row.get("confidence") or TRUTH_DEFAULTS["confidence"],
        "evidence_refs": row.get("evidence_refs") or [],
        "redaction_state": row.get("redaction_state") or TRUTH_DEFAULTS["redaction_state"],
    }


def status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or item.get("event_kind") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def write_or_print(payload: dict[str, Any], output: str | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        from pathlib import Path

        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
