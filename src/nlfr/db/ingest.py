"""Idempotent ingest helpers for the SQLite data spine."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from nlfr.db.schema import CORE_TABLES
from nlfr.ids import stable_id

_JSON_COLUMNS = {"command", "evidence_refs", "payload", "producer_command", "span"}


def upsert_record(
    conn: sqlite3.Connection,
    table: str,
    *,
    stable_key: str,
    values: dict[str, Any] | None = None,
    record_id: str | None = None,
) -> str:
    """Insert a record once and return its id on later duplicate ingests."""

    if table not in CORE_TABLES:
        raise ValueError(f"unsupported ingest table: {table}")

    table_columns = _table_columns(conn, table)
    row = {"id": record_id or stable_id(table, stable_key), "stable_key": stable_key}
    row.update(values or {})

    unknown_columns = set(row) - table_columns
    if unknown_columns:
        unknown = ", ".join(sorted(unknown_columns))
        raise ValueError(f"unknown columns for {table}: {unknown}")

    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    params = [_coerce_value(column, row[column]) for column in columns]

    with conn:
        conn.execute(
            f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholders})",
            params,
        )

    existing = conn.execute(
        f"SELECT id FROM {table} WHERE stable_key = ?",
        (stable_key,),
    ).fetchone()
    if existing is None:
        raise RuntimeError(f"failed to ingest {table} record with key {stable_key}")
    return existing["id"]


def upsert_run(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing run row id."""

    return upsert_record(conn, "runs", stable_key=stable_key, values=values)


def upsert_change(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing change row id."""

    return upsert_record(conn, "changes", stable_key=stable_key, values=values)


def upsert_invocation(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing invocation row id."""

    return upsert_record(conn, "invocations", stable_key=stable_key, values=values)


def upsert_artifact(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing artifact row id."""

    return upsert_record(conn, "artifacts", stable_key=stable_key, values=values)


def upsert_artifact_reference(
    conn: sqlite3.Connection, *, stable_key: str, **values: Any
) -> str:
    """Insert or return an existing artifact-reference verification row id."""

    return upsert_record(conn, "artifact_references", stable_key=stable_key, values=values)


def upsert_target(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing target row id."""

    return upsert_record(conn, "targets", stable_key=stable_key, values=values)


def upsert_action(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing action row id."""

    return upsert_record(conn, "actions", stable_key=stable_key, values=values)


def upsert_cache_event(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing cache event row id."""

    return upsert_record(conn, "cache_events", stable_key=stable_key, values=values)


def upsert_failure(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing failure row id."""

    return upsert_record(conn, "failures", stable_key=stable_key, values=values)


def upsert_graph_node(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing graph node row id."""

    return upsert_record(conn, "graph_nodes", stable_key=stable_key, values=values)


def upsert_graph_edge(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing graph edge row id."""

    return upsert_record(conn, "graph_edges", stable_key=stable_key, values=values)


def upsert_proof_block(conn: sqlite3.Connection, *, stable_key: str, **values: Any) -> str:
    """Insert or return an existing proof block row id."""

    return upsert_record(conn, "proof_blocks", stable_key=stable_key, values=values)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _coerce_value(column: str, value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Path):
        return str(value)
    if column in _JSON_COLUMNS and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return value
