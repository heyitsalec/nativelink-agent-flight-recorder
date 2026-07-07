"""Database maintenance commands.

The single subcommand today is ``nlfr db upgrade``, the WRITER-side counterpart
to the reader schema gate in :func:`nlfr.db.connection.connect_readonly`. Readers
no longer migrate a database on open — that hidden write to recorded evidence is
gone. Migrating an old database is therefore an explicit, operator-consented act
rather than a silent side effect of exporting a projection, and this command is
how the operator consents.
"""

from __future__ import annotations

import argparse
import sys

from nlfr.db import SCHEMA_VERSION, connect, database_defect, migrate


def _refuse_path_message(database: str, defect: str) -> str:
    """Render the writer-appropriate refusal for a path that is not a DB to upgrade."""

    if defect == "empty":
        headline = (
            f"nlfr: the file at '{database}' is empty (0 bytes), not an NLFR "
            "database — refusing to upgrade."
        )
    elif defect == "not_a_database":
        headline = (
            f"nlfr: the file at '{database}' is not a SQLite database — refusing "
            "to upgrade."
        )
    else:
        headline = (
            f"nlfr: no database at '{database}' to upgrade — refusing to create one."
        )
    return "\n".join(
        [
            headline,
            "`nlfr db upgrade` migrates an EXISTING database in place; it never "
            "creates one, so a path typo cannot fabricate an empty database.",
            "Point --db at an existing database, or record one first "
            "(e.g. `nlfr record -- bazel test //...`).",
        ]
    )


def db_upgrade(args: argparse.Namespace) -> int:
    """Migrate an existing database to the current schema version, in place.

    Idempotent: a database already at the current version reports "already
    current" and exits 0. A database NEWER than this build cannot be safely
    downgraded, so it is refused with a clean exit 2 (never a ``migrate()``
    traceback). All recorded rows are preserved by the migrations themselves.
    """

    defect = database_defect(args.db)
    if defect is not None:
        print(_refuse_path_message(str(args.db), defect), file=sys.stderr)
        return 2

    conn = connect(args.db)
    try:
        before = conn.execute("PRAGMA user_version").fetchone()[0]
        if before > SCHEMA_VERSION:
            print(
                f"nlfr: the database at '{args.db}' is schema v{before}, newer than "
                f"the schema v{SCHEMA_VERSION} this nlfr supports — refusing to "
                "downgrade.\nUpgrade nlfr instead, then re-run.",
                file=sys.stderr,
            )
            return 2
        migrate(conn)
        after = conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()

    if before == after:
        print(
            f"nlfr db upgrade: '{args.db}' is already at schema v{after}; nothing "
            "to upgrade."
        )
    else:
        print(
            f"nlfr db upgrade: migrated '{args.db}' from schema v{before} to "
            f"v{after} (all recorded rows preserved)."
        )
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``db`` command group on ``subparsers``."""

    parser = subparsers.add_parser(
        "db",
        help="database maintenance commands",
        description="Maintenance commands for the NLFR SQLite data spine.",
    )
    db_subparsers = parser.add_subparsers(
        dest="db_command",
        metavar="command",
        required=True,
    )

    upgrade_parser = db_subparsers.add_parser(
        "upgrade",
        help="migrate an existing database to the current schema version",
        description=(
            "Migrate an existing NLFR database to the current schema version, in "
            "place. Idempotent and row-preserving. Read commands never migrate on "
            "open, so this is the explicit, consented way to upgrade old evidence."
        ),
    )
    upgrade_parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path to upgrade",
    )
    upgrade_parser.set_defaults(handler=db_upgrade)
