"""Multi-run compare commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from nlfr.db.connection import (
    DatabaseNotFoundError,
    SchemaVersionError,
    UnreadableDatabaseError,
    connect_readonly,
)
from nlfr.projectors.common import (
    generated_at,
    run_rows,
    scrub_local_paths_deep,
    write_or_print,
)
from nlfr.projectors.compare import (
    MissingRunGroupError,
    build_compare_projection,
    export_compare_projection,
    export_history_projection,
    list_run_group_index,
    require_run_group,
)
from nlfr.projectors.proof import export_proof_packet
from nlfr.retention_policy import retention_policy_summary

#: The per-run-group database filename `nlfr record` writes. Discovery under
#: ``--db-root`` matches EXACTLY this file one directory level down (see
#: :func:`_discover_record_dbs`).
_RECORD_DB_FILENAME = "nlfr.sqlite"


def _discover_record_dbs(db_root: str) -> list[tuple[str, str]]:
    """Discover per-run-group databases under a ``nlfr record`` layout root.

    ``nlfr record`` writes each run group to
    ``<db_root>/<run-group>/nlfr.sqlite`` (``record_cmd`` builds
    ``<workspace>/data/nlfr-record/<run-group>`` as the output dir and opens
    ``nlfr.sqlite`` inside it). Discovery mirrors that EXACT layout and nothing
    else: it looks EXACTLY ONE directory level down — every immediate
    subdirectory of ``db_root`` that contains an ``nlfr.sqlite`` file — and never
    recurses into arbitrary trees. Immediate subdirectories WITHOUT an
    ``nlfr.sqlite`` (and any non-directory entries) are ignored, so an
    unrelated tree under ``db_root`` cannot inflate the listing. Returns
    ``(discovered_group, db_path)`` pairs sorted by directory name for a
    deterministic listing; ``discovered_group`` is the directory name, which the
    record layout uses AS the run group — a boundary-safe locator that survives
    path scrubbing (see :func:`_scrub_entries`).
    """

    root = Path(db_root)
    discovered: list[tuple[str, str]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        candidate = child / _RECORD_DB_FILENAME
        if candidate.is_file():
            discovered.append((child.name, str(candidate)))
    return discovered


def _open_or_reason(
    db_path: str,
) -> tuple[Any | None, dict[str, Any] | None]:
    """Open ``db_path`` read-only, or return an honest unreadable reason.

    Returns ``(conn, None)`` when the database opens under the SAME read-only
    gate every other reader uses (:func:`connect_readonly`), or
    ``(None, reason)`` when it does not. ``reason`` carries a short ``reason``
    code plus the fully-rendered, actionable ``detail`` message — for an
    old-schema database that ``detail`` already names ``nlfr db upgrade``. This
    never mutates or auto-creates anything: a zero-byte / missing / non-SQLite
    file and a schema mismatch are reported, not repaired.
    """

    try:
        conn = connect_readonly(db_path)
    except SchemaVersionError as exc:
        return None, {
            "reason": f"schema_v{exc.found_version}",
            "found_schema_version": exc.found_version,
            "detail": str(exc),
        }
    except DatabaseNotFoundError as exc:
        return None, {"reason": exc.reason, "detail": str(exc)}
    except UnreadableDatabaseError as exc:  # pragma: no cover - defensive catch-all
        return None, {"reason": "unreadable", "detail": str(exc)}
    return conn, None


def _order_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order a multi-DB listing: readable groups newest-first, problems last.

    Readable run-group entries sort by ``last_started_at`` DESC then
    ``run_group`` ASC (matching the single-``--db`` index order); existing but
    empty databases and unreadable databases follow, each sorted by
    ``discovered_group``. Ordering is a presentation choice over a LISTING — it
    never merges rows across databases, so stable run ids can never collide.
    """

    readable = [e for e in entries if e.get("readable") and e.get("run_group")]
    empty = [e for e in entries if e.get("readable") and not e.get("run_group")]
    unreadable = [e for e in entries if not e.get("readable")]
    readable.sort(key=lambda e: e.get("run_group") or "")
    readable.sort(key=lambda e: e.get("last_started_at") or "", reverse=True)
    empty.sort(key=lambda e: e.get("discovered_group") or "")
    unreadable.sort(key=lambda e: e.get("discovered_group") or "")
    return [*readable, *empty, *unreadable]


def _scrub_entries(
    entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Scrub absolute local paths from listing entries at the sharing boundary.

    A per-run-group ``database`` path (and any raw path inside an unreadable
    entry's ``detail`` message) is scrubbed with the #63 redaction helper: an
    ABSOLUTE path collapses to a basename-preserving placeholder, a relative
    ``data/nlfr-record/<group>/nlfr.sqlite`` passes through untouched. When an
    entry that carries a ``redaction_state`` truth label had content scrubbed,
    that label is honestly upgraded ``safe``/``unknown`` -> ``redacted`` (never
    claim ``safe`` for scrubbed content; a stronger label is preserved). Returns
    ``(entries, any_scrubbed)``. The run group locator survives because the
    record layout keeps the group in ``discovered_group`` (a bare directory
    name, not a path), so the listing stays unambiguous after redaction even
    though absolute ``database`` values collapse to the same placeholder.
    """

    scrubbed_any = False
    out: list[dict[str, Any]] = []
    for entry in entries:
        scrubbed_entry, changed = scrub_local_paths_deep(entry)
        if changed:
            scrubbed_any = True
            state = scrubbed_entry.get("redaction_state")
            if isinstance(state, str) and state in {"safe", "unknown"}:
                scrubbed_entry["redaction_state"] = "redacted"
        out.append(scrubbed_entry)
    return out, scrubbed_any


def _db_root_error(db_root: str, headline: str) -> int:
    """Print an honest ``--db-root`` refusal to stderr and return exit code 2."""

    print(headline, file=sys.stderr)
    print(
        "`nlfr record` writes per-run-group databases under "
        "data/nlfr-record/<run-group>/nlfr.sqlite; point --db-root at that "
        "parent directory (the discovery rule matches <group>/nlfr.sqlite one "
        "level down and ignores everything else).",
        file=sys.stderr,
    )
    return 2


def _collect_db_root_entries(
    args: argparse.Namespace,
    per_db: Any,
) -> tuple[list[dict[str, Any]], int, int] | int:
    """Discover databases under ``--db-root`` and build per-database entries.

    ``per_db`` maps an open read-only connection + its ``(discovered_group,
    db_path)`` to a list of readable entries (the index vs history entry shapes
    differ). Returns ``(entries, readable_dbs, unreadable_dbs)`` on success, or an
    ``int`` exit code (2) when discovery itself fails (no directory, nothing
    discovered, or zero readable databases) — a listing with problems is still a
    successful listing, but a listing with ZERO readable sources is a hard error,
    never a confident empty result.
    """

    db_root = args.db_root
    if not Path(db_root).is_dir():
        return _db_root_error(
            db_root,
            f"nlfr: no directory at '{db_root}' to discover per-run-group "
            "databases in — refusing to read.",
        )

    discovered = _discover_record_dbs(db_root)
    if not discovered:
        return _db_root_error(
            db_root,
            f"nlfr: no per-run-group databases found under '{db_root}' "
            "(expected <run-group>/nlfr.sqlite one level down) — refusing to read.",
        )

    entries: list[dict[str, Any]] = []
    readable_dbs = 0
    unreadable_dbs = 0
    for discovered_group, db_path in discovered:
        conn, reason = _open_or_reason(db_path)
        if conn is None:
            unreadable_dbs += 1
            assert reason is not None
            entries.append(
                {
                    "database": db_path,
                    "discovered_group": discovered_group,
                    "run_group": None,
                    "readable": False,
                    **reason,
                }
            )
            continue
        readable_dbs += 1
        try:
            entries.extend(per_db(conn, discovered_group, db_path))
        finally:
            conn.close()

    if readable_dbs == 0:
        print(
            f"nlfr: discovered {unreadable_dbs} per-run-group database(s) under "
            f"'{db_root}', but none are readable — refusing to emit a listing "
            "with zero readable sources.",
            file=sys.stderr,
        )
        for entry in entries:
            first_line = (entry.get("detail") or entry.get("reason") or "").splitlines()
            note = first_line[0] if first_line else entry.get("reason", "")
            print(
                f"  - {entry['discovered_group']} ({entry['database']}): {note}",
                file=sys.stderr,
            )
        return 2

    return entries, readable_dbs, unreadable_dbs


def export_compare(args: argparse.Namespace) -> int:
    """Export a compare projection for two run groups.

    Every side is opened read-only (never auto-created) and validated to hold at
    least one recorded run BEFORE any projection is built, so a wrong ``--db`` /
    ``--left-db`` / ``--right-db`` or an empty run group is a hard error naming
    the side, not a confident zero-value compare (GitHub #47).
    """

    if args.left_db or args.right_db:
        if not (args.left_db and args.right_db):
            print(
                "error: --left-db and --right-db must both be set",
                file=sys.stderr,
            )
            return 2
        try:
            left_conn = connect_readonly(args.left_db)
        except UnreadableDatabaseError as exc:
            print("nlfr: the left compare database could not be read.", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            return 2
        try:
            right_conn = connect_readonly(args.right_db)
        except UnreadableDatabaseError as exc:
            print("nlfr: the right compare database could not be read.", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            return 2
        try:
            require_run_group(left_conn, "left", args.left)
            require_run_group(right_conn, "right", args.right)
        except MissingRunGroupError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        left_proof = export_proof_packet(left_conn, run_group=args.left)
        right_proof = export_proof_packet(right_conn, run_group=args.right)
        left_runs = run_rows(left_conn, args.left)
        right_runs = run_rows(right_conn, args.right)
        payload = build_compare_projection(
            left_proof,
            right_proof,
            args.left,
            args.right,
            left_runs=left_runs,
            right_runs=right_runs,
        )
    else:
        try:
            conn = connect_readonly(args.db)
        except UnreadableDatabaseError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        try:
            require_run_group(conn, "left", args.left)
            require_run_group(conn, "right", args.right)
        except MissingRunGroupError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        payload = export_compare_projection(conn, args.left, args.right)
    write_or_print(payload, args.output)
    return 0


def _history_entries_for_db(
    conn: Any, discovered_group: str, db_path: str
) -> list[dict[str, Any]]:
    """Build ``compare history`` entries for one discovered, readable database."""

    projection = export_history_projection(conn)
    group_entries = projection.get("run_groups") or []
    if not group_entries:
        return [
            {
                "database": db_path,
                "discovered_group": discovered_group,
                "run_group": None,
                "readable": True,
                "empty": True,
            }
        ]
    for entry in group_entries:
        entry["database"] = db_path
        entry["discovered_group"] = discovered_group
        entry["readable"] = True
    return list(group_entries)


def _history_db_root(args: argparse.Namespace) -> int:
    """Export per-database run history across the ``nlfr record`` layout.

    Each discovered database contributes its own per-group summaries (as the
    single-``--db`` history does), tagged with the source ``database``. This is a
    LISTING, never a merge: stable run ids can collide across independent
    databases, so entries are keyed by ``(database, run_group)`` and never
    combined. Any cross-database *comparison* goes through
    ``nlfr compare export --left-db X --right-db Y`` — this command does not
    build cross-database deltas. Unreadable databases are reported with an honest
    reason and no fabricated counts; zero readable databases is a hard error.
    """

    collected = _collect_db_root_entries(args, _history_entries_for_db)
    if isinstance(collected, int):
        return collected
    entries, readable_dbs, unreadable_dbs = collected

    entries = _order_entries(entries)
    total = len(entries)
    if args.limit is not None:
        entries = entries[: args.limit]

    entries, entries_scrubbed = _scrub_entries(entries)
    db_root_display, root_scrubbed = scrub_local_paths_deep(args.db_root)

    readable_groups = [e for e in entries if e.get("readable") and e.get("run_group")]
    total_runs = sum(int(e.get("run_count") or 0) for e in readable_groups)
    evidence_refs = [f"run_group:{e['run_group']}" for e in readable_groups]
    evidence_refs.append("projection:run-history")

    summary: dict[str, Any] = {
        "run_groups": len(readable_groups),
        "total_runs": total_runs,
        "databases": readable_dbs + unreadable_dbs,
        "readable_databases": readable_dbs,
        "unreadable_databases": unreadable_dbs,
    }
    if args.limit is not None:
        summary["limit"] = args.limit
        summary["total_listed"] = total

    claims = [
        "Run history is a LISTING of per-database facts across the record "
        "layout — never a merge. Stable run ids can collide across independent "
        "databases, so entries are keyed by (database, run_group) and never "
        "combined.",
        f"Listed {len(readable_groups)} run group(s) with {total_runs} total "
        f"run(s) from {readable_dbs} readable database(s).",
        "Cross-database comparison goes through `nlfr compare export "
        "--left-db X --right-db Y`, not this listing.",
        "This projection does not claim scheduler assignment, queue time, or "
        "fleet trends.",
    ]
    if unreadable_dbs:
        claims.append(
            f"{unreadable_dbs} discovered database(s) could not be read; each "
            "carries an honest reason and no fabricated counts."
        )
    if args.limit is not None and total > args.limit:
        claims.append(
            f"Listing is limited to the newest {args.limit} of {total} entries."
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "projection_kind": "run_history",
        "generated_at": generated_at(),
        "layout": "record",
        "db_root": db_root_display,
        "retention_policy": retention_policy_summary(),
        "summary": summary,
        "claims": claims,
        "run_groups": entries,
        "source_kind": "derived_v1",
        "confidence": "medium",
        "evidence_refs": evidence_refs,
        "redaction_state": "redacted" if entries_scrubbed or root_scrubbed else "safe",
    }
    write_or_print(payload, args.output)
    return 0


def export_history(args: argparse.Namespace) -> int:
    """Export a multi-run history projection from the retention index.

    An existing-but-empty database is honest (zero run groups is a legitimate
    report); a nonexistent/empty ``--db`` is a hard error, refused read-only.
    ``--db-root`` switches to the multi-database record-layout listing.
    """

    if args.db_root:
        return _history_db_root(args)

    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = export_history_projection(conn, limit=args.limit)
    write_or_print(payload, args.output)
    return 0


def _index_entries_for_db(
    conn: Any, discovered_group: str, db_path: str
) -> list[dict[str, Any]]:
    """Build ``compare index`` entries for one discovered, readable database."""

    groups = list_run_group_index(conn)
    if not groups:
        # An existing, current-schema database with zero recorded run groups is
        # an honest empty source — reported, never dropped or fabricated.
        return [
            {
                "database": db_path,
                "discovered_group": discovered_group,
                "run_group": None,
                "readable": True,
                "run_count": 0,
                "first_started_at": None,
                "last_started_at": None,
                "empty": True,
            }
        ]
    return [
        {
            "database": db_path,
            "discovered_group": discovered_group,
            "run_group": item["run_group"],
            "run_count": item["run_count"],
            "first_started_at": item["first_started_at"],
            "last_started_at": item["last_started_at"],
            "readable": True,
        }
        for item in groups
    ]


def _index_db_root(args: argparse.Namespace) -> int:
    """List run groups across every per-run-group DB under ``--db-root``.

    Discovers databases in the ``nlfr record`` layout and reports a LISTING of
    per-database facts — never a merge (stable run ids can collide across
    independent databases, so entries are keyed by ``(database, run_group)`` and
    never combined). Unreadable databases (zero-byte / missing / old-schema)
    are reported honestly with their reason, not silently skipped; a listing with
    such problems still exits 0, but ZERO readable databases is a hard error.
    """

    collected = _collect_db_root_entries(args, _index_entries_for_db)
    if isinstance(collected, int):
        return collected
    entries, readable_dbs, unreadable_dbs = collected

    entries = _order_entries(entries)
    total = len(entries)
    if args.limit is not None:
        entries = entries[: args.limit]

    entries, entries_scrubbed = _scrub_entries(entries)
    db_root_display, root_scrubbed = scrub_local_paths_deep(args.db_root)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "run_group_index",
        "layout": "record",
        "db_root": db_root_display,
        "retention_policy": retention_policy_summary(),
        "run_groups": entries,
        "count": len(entries),
        "databases": readable_dbs + unreadable_dbs,
        "readable_databases": readable_dbs,
        "unreadable_databases": unreadable_dbs,
        "redaction_state": "redacted" if entries_scrubbed or root_scrubbed else "safe",
    }
    if args.limit is not None:
        payload["limit"] = args.limit
        payload["total"] = total

    output_format = "json" if args.json else args.format
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_db_root_index_table(entries)
    return 0


def _print_db_root_index_table(entries: list[dict[str, Any]]) -> None:
    """Print a tab-separated multi-DB index listing (discovered_group first)."""

    for item in entries:
        group = item.get("discovered_group") or "unknown"
        database = item.get("database") or "unknown"
        if not item.get("readable"):
            print(f"{group}\t(unreadable: {item.get('reason')})\t-\t-\t{database}")
        elif item.get("run_group") is None:
            print(f"{group}\t(no run groups)\t0\tunknown\t{database}")
        else:
            print(
                f"{group}\t{item['run_group']}\t{item['run_count']}\t"
                f"{item.get('last_started_at') or 'unknown'}\t{database}"
            )


def index_run_groups(args: argparse.Namespace) -> int:
    """List distinct run groups and run counts from SQLite.

    An empty listing over an EXISTING database is a legitimate, honest report and
    exits 0; only a nonexistent/empty ``--db`` is a hard error (refused read-only).
    ``--db-root`` switches to the multi-database record-layout listing.
    """

    if args.db_root:
        return _index_db_root(args)

    try:
        conn = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    groups = list_run_group_index(conn)
    total = len(groups)
    if args.limit is not None:
        groups = groups[: args.limit]
    payload = {
        "schema_version": 1,
        "kind": "run_group_index",
        "db": args.db,
        "retention_policy": retention_policy_summary(),
        "run_groups": groups,
        "count": len(groups),
    }
    if args.limit is not None:
        payload["limit"] = args.limit
        payload["total"] = total
    output_format = "json" if args.json else args.format
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not groups:
            print("no run groups recorded")
            return 0
        for item in groups:
            print(
                f"{item['run_group']}\t{item['run_count']}\t"
                f"{item.get('last_started_at') or 'unknown'}"
            )
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``compare`` subcommands on ``subparsers``."""

    parser = subparsers.add_parser(
        "compare",
        help="compare recorded run groups",
        description="Compare proof packet summaries across run groups.",
    )
    compare_subparsers = parser.add_subparsers(
        dest="compare_command",
        metavar="command",
        required=True,
    )

    export_parser = compare_subparsers.add_parser(
        "export",
        help="export compare projection JSON",
        description="Export a compare projection for two run groups.",
    )
    export_parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path when both run groups live in one DB",
    )
    export_parser.add_argument(
        "--left-db",
        help="SQLite database path for the left run group",
    )
    export_parser.add_argument(
        "--right-db",
        help="SQLite database path for the right run group",
    )
    export_parser.add_argument(
        "--left",
        required=True,
        help="left run group id",
    )
    export_parser.add_argument(
        "--right",
        required=True,
        help="right run group id",
    )
    export_parser.add_argument(
        "--output",
        help="output path for compare projection JSON",
    )
    export_parser.set_defaults(handler=export_compare)

    index_parser = compare_subparsers.add_parser(
        "index",
        help="list distinct run groups with run counts",
        description="Retention index of recorded run groups.",
    )
    index_source = index_parser.add_mutually_exclusive_group(required=True)
    index_source.add_argument(
        "--db",
        default=None,
        help="SQLite database path (single shared database)",
    )
    index_source.add_argument(
        "--db-root",
        dest="db_root",
        default=None,
        metavar="DIR",
        help=(
            "discover per-run-group databases in the `nlfr record` layout "
            "(<DIR>/<run-group>/nlfr.sqlite, one level down) and list them all"
        ),
    )
    index_parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="output format (default: table)",
    )
    index_parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of tab-separated rows (alias for --format json)",
    )
    index_parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="return at most N run groups (index-only; no purge)",
    )
    index_parser.set_defaults(handler=index_run_groups)

    history_parser = compare_subparsers.add_parser(
        "history",
        help="export multi-run history projection JSON",
        description="Export derived_v1 run history from the retention index.",
    )
    history_source = history_parser.add_mutually_exclusive_group(required=True)
    history_source.add_argument(
        "--db",
        default=None,
        help="SQLite database path (single shared database)",
    )
    history_source.add_argument(
        "--db-root",
        dest="db_root",
        default=None,
        metavar="DIR",
        help=(
            "discover per-run-group databases in the `nlfr record` layout "
            "(<DIR>/<run-group>/nlfr.sqlite, one level down) and list them all"
        ),
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="include at most N newest run groups (index-only; no purge)",
    )
    history_parser.add_argument(
        "--output",
        help="output path for run history projection JSON",
    )
    history_parser.set_defaults(handler=export_history)
