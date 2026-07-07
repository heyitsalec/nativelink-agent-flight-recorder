"""Shared projection helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from sqlite3 import Connection, OperationalError, Row
from typing import Any

from nlfr.redaction import scrub_local_paths

TRUTH_DEFAULTS = {
    "source_kind": "unknown",
    "confidence": "unknown",
    "evidence_refs": [],
    "redaction_state": "unknown",
}


def generated_at() -> str:
    """Return an ISO-8601 UTC timestamp for projection metadata."""

    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def rows(conn: Connection, table: str, run_ids: list[str]) -> list[dict[str, Any]]:
    """Load normalized rows from ``table`` for the given run ids."""
    if not run_ids:
        return []
    placeholders = ", ".join("?" for _ in run_ids)
    result = conn.execute(
        f"SELECT * FROM {table} WHERE run_id IN ({placeholders}) ORDER BY created_at, id",
        run_ids,
    ).fetchall()
    return [row_to_dict(row) for row in result]


def run_rows(conn: Connection, run_group: str) -> list[dict[str, Any]]:
    """Load normalized run rows for a run group."""

    result = conn.execute(
        """
        SELECT * FROM runs
        WHERE run_group = ?
        ORDER BY started_at, created_at, id
        """,
        (run_group,),
    ).fetchall()
    return [row_to_dict(row) for row in result]


def available_run_groups(conn: Connection) -> list[dict[str, Any]]:
    """Run groups present in the DB (``run_group`` + ``run_count``) for guiding errors.

    Queries the ``runs`` table directly so a hard-error message (empty in-toto
    subject, missing compare side) can list the run groups that ARE present and
    turn the failure into recovery guidance. A file with no ``runs`` table (an
    unrelated SQLite file) is reported as "no run groups" rather than a traceback.
    Shared by the in-toto exporter and the compare exporter so their guidance
    lists stay identical (GitHub #47, #26).
    """

    try:
        result = conn.execute(
            """
            SELECT run_group, COUNT(*) AS run_count
            FROM runs
            GROUP BY run_group
            ORDER BY MAX(started_at) DESC, run_group ASC
            """
        ).fetchall()
    except OperationalError:
        return []
    return [
        {"run_group": row["run_group"], "run_count": row["run_count"]}
        for row in result
    ]


def row_to_dict(row: Row) -> dict[str, Any]:
    """Convert a SQLite row and decode JSON-backed columns."""

    value = dict(row)
    for key in ("command", "evidence_refs", "payload", "producer_command", "span"):
        if key in value and isinstance(value[key], str):
            value[key] = parse_json(value[key])
    return value


def parse_json(value: str) -> Any:
    """Parse JSON text, returning the original string on decode failure."""

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def truth(row: dict[str, Any]) -> dict[str, Any]:
    """Extract truth-label fields from a normalized row."""

    return {
        "source_kind": row.get("source_kind") or TRUTH_DEFAULTS["source_kind"],
        "confidence": row.get("confidence") or TRUTH_DEFAULTS["confidence"],
        "evidence_refs": row.get("evidence_refs") or [],
        "redaction_state": row.get("redaction_state") or TRUTH_DEFAULTS["redaction_state"],
    }


#: redaction_state values honestly upgradeable to ``redacted`` when the
#: projector had to scrub content. A stronger ``blocked`` (and an already
#: ``redacted``) is never downgraded — mirrors ``redaction.py`` semantics.
_UPGRADEABLE_REDACTION_STATES = {"safe", "unknown"}


def scrub_local_paths_deep(value: Any, roots: list[str] | None = None) -> tuple[Any, bool]:
    """Recursively scrub absolute local paths from a JSON-ish projection value.

    Walks strings, lists, and dicts, applying
    :func:`nlfr.redaction.scrub_local_paths` to every string. Returns
    ``(new_value, changed)`` where ``changed`` is ``True`` if any replacement
    occurred anywhere in the subtree. Non-string scalars pass through untouched.
    """

    if isinstance(value, str):
        new_value, count = scrub_local_paths(value, roots=roots)
        return new_value, count > 0
    if isinstance(value, list):
        changed = False
        new_list = []
        for item in value:
            new_item, child_changed = scrub_local_paths_deep(item, roots)
            new_list.append(new_item)
            changed = changed or child_changed
        return new_list, changed
    if isinstance(value, dict):
        changed = False
        new_dict: dict[str, Any] = {}
        for key, item in value.items():
            new_item, child_changed = scrub_local_paths_deep(item, roots)
            new_dict[key] = new_item
            changed = changed or child_changed
        return new_dict, changed
    return value, False


def redact_projection_node(
    node: dict[str, Any],
    *,
    fields: tuple[str, ...] = ("label", "payload"),
    roots: list[str] | None = None,
) -> dict[str, Any]:
    """Scrub local abs paths from a projected node/event and relabel honestly.

    This is the sharing boundary: ``graph``/``runway`` projections are what an
    adopter attaches to a PR or dashboard, so any absolute local path that
    survives into ``label``/``payload`` is scrubbed to a basename-preserving
    placeholder here. When ANY field needed scrubbing, the node's projected
    ``redaction_state`` is upgraded ``safe``/``unknown`` -> ``redacted`` — never
    claim ``safe`` for content that had to be scrubbed. A recorded ``blocked``
    (or already ``redacted``) state is preserved. The recorded SQLite row is
    never mutated; this is projection-time only. ``id`` is left untouched so
    edge references stay stable.
    """

    scrubbed = False
    for field in fields:
        if field in node and node[field] is not None:
            node[field], changed = scrub_local_paths_deep(node[field], roots)
            scrubbed = scrubbed or changed
    if scrubbed:
        current = node.get("redaction_state")
        if isinstance(current, str) and current in _UPGRADEABLE_REDACTION_STATES:
            node["redaction_state"] = "redacted"
    return node


def status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    """Count items by ``status`` or ``event_kind``."""

    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or item.get("event_kind") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def write_or_print(payload: dict[str, Any], output: str | None) -> None:
    """Write projection JSON to ``output`` or print it to stdout."""

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        from pathlib import Path

        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
