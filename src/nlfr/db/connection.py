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
from typing import Optional, Union
from urllib.parse import quote

from nlfr.db.schema import SCHEMA_VERSION

DatabasePath = Union[str, Path]

#: The 16-byte header every real on-disk SQLite database begins with. Used to
#: reject a non-SQLite file up front rather than let ``mode=ro`` open it and
#: surface a later "file is not a database" traceback from deep in a projector.
_SQLITE_HEADER = b"SQLite format 3\x00"


class UnreadableDatabaseError(Exception):
    """Base for reader-side refusals the command layer renders as a clean exit 2.

    Every subclass carries a fully-rendered, actionable message (``str(exc)``)
    and NEVER a raw traceback: a read command that cannot honestly read its
    ``--db`` must say why and how to fix it, not crash with a ``no such table``
    or ``attempt to write a readonly database`` stack trace. Command handlers
    catch this base, print the message to stderr, and return 2.
    """


class DatabaseNotFoundError(UnreadableDatabaseError, FileNotFoundError):
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


class SchemaVersionError(UnreadableDatabaseError):
    """A read command was pointed at a DB whose schema version != this code's.

    Readers NEVER migrate a database on open — a migration is a WRITE, and
    silently mutating evidence as a side effect of reading it is exactly the
    fabrication this branch removes. On ``main`` readers called ``initialize()``
    and quietly upgraded any old DB; that hidden write is gone, so a schema
    mismatch is surfaced honestly instead:

    * found < supported: the DB predates this code. The operator must run the
      explicit ``nlfr db upgrade --db PATH`` (idempotent, preserves all rows) so
      schema mutation of evidence is a consented act, never a read side effect.
      Silently treating the missing newer tables as "empty" would emit an
      incomplete proof packet without saying why — fabrication-adjacent.
    * found > supported: the DB was written by a NEWER nlfr; this build cannot
      safely read it and will not downgrade it. Upgrade nlfr instead. (This
      mirrors ``migrate()``'s existing "newer than supported" guard, but as a
      clean exit 2 rather than a ``RuntimeError`` traceback.)
    """

    def __init__(
        self, database: DatabasePath, *, found_version: int, supported_version: int
    ) -> None:
        self.database = str(database)
        self.found_version = found_version
        self.supported_version = supported_version
        super().__init__(self._render())

    def _render(self) -> str:
        if self.found_version < self.supported_version:
            return "\n".join(
                [
                    f"nlfr: the database at '{self.database}' is schema "
                    f"v{self.found_version}, but this nlfr reads schema "
                    f"v{self.supported_version} — refusing to read.",
                    "A read command never migrates a database on open; upgrading "
                    "recorded evidence is an explicit, operator-consented act, "
                    "never a side effect of reading it.",
                    f"Upgrade it in place with:  nlfr db upgrade --db "
                    f"{self.database}",
                    "(the upgrade is idempotent and preserves every recorded "
                    "row), then re-run this command.",
                ]
            )
        return "\n".join(
            [
                f"nlfr: the database at '{self.database}' is schema "
                f"v{self.found_version}, newer than the schema v"
                f"{self.supported_version} this nlfr reads — refusing to read.",
                "It was written by a newer nlfr; this build cannot safely read it "
                "and will not downgrade it.",
                "Upgrade nlfr to a build that supports schema "
                f"v{self.found_version}, then re-run this command.",
            ]
        )


def database_defect(database: DatabasePath) -> Optional[str]:
    """Return why ``database`` is not a usable on-disk SQLite file, or ``None``.

    The reason is one of ``"missing"`` / ``"empty"`` / ``"not_a_database"`` —
    the exact vocabulary :class:`DatabaseNotFoundError` renders. Shared by
    :func:`connect_readonly` (a reader: raises the error) and ``nlfr db upgrade``
    (a writer: refuses to *create* a database it was asked to *upgrade*), so both
    apply one definition of "a real, existing SQLite database" and cannot drift.
    An in-memory database (``":memory:"``) has no on-disk file and is reported as
    ``"missing"``.
    """

    database_text = str(database)
    if database_text == ":memory:":
        return "missing"
    path = Path(database_text)
    if not path.is_file():
        return "missing"
    if path.stat().st_size == 0:
        # mode=ro would open a zero-byte file as a valid, tableless database and
        # every read would return honest-looking nothing. Reject it explicitly.
        return "empty"
    with path.open("rb") as handle:
        header = handle.read(len(_SQLITE_HEADER))
    if header != _SQLITE_HEADER:
        return "not_a_database"
    return None


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


def _is_readonly_write_error(exc: sqlite3.OperationalError) -> bool:
    """True for SQLite's "attempt to write a readonly database" error.

    Writers (WAL journal_mode) leave a database whose header says WAL. Opening
    such a file with ``mode=ro`` still makes SQLite try to create the
    ``-shm``/``-wal`` sidecar files to build a read snapshot — an
    *unwritable directory* turns that attempt into this error. It fires on the
    open OR the first header read (``PRAGMA user_version`` below), so both are
    wrapped in the fallback.
    """

    return "readonly database" in str(exc).lower()


def _open_ro(uri_query: str, resolved: str) -> tuple[sqlite3.Connection, int]:
    """Open ``resolved`` read-only with ``uri_query`` and read its schema version.

    Returns ``(conn, user_version)``. Runs ``PRAGMA user_version`` here, inside
    the caller's fallback ``try``, because on a WAL database that header read is
    the first operation that touches the file and can raise the readonly-write
    error (see :func:`_is_readonly_write_error`).
    """

    conn = sqlite3.connect(f"file:{resolved}?{uri_query}", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        # foreign_keys is a connection-level pragma (no file write) — harmless
        # for reads and keeps parity with the writer. journal_mode is NOT set:
        # switching to WAL is a write and is pointless for a read-only handle.
        conn.execute("PRAGMA foreign_keys = ON")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except BaseException:
        conn.close()
        raise
    return conn, version


def connect_readonly(database: DatabasePath) -> sqlite3.Connection:
    """Open a READ-ONLY connection that never creates or migrates a database.

    Opens via the SQLite ``mode=ro`` URI. A nonexistent path, a zero-byte file,
    or a non-SQLite file raises :class:`DatabaseNotFoundError` — the emptiness/
    header checks are explicit and run before SQLite is handed the path, because
    ``mode=ro`` alone happily opens a zero-byte file as a valid EMPTY database
    (the silent-empty trap). A database whose schema version does not match this
    build raises :class:`SchemaVersionError` (readers never migrate on open).

    ``mode=ro`` is not a total write barrier: opening a WAL-mode database (every
    writer creates one) makes SQLite create ``-shm``/``-wal`` sidecar files to
    build a read snapshot, so a plain ``mode=ro`` read on a WRITABLE directory
    may leave those sidecars behind. In an UNWRITABLE directory (the
    protect-the-evidence scenario NLFR exists for — e.g. ``chmod 555``) that
    sidecar creation instead fails with "attempt to write a readonly database".
    We therefore try ``mode=ro`` first and, only if that raises the
    readonly-write error, retry with ``mode=ro&immutable=1``. ``immutable=1``
    reads the main file directly with no sidecars, and is safe *precisely here*:
    a directory SQLite cannot write to cannot be hosting a live writer, so the
    "no concurrent writer" assumption ``immutable=1`` requires already holds. We
    do NOT use ``immutable=1`` on writable directories, where a concurrent
    writer is possible and that assumption would be unsound.
    """

    defect = database_defect(database)
    if defect is not None:
        raise DatabaseNotFoundError(database, reason=defect)

    # Resolve to an absolute path so the URI is unambiguous (``file:/abs?...``);
    # a relative ``file:foo?...`` risks the ``file://authority`` parsing edge.
    resolved = quote(str(Path(str(database)).resolve()))
    try:
        conn, version = _open_ro("mode=ro", resolved)
    except sqlite3.OperationalError as exc:
        if not _is_readonly_write_error(exc):
            raise
        # Unwritable directory: no live writer is possible, so immutable=1 is
        # safe and reads the main file without touching the -shm/-wal sidecars.
        conn, version = _open_ro("mode=ro&immutable=1", resolved)

    if version != SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionError(
            database, found_version=version, supported_version=SCHEMA_VERSION
        )
    return conn
