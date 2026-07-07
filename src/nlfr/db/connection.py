"""SQLite connection helpers.

Writers and readers open databases with different rules. Writers
(``nlfr record``/``run``/``ingest``/``init``) legitimately create parent
directories and a fresh schema on open — see :func:`connect`. Readers (the
``graph``/``proof``/``runway``/``compare`` exporters and the compare index/
history reports) must NEVER auto-create or migrate anything — see
:func:`connect_readonly`. A reader that auto-created a database would turn a
single ``--db`` typo into a schema-valid, fully truth-labeled, zero-value
projection: a confident comparison of real data against nothing (GitHub #47).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union
from urllib.parse import quote

DatabasePath = Union[str, Path]

#: The 16-byte header every real on-disk SQLite database begins with. Used to
#: reject a non-SQLite file up front rather than let ``mode=ro`` open it and
#: surface a later "file is not a database" traceback from deep in a projector.
_SQLITE_HEADER = b"SQLite format 3\x00"


class DatabaseNotFoundError(FileNotFoundError):
    """A read command was pointed at a ``--db`` that is not a usable database.

    NLFR readers must never auto-create or migrate a database. A missing path, a
    zero-byte file, or a non-SQLite file is therefore a HARD ERROR — otherwise a
    single ``--db`` typo silently auto-creates an empty schema and the reader
    emits a schema-valid, fully truth-labeled, zero-value projection: "a
    confidently-labeled comparison of real data against nothing" (GitHub #47).
    This exception carries the offending path and renders an actionable message
    that also points at where ``nlfr record`` actually writes. The command layer
    converts it to exit 2; no database file is ever left behind.
    """

    def __init__(self, database: DatabasePath, *, reason: str = "missing") -> None:
        self.database = str(database)
        self.reason = reason
        super().__init__(self._render())

    def _render(self) -> str:
        if self.reason == "empty":
            headline = (
                f"nlfr: the file at '{self.database}' is empty (0 bytes), not an "
                "NLFR database — refusing to read."
            )
        elif self.reason == "not_a_database":
            headline = (
                f"nlfr: the file at '{self.database}' is not a SQLite database — "
                "refusing to read."
            )
        else:
            headline = f"nlfr: no NLFR database at '{self.database}' — refusing to read."
        return "\n".join(
            [
                headline,
                "A read command never creates or migrates a database; a "
                "missing/empty --db is a hard error so a path typo cannot "
                "fabricate an empty, zero-value result.",
                "`nlfr record` writes per-run-group databases under "
                "data/nlfr-record/<run-group>/nlfr.sqlite.",
                "Point --db at an existing database, or record one first "
                "(e.g. `nlfr record -- bazel test //...`).",
            ]
        )


def connect(database: DatabasePath = ":memory:") -> sqlite3.Connection:
    """Open a WRITER connection with repo-wide defaults (auto-creates the file).

    Writers legitimately create the parent directory and a fresh schema on open.
    Readers must use :func:`connect_readonly`, which never creates anything.
    """

    database_text = str(database)
    if database_text != ":memory:":
        Path(database_text).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(database_text)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if database_text != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def connect_readonly(database: DatabasePath) -> sqlite3.Connection:
    """Open a READ-ONLY connection that never creates or migrates a database.

    Opens via the SQLite ``mode=ro`` URI so the reader also cannot accidentally
    write. A nonexistent path, a zero-byte file, or a non-SQLite file raises
    :class:`DatabaseNotFoundError` and leaves NO file behind — ``mode=ro`` alone
    is not enough because it happily opens a zero-byte file as a valid EMPTY
    database (the silent-empty trap), so the emptiness checks are explicit and
    run before SQLite is ever handed the path.
    """

    database_text = str(database)
    if database_text == ":memory:":
        # An in-memory database is empty by construction; a reader that opened
        # one would be "reading" fabricated nothing — exactly the failure this
        # guards against.
        raise DatabaseNotFoundError(":memory:", reason="missing")

    path = Path(database_text)
    if not path.is_file():
        raise DatabaseNotFoundError(database_text, reason="missing")
    if path.stat().st_size == 0:
        # mode=ro would open a zero-byte file as a valid, tableless database and
        # every read would return honest-looking nothing. Reject it explicitly.
        raise DatabaseNotFoundError(database_text, reason="empty")
    with path.open("rb") as handle:
        header = handle.read(len(_SQLITE_HEADER))
    if header != _SQLITE_HEADER:
        raise DatabaseNotFoundError(database_text, reason="not_a_database")

    # Resolve to an absolute path so the URI is unambiguous (``file:/abs?...``);
    # a relative ``file:foo?...`` risks the ``file://authority`` parsing edge.
    uri = f"file:{quote(str(path.resolve()))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    # foreign_keys is a connection-level pragma (no file write) — harmless for
    # reads and keeps parity with the writer. journal_mode is intentionally NOT
    # set: switching to WAL is a write and is pointless for a read-only handle.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
