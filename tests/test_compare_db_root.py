"""``compare index``/``history`` over the per-run-group ``nlfr record`` layout.

``nlfr record`` writes each run group to its own database at
``data/nlfr-record/<run-group>/nlfr.sqlite``, so the single-``--db`` retention
index is blind to sibling groups (GitHub #48). ``--db-root DIR`` discovers those
per-group databases one directory level down and emits an HONEST multi-database
LISTING: a healthy database contributes its run groups; a zero-byte or
old-schema database is reported with its reason (never silently skipped, never
fabricated); and the aggregation is a listing keyed by ``(database, run_group)``
— never a merge that could collide stable run ids across independent databases.

These tests build a record-layout tree with three groups (healthy, zero-byte,
old-schema v1) and assert the listing is honest, exits 0 when at least one
database is readable, and exits 2 for the mutual-exclusion, empty-discovery, and
zero-readable failure modes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run, upsert_target
from nlfr.db.schema import MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]


def run_nlfr(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=str(cwd or ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _seed_healthy_group(
    db_path: Path, run_group: str, *, status: str = "completed", started_at: str
) -> None:
    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario="record",
        mode="record",
        status=status,
        started_at=started_at,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    upsert_target(
        conn,
        stable_key=f"target:{run_group}",
        run_id=run_id,
        label="//tasks:priority_test",
        target_kind="py_test",
        status="passed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    conn.commit()
    conn.close()


def _seed_v1_db(db_path: Path) -> None:
    """Build a genuine schema-v1 database (one version behind this build)."""

    v1 = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1.sql)
        conn.execute("PRAGMA user_version = 1")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()


def _build_record_tree(root: Path) -> Path:
    """Create a ``data/nlfr-record``-style tree: healthy + zero-byte + old v1.

    Also drops a non-matching directory (no ``nlfr.sqlite``) that discovery must
    ignore. Returns the ``nlfr-record`` root to pass as ``--db-root``.
    """

    record_root = root / "nlfr-record"
    record_root.mkdir(parents=True, exist_ok=True)

    (record_root / "healthy").mkdir()
    _seed_healthy_group(
        record_root / "healthy" / "nlfr.sqlite",
        "healthy",
        started_at="2026-07-06T00:00:00.000000Z",
    )

    (record_root / "zerobyte").mkdir()
    (record_root / "zerobyte" / "nlfr.sqlite").write_bytes(b"")

    (record_root / "oldschema").mkdir()
    _seed_v1_db(record_root / "oldschema" / "nlfr.sqlite")

    # A directory with no nlfr.sqlite — discovery must ignore it entirely.
    (record_root / "notadb").mkdir()
    (record_root / "notadb" / "readme.txt").write_text("ignore me\n")

    return record_root


# --------------------------------------------------------------------------- #
# index --db-root                                                             #
# --------------------------------------------------------------------------- #


def test_index_db_root_lists_healthy_plus_honest_unreadable(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "index", "--db-root", str(record_root), "--json")

    assert result.returncode == 0, result.stderr  # a listing with problems is a listing
    payload = json.loads(result.stdout)
    assert payload["kind"] == "run_group_index"
    assert payload["layout"] == "record"
    assert payload["databases"] == 3  # notadb ignored
    assert payload["readable_databases"] == 1
    assert payload["unreadable_databases"] == 2

    by_group = {e["discovered_group"]: e for e in payload["run_groups"]}
    assert set(by_group) == {"healthy", "zerobyte", "oldschema"}

    healthy = by_group["healthy"]
    assert healthy["readable"] is True
    assert healthy["run_group"] == "healthy"
    assert healthy["run_count"] == 1

    zero = by_group["zerobyte"]
    assert zero["readable"] is False
    assert zero["reason"] == "empty"
    assert zero["run_group"] is None
    assert "run_count" not in zero  # no fabricated counts for an unreadable source

    old = by_group["oldschema"]
    assert old["readable"] is False
    assert old["reason"] == "schema_v1"
    assert old["found_schema_version"] == 1
    assert "nlfr db upgrade" in old["detail"]  # honest upgrade guidance, not fatal


def test_index_db_root_ignores_non_matching_dirs(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "index", "--db-root", str(record_root), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    groups = {e["discovered_group"] for e in payload["run_groups"]}
    assert "notadb" not in groups


def test_index_db_root_scrubs_absolute_database_paths(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "index", "--db-root", str(record_root), "--json")

    assert result.returncode == 0, result.stderr
    # The absolute tmp_path must never survive into the shared JSON projection.
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["redaction_state"] == "redacted"  # honest: scrubbing happened
    for entry in payload["run_groups"]:
        assert "[REDACTED:abs_path]" in entry["database"]
    assert "[REDACTED:abs_path]" in payload["db_root"]


def test_index_db_root_keyed_by_database_and_run_group_no_merge(tmp_path: Path) -> None:
    # Two healthy groups in two independent databases stay two distinct entries;
    # nothing is merged across databases (stable run ids could collide).
    record_root = tmp_path / "nlfr-record"
    (record_root / "baseline").mkdir(parents=True)
    _seed_healthy_group(
        record_root / "baseline" / "nlfr.sqlite",
        "baseline",
        started_at="2026-07-06T00:00:00.000000Z",
    )
    (record_root / "candidate").mkdir()
    _seed_healthy_group(
        record_root / "candidate" / "nlfr.sqlite",
        "candidate",
        started_at="2026-07-07T00:00:00.000000Z",
    )

    result = run_nlfr("compare", "index", "--db-root", str(record_root), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["count"] == 2
    keys = {(e["discovered_group"], e["run_group"]) for e in payload["run_groups"]}
    assert keys == {("baseline", "baseline"), ("candidate", "candidate")}
    # Newest-first ordering over the listing (candidate started later).
    assert payload["run_groups"][0]["discovered_group"] == "candidate"


def test_index_db_root_limit_truncates_listing(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr(
        "compare", "index", "--db-root", str(record_root), "--json", "--limit", "1"
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["count"] == 1
    assert payload["limit"] == 1
    assert payload["total"] == 3
    # Readable group sorts first, so the single kept entry is the healthy one.
    assert payload["run_groups"][0]["discovered_group"] == "healthy"


def test_index_db_root_table_output(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "index", "--db-root", str(record_root))

    assert result.returncode == 0, result.stderr
    assert str(tmp_path) not in result.stdout
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert len(lines) == 3
    assert all("\t" in line for line in lines)
    assert any("unreadable" in line for line in lines)


# --------------------------------------------------------------------------- #
# history --db-root                                                           #
# --------------------------------------------------------------------------- #


def test_history_db_root_lists_per_database_summaries(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "history", "--db-root", str(record_root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["projection_kind"] == "run_history"
    assert payload["layout"] == "record"
    assert payload["source_kind"] == "derived_v1"
    assert payload["summary"]["run_groups"] == 1
    assert payload["summary"]["total_runs"] == 1
    assert payload["summary"]["readable_databases"] == 1
    assert payload["summary"]["unreadable_databases"] == 2

    by_group = {e["discovered_group"]: e for e in payload["run_groups"]}
    assert set(by_group) == {"healthy", "zerobyte", "oldschema"}

    healthy = by_group["healthy"]
    assert healthy["readable"] is True
    assert healthy["run_group"] == "healthy"
    assert "database" in healthy
    assert "proof_summary" in healthy

    old = by_group["oldschema"]
    assert old["readable"] is False
    assert old["reason"] == "schema_v1"
    assert "proof_summary" not in old  # no fabricated summary for an unreadable source


def test_history_db_root_points_cross_db_compare_at_export(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "history", "--db-root", str(record_root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    joined = " ".join(payload["claims"])
    assert "compare export" in joined
    assert "--left-db" in joined
    assert "(database, run_group)" in joined  # listing, not merge


def test_history_db_root_scrubs_absolute_paths(tmp_path: Path) -> None:
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr("compare", "history", "--db-root", str(record_root))

    assert result.returncode == 0, result.stderr
    assert str(tmp_path) not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["redaction_state"] == "redacted"


# --------------------------------------------------------------------------- #
# mutual exclusion + hard-error modes (exit 2)                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("command", ["index", "history"])
def test_db_and_db_root_together_exit_2(tmp_path: Path, command: str) -> None:
    record_root = _build_record_tree(tmp_path)
    db = record_root / "healthy" / "nlfr.sqlite"

    result = run_nlfr(
        "compare", command, "--db", str(db), "--db-root", str(record_root)
    )

    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr


@pytest.mark.parametrize("command", ["index", "history"])
def test_neither_db_nor_db_root_exit_2(command: str) -> None:
    result = run_nlfr("compare", command)

    assert result.returncode == 2
    assert "one of the arguments --db --db-root is required" in result.stderr


@pytest.mark.parametrize("command", ["index", "history"])
def test_db_root_nonexistent_directory_exit_2(tmp_path: Path, command: str) -> None:
    result = run_nlfr("compare", command, "--db-root", str(tmp_path / "nope"))

    assert result.returncode == 2
    assert "no directory at" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("command", ["index", "history"])
def test_db_root_no_databases_discovered_exit_2(tmp_path: Path, command: str) -> None:
    empty_root = tmp_path / "nlfr-record"
    (empty_root / "notadb").mkdir(parents=True)  # a dir but no nlfr.sqlite

    result = run_nlfr("compare", command, "--db-root", str(empty_root))

    assert result.returncode == 2
    assert "no per-run-group databases found" in result.stderr


@pytest.mark.parametrize("command", ["index", "history"])
def test_db_root_zero_readable_databases_exit_2(tmp_path: Path, command: str) -> None:
    record_root = tmp_path / "nlfr-record"
    (record_root / "a").mkdir(parents=True)
    (record_root / "a" / "nlfr.sqlite").write_bytes(b"")
    (record_root / "b").mkdir()
    _seed_v1_db(record_root / "b" / "nlfr.sqlite")

    result = run_nlfr("compare", command, "--db-root", str(record_root))

    assert result.returncode == 2
    assert "none are readable" in result.stderr
    # The honest reasons are still surfaced (never a silent skip).
    assert "empty (0 bytes)" in result.stderr
    assert "schema v1" in result.stderr
    assert "Traceback" not in result.stderr


# --------------------------------------------------------------------------- #
# single --db behavior is byte-identical (regression guard)                    #
# --------------------------------------------------------------------------- #


def test_single_db_index_unchanged(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed_healthy_group(db, "solo", started_at="2026-07-06T00:00:00.000000Z")

    result = run_nlfr("compare", "index", "--db", str(db), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    # The single-DB shape is preserved: `db` (raw path), no `db_root`/`layout`.
    assert payload["db"] == str(db)
    assert "db_root" not in payload
    assert payload["count"] == 1
    assert payload["run_groups"][0]["run_group"] == "solo"


def test_db_root_relative_path_is_not_scrubbed(tmp_path: Path) -> None:
    # A relative --db-root (resolved against cwd) carries no absolute prefix, so
    # the redaction helper is a no-op and the listing stays labeled `safe`.
    record_root = _build_record_tree(tmp_path)

    result = run_nlfr(
        "compare", "index", "--db-root", "nlfr-record", "--json", cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["db_root"] == "nlfr-record"
    assert payload["redaction_state"] == "safe"
    healthy = next(e for e in payload["run_groups"] if e["discovered_group"] == "healthy")
    assert healthy["database"] == "nlfr-record/healthy/nlfr.sqlite"


# --------------------------------------------------------------------------- #
# Symlinks: never followed, never silent (PR #72 review repros)
# --------------------------------------------------------------------------- #


def test_symlinked_group_alias_is_reported_not_double_counted(tmp_path: Path) -> None:
    """A same-tree symlink alias must not duplicate evidence in the listing.

    Review repro: db_root/healthy_alias -> db_root/healthy previously listed as
    an independent third database, double-counting the same physical rows.
    """

    db_root = tmp_path / "nlfr-record"
    _seed_healthy_group(db_root / "healthy" / "nlfr.sqlite", "healthy", started_at="2026-07-01T00:00:00Z")
    (db_root / "healthy_alias").symlink_to(db_root / "healthy")

    result = run_nlfr("compare", "index", "--db-root", str(db_root), "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    entries = payload["run_groups"]

    aliases = [e for e in entries if e.get("discovered_group") == "healthy_alias"]
    assert len(aliases) == 1
    assert aliases[0]["readable"] is False
    assert aliases[0]["reason"] == "symlinked_entry"
    assert "--db" in aliases[0]["detail"]
    # The real group is counted exactly once; the alias contributes no rows.
    readable = [e for e in entries if e.get("readable")]
    assert len(readable) == 1
    assert payload["readable_databases"] == 1
    assert payload["unreadable_databases"] == 1


def test_symlink_escaping_db_root_is_reported_not_read(tmp_path: Path) -> None:
    """A link pointing outside db_root must never pull outside evidence in.

    Review repro: db_root/escaped -> /outside tree with its own nlfr.sqlite
    previously flowed the outside database's rows into the listing.
    """

    outside = tmp_path / "outside-evidence"
    _seed_healthy_group(outside / "nlfr.sqlite", "outside-group", started_at="2026-07-02T00:00:00Z")
    db_root = tmp_path / "nlfr-record"
    _seed_healthy_group(db_root / "healthy" / "nlfr.sqlite", "healthy", started_at="2026-07-01T00:00:00Z")
    (db_root / "escaped").symlink_to(outside)

    result = run_nlfr("compare", "index", "--db-root", str(db_root), "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    entries = payload["run_groups"]

    assert not any(e.get("run_group") == "outside-group" for e in entries)
    escaped = [e for e in entries if e.get("discovered_group") == "escaped"]
    assert len(escaped) == 1
    assert escaped[0]["readable"] is False
    assert escaped[0]["reason"] == "symlinked_entry"


def test_stray_symlink_without_db_is_ignored_like_any_non_group(tmp_path: Path) -> None:
    """A 'latest'-style symlink to a dir WITHOUT nlfr.sqlite adds no noise."""

    db_root = tmp_path / "nlfr-record"
    _seed_healthy_group(db_root / "healthy" / "nlfr.sqlite", "healthy", started_at="2026-07-01T00:00:00Z")
    plain = tmp_path / "not-a-group"
    plain.mkdir()
    (db_root / "latest").symlink_to(plain)

    result = run_nlfr("compare", "index", "--db-root", str(db_root), "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert not any(
        e.get("discovered_group") == "latest" for e in payload["run_groups"]
    )
    assert payload["unreadable_databases"] == 0
