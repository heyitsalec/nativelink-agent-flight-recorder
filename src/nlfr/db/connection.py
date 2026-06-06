"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

DatabasePath = Union[str, Path]


def connect(database: DatabasePath = ":memory:") -> sqlite3.Connection:
    """Open an NLFR SQLite connection with repo-wide defaults."""

    database_text = str(database)
    if database_text != ":memory:":
        Path(database_text).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(database_text)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if database_text != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn
