"""Database maintenance commands.

Two subcommands, both WRITER-side and both explicit, operator-consented acts on
recorded evidence:

* ``nlfr db upgrade`` — the writer-side counterpart to the reader schema gate in
  :func:`nlfr.db.connection.connect_readonly`. Readers no longer migrate a
  database on open — that hidden write to recorded evidence is gone. Migrating an
  old database is therefore an explicit, operator-consented act rather than a
  silent side effect of exporting a projection, and this command is how the
  operator consents.

* ``nlfr db gc`` — operator-consented retention. ``retention_policy.py`` documents
  "no auto-purge, operator-managed"; this command is the *managed* mechanism.
  Deleting recorded evidence is the marked action: a bare invocation is a DRY RUN
  that only prints the plan, and real deletion requires an explicit ``--apply``.
  The unit of deletion is always a whole RUN GROUP (never individual rows), so an
  ``ON DELETE CASCADE`` from ``runs`` can never orphan referenced child rows, and
  on-disk artifact trees are removed only when they live inside the evidence root.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from nlfr.db import CORE_TABLES, SCHEMA_VERSION, connect, database_defect, migrate

# Child tables that cascade from ``runs`` (everything in the core schema except
# ``runs`` itself). Deleting a ``runs`` row removes these via ON DELETE CASCADE;
# they are enumerated here only to COUNT what a deletion (would) remove, per table.
_CHILD_TABLES = tuple(table for table in CORE_TABLES if table != "runs")

_RUNS_DIRNAME = "runs"
_RUN_METADATA_FILENAME = "run.json"
_GC_REPORT_FILENAME = "gc-report.json"


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

    try:
        conn = connect(args.db)
    except sqlite3.OperationalError as exc:
        # Upgrading writes; an unwritable directory must be a clean refusal,
        # not a traceback (the evidence stays untouched either way).
        print(
            f"nlfr: cannot upgrade the database at '{args.db}': {exc}.\n"
            "The database (or its directory) is not writable — restore write "
            "permission, or copy the file somewhere writable and upgrade the copy.",
            file=sys.stderr,
        )
        return 2
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


# --------------------------------------------------------------------------- gc


def _gc_refuse_path_message(database: str, defect: str) -> str:
    """Render the writer-appropriate refusal for a ``db gc`` path that is not a DB.

    Mirrors :func:`_refuse_path_message` (and the reader-side
    :class:`~nlfr.db.connection.DatabaseNotFoundError`) so all three apply one
    definition of "a real, existing NLFR database". ``db gc`` never CREATES a
    database — collecting evidence from a nonexistent store is an error, not a
    reason to fabricate an empty one (the same silent-empty trap GitHub #47
    closed for readers).
    """

    if defect == "empty":
        headline = (
            f"nlfr: the file at '{database}' is empty (0 bytes), not an NLFR "
            "database — refusing to garbage-collect."
        )
    elif defect == "not_a_database":
        headline = (
            f"nlfr: the file at '{database}' is not a SQLite database — refusing "
            "to garbage-collect."
        )
    else:
        headline = (
            f"nlfr: no database at '{database}' to garbage-collect — refusing to "
            "create one."
        )
    return "\n".join(
        [
            headline,
            "`nlfr db gc` deletes run groups from an EXISTING database in place; "
            "it never creates one, so a path typo cannot fabricate an empty store.",
            "Point --db at an existing database, or record one first "
            "(e.g. `nlfr record -- bazel test //...`).",
        ]
    )


def _schema_gate_message(database: str, found: int) -> str:
    """Refusal for a ``db gc`` against a DB whose schema this build cannot mutate.

    ``db gc`` mutates recorded evidence, so it must never run against a schema it
    does not fully understand. Guidance mirrors the reader gate
    (:class:`~nlfr.db.connection.SchemaVersionError`): an older DB is pointed at
    ``nlfr db upgrade`` first; a newer DB tells the operator to upgrade nlfr.
    """

    if found < SCHEMA_VERSION:
        return "\n".join(
            [
                f"nlfr: the database at '{database}' is schema v{found}, older than "
                f"the schema v{SCHEMA_VERSION} this nlfr supports — refusing to "
                "garbage-collect.",
                "Deleting evidence under a stale schema could mis-handle rows the "
                "current code does not model; upgrade it first (idempotent, "
                "row-preserving):",
                f"  nlfr db upgrade --db {database}",
                "then re-run `nlfr db gc`.",
            ]
        )
    return "\n".join(
        [
            f"nlfr: the database at '{database}' is schema v{found}, newer than the "
            f"schema v{SCHEMA_VERSION} this nlfr supports — refusing to "
            "garbage-collect.",
            "It was written by a newer nlfr; this build cannot safely mutate it. "
            "Upgrade nlfr instead, then re-run.",
        ]
    )


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse a recorded ISO-8601 UTC timestamp, or ``None`` if absent/unparseable.

    Recorded timestamps use a trailing ``Z``; normalize it to ``+00:00`` before
    :func:`datetime.fromisoformat`. An unparseable value returns ``None`` so its
    group is treated as "age unknown" and never deleted by ``--keep-days``.
    """

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_group_index(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Group the ``runs`` table into run-group records, newest-first.

    Each record carries the group's run ids, run count, and first/last
    ``started_at``. Ordering matches the retention index used elsewhere: newest
    ``last_started_at`` first, ties broken by run-group name ascending. Groups
    with no parseable timestamp sort LAST but are NOT treated as "oldest" for
    deletion — the selectors route them to a separate unknown-age bucket that is
    never auto-selected (see :func:`_select_groups`). A ``NULL`` run_group is a
    legitimate group keyed by ``None``.
    """

    rows = conn.execute("SELECT id, run_group, started_at FROM runs").fetchall()
    buckets: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = row["run_group"]
        bucket = buckets.setdefault(key, {"run_ids": [], "started_ats": []})
        bucket["run_ids"].append(row["id"])
        if row["started_at"] is not None:
            bucket["started_ats"].append(row["started_at"])

    groups: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        started = sorted(bucket["started_ats"])
        groups.append(
            {
                "run_group": key,
                "run_ids": bucket["run_ids"],
                "run_count": len(bucket["run_ids"]),
                "first_started_at": started[0] if started else None,
                "last_started_at": started[-1] if started else None,
            }
        )

    # Stable two-pass sort: name ascending (tiebreak), then last_started_at
    # descending with untimestamped groups last.
    groups.sort(key=lambda g: (g["run_group"] is None, str(g["run_group"] or "")))
    groups.sort(
        key=lambda g: (g["last_started_at"] is not None, g["last_started_at"] or ""),
        reverse=True,
    )
    return groups


def _group_label(run_group: Any) -> str:
    """Human label for a run group (``NULL`` renders as ``(unnamed)``)."""

    return str(run_group) if run_group is not None else "(unnamed)"


def _within(root: Path, path: Path) -> bool:
    """True when ``path`` resolves to ``root`` itself or a descendant of it."""

    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _abs_escape(path_value: Any, evidence_root: Path) -> Optional[str]:
    """Return a reason string when an ABSOLUTE recorded path escapes ``evidence_root``.

    Relative paths are always safe: they resolve inside a run's artifact_root
    (itself inside the evidence root) and gc deletes whole run directories, never
    a raw relative path. Only an absolute recorded path can point outside the
    evidence tree — and NLFR never deletes anything outside it.
    """

    if not path_value:
        return None
    candidate = Path(str(path_value))
    if not candidate.is_absolute():
        return None
    if _within(evidence_root, candidate):
        return None
    return (
        f"references evidence at '{path_value}', which is OUTSIDE the evidence "
        f"root {evidence_root}"
    )


def _discover_run_dirs(evidence_root: Path) -> dict[Any, list[tuple[Path, dict[str, Any]]]]:
    """Map each run group to its on-disk run directories under ``<root>/runs``.

    A run directory is attributed to a group by reading its
    ``artifacts/run.json`` (written by ``nlfr record``/``nlfr run``), which
    records the run_group and the run's own artifact_root. Directories with no
    parseable ``run.json`` are left unattributed and are never deleted — gc only
    removes trees it can positively tie to a group being collected.
    """

    result: dict[Any, list[tuple[Path, dict[str, Any]]]] = {}
    runs_root = evidence_root / _RUNS_DIRNAME
    if not runs_root.is_dir():
        return result
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir():
            continue
        metadata_path = child / "artifacts" / _RUN_METADATA_FILENAME
        if not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(metadata, dict):
            continue
        result.setdefault(metadata.get("run_group"), []).append((child, metadata))
    return result


def _dir_stats(run_dir: Path) -> tuple[int, int]:
    """Return ``(file_count, total_bytes)`` for every file under ``run_dir``."""

    files = 0
    total = 0
    for path in run_dir.rglob("*"):
        if path.is_file():
            files += 1
            total += path.stat().st_size
    return files, total


def _count_rows(conn: sqlite3.Connection, run_ids: list[str]) -> dict[str, int]:
    """Count rows a group's deletion (would) remove, per table (``runs`` + children)."""

    counts: dict[str, int] = {"runs": len(run_ids)}
    if not run_ids:
        return counts
    placeholders = ", ".join("?" for _ in run_ids)
    for table in _CHILD_TABLES:
        count = conn.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE run_id IN ({placeholders})",
            run_ids,
        ).fetchone()["c"]
        if count:
            counts[table] = count
    return counts


def _group_escape_reason(
    conn: sqlite3.Connection,
    group: dict[str, Any],
    evidence_root: Path,
    run_dirs: list[tuple[Path, dict[str, Any]]],
) -> Optional[str]:
    """Return why a group cannot be safely collected, or ``None`` if it is safe.

    Two escape sources, both refusing the WHOLE group (partial deletion is
    worse): (1) a DB artifact row whose absolute ``artifact_path``/``manifest_path``
    points outside the evidence root, and (2) an on-disk ``run.json`` whose
    recorded ``artifact_root`` points outside it. Either means deleting the group
    honestly would require touching evidence outside the tree NLFR owns — so gc
    refuses and reports instead.
    """

    run_ids = group["run_ids"]
    if run_ids:
        placeholders = ", ".join("?" for _ in run_ids)
        rows = conn.execute(
            f"SELECT artifact_path, manifest_path FROM artifacts "
            f"WHERE run_id IN ({placeholders})",
            run_ids,
        ).fetchall()
        for row in rows:
            for column in ("artifact_path", "manifest_path"):
                reason = _abs_escape(row[column], evidence_root)
                if reason is not None:
                    return f"an artifact row {reason}"
    for run_dir, metadata in run_dirs:
        reason = _abs_escape(metadata.get("artifact_root"), evidence_root)
        if reason is not None:
            return f"the run directory {run_dir.name}/ {reason}"
        if not _within(evidence_root, run_dir):
            return (
                f"the run directory {run_dir} is OUTSIDE the evidence root "
                f"{evidence_root}"
            )
    return None


def _build_deleted_entry(
    conn: sqlite3.Connection,
    group: dict[str, Any],
    run_dirs: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    """Assemble the per-group report entry: identity, rows, on-disk files/bytes.

    Records only NON-resurrectable metadata (group name, run ids, time range,
    per-table row counts, file/byte totals, run-dir paths) so the durable
    ``gc-report.json`` documents the deletion without preserving its content.
    """

    total_files = 0
    total_bytes = 0
    dir_paths: list[str] = []
    for run_dir, _metadata in run_dirs:
        files, size = _dir_stats(run_dir)
        total_files += files
        total_bytes += size
        dir_paths.append(str(run_dir))
    return {
        "run_group": group["run_group"],
        "run_count": group["run_count"],
        "run_ids": list(group["run_ids"]),
        "first_started_at": group["first_started_at"],
        "last_started_at": group["last_started_at"],
        "rows_by_table": _count_rows(conn, group["run_ids"]),
        "run_dirs": dir_paths,
        "files": total_files,
        "bytes": total_bytes,
    }


def _validate_selection(args: argparse.Namespace) -> Optional[str]:
    """Return a usage-error string if the selection flags are invalid, else ``None``.

    Exactly one selection mode is required. ``--keep-last`` needs N >= 1 (keeping
    zero groups is spelled ``--run-group`` / ``--keep-days``, not ``--keep-last``);
    ``--keep-days`` needs D >= 0.
    """

    modes = []
    if args.keep_last is not None:
        modes.append("--keep-last")
    if args.keep_days is not None:
        modes.append("--keep-days")
    if args.run_group:
        modes.append("--run-group")

    if len(modes) == 0:
        return (
            "nlfr db gc: choose exactly one selection mode: --keep-last N, "
            "--keep-days D, or --run-group G (repeatable)."
        )
    if len(modes) > 1:
        return (
            "nlfr db gc: selection modes are mutually exclusive; got "
            f"{', '.join(modes)}. Use exactly one of --keep-last / --keep-days / "
            "--run-group per invocation."
        )
    if args.keep_last is not None and args.keep_last < 1:
        return "nlfr db gc: --keep-last must be >= 1 (it keeps the N newest groups)."
    if args.keep_days is not None and args.keep_days < 0:
        return "nlfr db gc: --keep-days must be >= 0."
    return None


def _select_groups(
    args: argparse.Namespace, groups: list[dict[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    Optional[str],
    Optional[str],
]:
    """Split ``groups`` into (keep, delete, unknown) for the chosen selection mode.

    Returns ``(keep, delete, unknown, usage_error, nothing_reason)``. ``unknown``
    holds groups whose age cannot be known (no parseable ``started_at`` on any
    run). The retention doctrine is that UNKNOWN AGE IS NEVER AUTO-SELECTABLE FOR
    DELETION: the recency modes (``--keep-last`` / ``--keep-days``) rank only
    groups with a known timestamp and route the rest to ``unknown`` — never to
    ``delete``, and never silently folded into ``keep`` either. Deleting an
    age-unknown group is possible only by naming it explicitly with
    ``--run-group``. ``usage_error`` is a hard exit-2 message (e.g. ``--run-group``
    names an absent group); ``nothing_reason`` explains an empty delete set (a
    clean exit-0 no-op).
    """

    if args.keep_last is not None:
        # Rank ONLY age-known groups (already newest-first from _load_group_index);
        # age-unknown groups are excluded from both keep and delete and reported.
        rankable = [g for g in groups if g["last_started_at"] is not None]
        unknown = [g for g in groups if g["last_started_at"] is None]
        keep = rankable[: args.keep_last]
        delete = rankable[args.keep_last :]
        reason = None
        if not delete:
            reason = (
                f"--keep-last {args.keep_last} keeps all {len(rankable)} "
                "age-known run group(s)"
            )
        return keep, delete, unknown, None, reason

    if args.keep_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=args.keep_days)
        keep, delete, unknown = [], [], []
        for group in groups:
            started = _parse_timestamp(group["last_started_at"])
            if started is None:
                # Age unknown: cannot be judged old enough to delete — never
                # auto-selected, reported separately (not silently "kept").
                unknown.append(group)
            elif started < cutoff:
                delete.append(group)
            else:
                keep.append(group)
        reason = None
        if not delete:
            reason = f"no run group's newest run is older than {args.keep_days} day(s)"
        return keep, delete, unknown, None, reason

    # --run-group (repeatable): delete exactly the named groups. Explicit naming
    # is a deliberate operator act, so an age-unknown group named here IS deletable
    # (the unknown-age doctrine only guards *auto*-selection, not explicit intent).
    names = list(dict.fromkeys(args.run_group))  # de-dupe, preserve order
    by_name = {g["run_group"]: g for g in groups}
    missing = [name for name in names if name not in by_name]
    if missing:
        available = ", ".join(_group_label(g["run_group"]) for g in groups) or "(none)"
        usage = (
            "nlfr db gc: no run group named "
            + ", ".join(f"'{name}'" for name in missing)
            + f" in this database. Present run groups: {available}. "
            "List them any time with `nlfr compare index --db <db>`."
        )
        return groups, [], [], usage, None
    delete = [by_name[name] for name in names]
    delete_keys = {g["run_group"] for g in delete}
    keep = [g for g in groups if g["run_group"] not in delete_keys]
    return keep, delete, [], None, None


def _selection_descriptor(args: argparse.Namespace) -> dict[str, Any]:
    """Machine-readable description of the chosen selection mode for the report."""

    if args.keep_last is not None:
        return {"mode": "keep_last", "keep_last": args.keep_last}
    if args.keep_days is not None:
        return {"mode": "keep_days", "keep_days": args.keep_days}
    return {"mode": "run_group", "run_groups": list(dict.fromkeys(args.run_group))}


def _selection_summary(args: argparse.Namespace) -> str:
    """One-line human description of the selection for the summary header."""

    if args.keep_last is not None:
        return f"keep-last {args.keep_last}"
    if args.keep_days is not None:
        return f"keep-days {args.keep_days}"
    names = ", ".join(_group_label(name) for name in dict.fromkeys(args.run_group))
    return f"run-group {names}"


def _emit(report: dict[str, Any], as_json: bool) -> None:
    """Print the gc report as JSON or a human-readable summary."""

    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    applied = report["applied"]
    header = (
        "APPLIED — deleted evidence is gone."
        if applied
        else "DRY RUN — no evidence deleted (re-run with --apply to delete)."
    )
    print(f"nlfr db gc: {header}")
    print(f"selection:  {report['selection_summary']}")
    print(f"database:   {report['db']}")
    print(f"evidence:   {report['evidence_root']}")

    totals = report["totals"]
    verb = "deleted" if applied else "would delete"
    deleted = report["deleted_groups"]
    if deleted:
        print(
            f"\n{verb} {totals['groups']} run group(s), {totals['runs']} run(s), "
            f"{totals['rows']} row(s), {totals['files']} file(s), "
            f"{totals['bytes']} byte(s):"
        )
        for entry in deleted:
            rows = ", ".join(
                f"{table}={count}" for table, count in sorted(entry["rows_by_table"].items())
            )
            span = _format_span(entry["first_started_at"], entry["last_started_at"])
            print(
                f"  - {_group_label(entry['run_group'])} "
                f"({entry['run_count']} run(s), {span}) "
                f"rows: {rows}; files: {entry['files']} ({entry['bytes']} B)"
            )
    else:
        print(f"\nnothing to delete: {report.get('nothing_reason') or 'no matching run groups'}")

    kept = report["kept_groups"]
    keep_verb = "kept" if applied else "would keep"
    print(f"\n{keep_verb} {len(kept)} run group(s):")
    for entry in kept:
        span = _format_span(None, entry["last_started_at"])
        print(f"  - {_group_label(entry['run_group'])} ({entry['run_count']} run(s), {span})")

    unknown = report.get("unknown_age_groups") or []
    if unknown:
        print(
            f"\n{len(unknown)} group(s) with unknown age — not auto-selected; "
            "delete explicitly with --run-group:"
        )
        for entry in unknown:
            print(
                f"  - {_group_label(entry['run_group'])} "
                f"({entry['run_count']} run(s), no timestamp)"
            )

    vacuum = report.get("vacuum")
    if applied and vacuum and vacuum.get("ran"):
        print(
            f"\nreclaimed {vacuum['reclaimed_bytes']} byte(s) "
            f"(db {vacuum['db_bytes_before']} -> {vacuum['db_bytes_after']} after VACUUM)."
        )
    if applied and report.get("gc_report_path"):
        print(f"gc report:  {report['gc_report_path']}")


def _format_span(first: Optional[str], last: Optional[str]) -> str:
    if first and last and first != last:
        return f"{first} .. {last}"
    stamp = last or first
    return f"last {stamp}" if stamp else "no timestamp"


def db_gc(args: argparse.Namespace) -> int:
    """Delete whole run groups' evidence with operator consent (dry-run by default).

    Selection is one of ``--keep-last N`` / ``--keep-days D`` / ``--run-group G``
    (repeatable). A bare invocation is a DRY RUN that prints the plan and deletes
    nothing; ``--apply`` performs the deletion, VACUUMs to reclaim space, and
    writes a durable ``gc-report.json`` next to the database. Refuses to empty the
    store (delete the last group) without ``--allow-empty``, and refuses any group
    that references evidence outside the evidence root.
    """

    usage = _validate_selection(args)
    if usage is not None:
        print(usage, file=sys.stderr)
        return 2

    # Never CREATE a database: collecting a nonexistent store is an error.
    defect = database_defect(args.db)
    if defect is not None:
        print(_gc_refuse_path_message(str(args.db), defect), file=sys.stderr)
        return 2

    try:
        conn = connect(args.db)
    except sqlite3.OperationalError as exc:
        print(
            f"nlfr: cannot garbage-collect the database at '{args.db}': {exc}.\n"
            "The database (or its directory) is not writable — restore write "
            "permission before running `nlfr db gc`.",
            file=sys.stderr,
        )
        return 2

    evidence_root = Path(str(args.db)).resolve().parent
    db_path = Path(str(args.db)).resolve()
    try:
        found_version = conn.execute("PRAGMA user_version").fetchone()[0]
        if found_version != SCHEMA_VERSION:
            print(_schema_gate_message(str(args.db), found_version), file=sys.stderr)
            return 2

        groups = _load_group_index(conn)
        discovered = _discover_run_dirs(evidence_root)
        keep, delete, unknown, selection_error, nothing_reason = _select_groups(
            args, groups
        )

        if selection_error is not None:
            print(selection_error, file=sys.stderr)
            return 2

        # Refuse any group that would require touching evidence outside the root.
        for group in delete:
            reason = _group_escape_reason(
                conn, group, evidence_root, discovered.get(group["run_group"], [])
            )
            if reason is not None:
                print(
                    f"nlfr db gc: refusing to collect run group "
                    f"'{_group_label(group['run_group'])}' — {reason}.\n"
                    "Refusing the whole group (partial deletion is worse). Nothing "
                    "was deleted. Move or detach the out-of-tree evidence, then "
                    "re-run.",
                    file=sys.stderr,
                )
                return 2

        # Refuse to empty the store (delete the last remaining group) unless the
        # operator explicitly opts in — an empty evidence DB is a foot-gun.
        # Age-unknown groups are never deleted, so they still populate the store:
        # only refuse when NOTHING (neither kept nor unknown) would remain.
        if delete and not keep and not unknown and not args.allow_empty:
            print(
                "nlfr db gc: this would delete the LAST remaining run group and "
                "leave an empty evidence database — refusing.\n"
                "If you really mean to empty the store, re-run with --allow-empty.",
                file=sys.stderr,
            )
            return 2

        db_bytes_before = db_path.stat().st_size
        deleted_entries = [
            _build_deleted_entry(conn, group, discovered.get(group["run_group"], []))
            for group in delete
        ]

        vacuum_info: Optional[dict[str, Any]] = None
        gc_report_path: Optional[str] = None

        if args.apply and delete:
            delete_run_ids = [rid for group in delete for rid in group["run_ids"]]
            placeholders = ", ".join("?" for _ in delete_run_ids)
            with conn:
                conn.execute(
                    f"DELETE FROM runs WHERE id IN ({placeholders})", delete_run_ids
                )
            # Remove the on-disk run trees (only those inside the evidence root).
            for group in delete:
                for run_dir, _metadata in discovered.get(group["run_group"], []):
                    if _within(evidence_root, run_dir):
                        shutil.rmtree(run_dir, ignore_errors=True)
            # Reclaim space: checkpoint the WAL, then VACUUM (both need autocommit).
            conn.isolation_level = None
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
            db_bytes_after = db_path.stat().st_size
            vacuum_info = {
                "ran": True,
                "db_bytes_before": db_bytes_before,
                "db_bytes_after": db_bytes_after,
                "reclaimed_bytes": max(0, db_bytes_before - db_bytes_after),
            }
    finally:
        conn.close()

    report = _build_report(
        args=args,
        db=str(args.db),
        evidence_root=str(evidence_root),
        deleted_entries=deleted_entries,
        kept_groups=keep,
        unknown_groups=unknown,
        nothing_reason=nothing_reason,
        vacuum_info=vacuum_info,
    )

    if args.apply and delete:
        gc_report_path = str(evidence_root / _GC_REPORT_FILENAME)
        report["gc_report_path"] = gc_report_path
        _write_gc_report(evidence_root, report)

    _emit(report, args.json)
    return 0


def _build_report(
    *,
    args: argparse.Namespace,
    db: str,
    evidence_root: str,
    deleted_entries: list[dict[str, Any]],
    kept_groups: list[dict[str, Any]],
    unknown_groups: list[dict[str, Any]],
    nothing_reason: Optional[str],
    vacuum_info: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the truth-labeled gc report (``derived_v1``) used for all outputs."""

    total_rows = sum(sum(entry["rows_by_table"].values()) for entry in deleted_entries)
    total_runs = sum(entry["run_count"] for entry in deleted_entries)
    total_files = sum(entry["files"] for entry in deleted_entries)
    total_bytes = sum(entry["bytes"] for entry in deleted_entries)
    applied = bool(args.apply) and bool(deleted_entries)

    kept = [
        {
            "run_group": group["run_group"],
            "run_count": group["run_count"],
            "last_started_at": group["last_started_at"],
        }
        for group in kept_groups
    ]
    unknown = [
        {
            "run_group": group["run_group"],
            "run_count": group["run_count"],
            "last_started_at": group["last_started_at"],
        }
        for group in unknown_groups
    ]
    evidence_refs = [
        f"run_group:{_group_label(entry['run_group'])}" for entry in deleted_entries
    ]
    evidence_refs.append("command:nlfr-db-gc")

    return {
        "schema_version": 1,
        "report_kind": "gc",
        "generated_at": datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "db": db,
        "evidence_root": evidence_root,
        "mode": "apply" if applied else "dry_run",
        "applied": applied,
        "allow_empty": bool(args.allow_empty),
        "selection": _selection_descriptor(args),
        "selection_summary": _selection_summary(args),
        "nothing_reason": nothing_reason,
        "deleted_groups": deleted_entries,
        "kept_groups": kept,
        "unknown_age_groups": unknown,
        "totals": {
            "groups": len(deleted_entries),
            "runs": total_runs,
            "rows": total_rows,
            "files": total_files,
            "bytes": total_bytes,
        },
        "vacuum": vacuum_info,
        "source_kind": "derived_v1",
        "confidence": "high",
        "evidence_refs": evidence_refs,
        "redaction_state": "safe",
    }


def _write_gc_report(evidence_root: Path, event: dict[str, Any]) -> None:
    """Append a gc event to the durable ``gc-report.json`` next to the database.

    Deleting evidence must leave a durable record. The file is an append-only
    array of gc events so a later gc never erases the record of an earlier one; a
    malformed/foreign file is replaced rather than trusted.
    """

    path = evidence_root / _GC_REPORT_FILENAME
    document: dict[str, Any] = {"schema_version": 1, "report_kind": "gc", "gc_events": []}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = None
        if isinstance(existing, dict) and isinstance(existing.get("gc_events"), list):
            document = existing
    document["gc_events"].append(event)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temp_path, path)


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

    gc_parser = db_subparsers.add_parser(
        "gc",
        help="delete old run groups' evidence (operator-consented retention)",
        description=(
            "Delete whole run groups' recorded evidence — rows AND on-disk artifact "
            "trees — with operator consent. A bare invocation is a DRY RUN that only "
            "prints the plan; deletion requires --apply. The unit is always a whole "
            "run group, so cascade deletes never orphan referenced evidence, and "
            "nothing outside the evidence root is ever touched."
        ),
    )
    gc_parser.add_argument(
        "--db",
        default="data/nlfr/nlfr.sqlite",
        help="SQLite database path to garbage-collect",
    )
    gc_parser.add_argument(
        "--keep-last",
        type=int,
        metavar="N",
        help="keep the N most-recent run groups (by latest run), delete older ones",
    )
    gc_parser.add_argument(
        "--keep-days",
        type=int,
        metavar="D",
        help="delete run groups whose newest run is older than D days",
    )
    gc_parser.add_argument(
        "--run-group",
        action="append",
        metavar="G",
        help="delete this run group (repeatable); mutually exclusive with --keep-*",
    )
    gc_parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete (default: dry run — print the plan and delete nothing)",
    )
    gc_parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="permit deleting the last remaining run group (leaving an empty store)",
    )
    gc_parser.add_argument(
        "--json",
        action="store_true",
        help="emit the gc report as JSON instead of the human-readable summary",
    )
    gc_parser.set_defaults(handler=db_gc)
