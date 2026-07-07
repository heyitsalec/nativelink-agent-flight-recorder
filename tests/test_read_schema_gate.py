"""Readers refuse a schema-mismatched DB honestly; `nlfr db upgrade` is the consent.

On ``main`` a read command that opened an OLD database silently migrated it —
a hidden WRITE to recorded evidence, and a genuinely old (schema-v1) database
that lacked the ``artifact_references`` table instead CRASHED proof/in-toto/
compare export with an uncaught ``no such table`` traceback and exit 1.

This branch removes read-time migration entirely, so a schema mismatch is now a
clean, actionable exit 2 (never a traceback):

* found < supported: name the found vs supported version and point the operator
  at ``nlfr db upgrade --db PATH`` — an EXPLICIT, operator-consented migration,
  not a side effect of reading.
* found > supported: a DB written by a newer nlfr is refused too (this build
  cannot safely read it), mirroring ``migrate()``'s "newer than supported" guard
  as a clean exit 2 rather than a ``RuntimeError`` traceback.

The gate is applied UNIFORMLY: every reader (graph/runway/proof/in-toto/compare
index/history/export) requires the current schema, so the behavior is one
predictable rule and the remedy is one command.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.db import SCHEMA_VERSION, connect
from nlfr.db.ingest import upsert_artifact, upsert_run
from nlfr.db.schema import MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]


def run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _build_v1_db(db_path: Path, run_group: str = "legacy") -> str:
    """Build a genuine schema-v1 database (the review's exact repro).

    Applies ONLY the first migration (the pre-``artifact_references`` core schema)
    and stamps ``user_version=1``, exactly as pre-PR code left an old database,
    then records a real run + artifact so a reader has real data to (fail to)
    project. Returns the run id.
    """

    v1 = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1.sql)
        conn.execute("PRAGMA user_version = 1")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "artifact_references" not in tables  # the missing table that crashed reads
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario=run_group,
        mode="cache-only",
        status="completed",
        started_at="2026-07-06T00:00:00.000000Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    upsert_artifact(
        conn,
        stable_key=f"run:{run_group}:artifact:a",
        run_id=run_id,
        artifact_key="out/a.txt",
        artifact_path="out/a.txt",
        sha256="a" * 64,
        size_bytes=12,
        producer_command="bazel build //a",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:a"],
        redaction_state="safe",
    )
    conn.commit()
    conn.close()
    return run_id


def _build_future_db(db_path: Path) -> None:
    """Build a current-schema DB then stamp a version NEWER than this build reads."""

    from nlfr.db import initialize

    conn = initialize(connect(db_path))
    with conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()


# Every reader that must refuse a schema-mismatched DB, keyed by argv. The gate is
# uniform: readers that never touch v2+ tables (graph/runway/index/history) are
# gated too, so "which readers need a current schema" has one answer: all of them.
READER_COMMANDS: dict[str, list[str]] = {
    "graph-export": ["graph", "export", "--run-group", "legacy"],
    "runway-export": ["runway", "export", "--run-group", "legacy"],
    "proof-export-json": ["proof", "export", "--run-group", "legacy"],
    "proof-export-in-toto": [
        "proof",
        "export",
        "--run-group",
        "legacy",
        "--format",
        "in-toto",
    ],
    "compare-index": ["compare", "index"],
    "compare-history": ["compare", "history"],
    "compare-export": ["compare", "export", "--left", "legacy", "--right", "legacy"],
}


@pytest.mark.parametrize("argv", list(READER_COMMANDS.values()), ids=list(READER_COMMANDS))
def test_v1_db_read_exits_2_with_upgrade_guidance(tmp_path: Path, argv: list[str]) -> None:
    """A genuine v1 DB fails EVERY reader with exit 2 + upgrade guidance, no traceback."""

    db = tmp_path / "nlfr.sqlite"
    _build_v1_db(db)

    result = run_nlfr(*argv, "--db", str(db))

    assert result.returncode == 2, result.stdout + result.stderr
    assert "is schema v1" in result.stderr
    assert f"schema v{SCHEMA_VERSION}" in result.stderr
    assert "refusing to read" in result.stderr
    assert "never migrates a database on open" in result.stderr
    assert f"nlfr db upgrade --db {db}" in result.stderr
    assert "Traceback" not in result.stderr
    # The reader did NOT migrate the evidence as a side effect of reading it.
    assert _user_version(db) == 1


@pytest.mark.parametrize("argv", list(READER_COMMANDS.values()), ids=list(READER_COMMANDS))
def test_future_version_db_read_exits_2_no_traceback(tmp_path: Path, argv: list[str]) -> None:
    """A DB NEWER than this build is refused with a clean exit 2, not a traceback."""

    db = tmp_path / "nlfr.sqlite"
    _build_future_db(db)

    result = run_nlfr(*argv, "--db", str(db))

    assert result.returncode == 2, result.stdout + result.stderr
    assert f"is schema v{SCHEMA_VERSION + 1}" in result.stderr
    assert "newer than" in result.stderr
    assert "Traceback" not in result.stderr


def _user_version(db_path: Path) -> int:
    conn = connect(db_path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def test_db_upgrade_migrates_v1_to_current_preserving_rows(tmp_path: Path) -> None:
    """`nlfr db upgrade` lifts a v1 DB to current schema, reports vN->vM, keeps rows."""

    db = tmp_path / "nlfr.sqlite"
    _build_v1_db(db)
    assert _user_version(db) == 1

    result = run_nlfr("db", "upgrade", "--db", str(db))

    assert result.returncode == 0, result.stderr
    assert "from schema v1 to v3" in result.stdout
    assert _user_version(db) == SCHEMA_VERSION

    conn = connect(db)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "artifact_references" in tables  # the v2 table now present
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 1
    finally:
        conn.close()


def test_db_upgrade_is_idempotent(tmp_path: Path) -> None:
    """Upgrading an already-current DB is a no-op that reports so and exits 0."""

    db = tmp_path / "nlfr.sqlite"
    _build_v1_db(db)
    first = run_nlfr("db", "upgrade", "--db", str(db))
    assert first.returncode == 0, first.stderr

    second = run_nlfr("db", "upgrade", "--db", str(db))
    assert second.returncode == 0, second.stderr
    assert "already at schema v3" in second.stdout
    assert _user_version(db) == SCHEMA_VERSION


def test_proof_export_succeeds_after_upgrade(tmp_path: Path) -> None:
    """The same reader that hard-errored on the v1 DB succeeds once it is upgraded."""

    db = tmp_path / "nlfr.sqlite"
    _build_v1_db(db)

    before = run_nlfr("proof", "export", "--db", str(db), "--run-group", "legacy")
    assert before.returncode == 2  # refused pre-upgrade

    upgrade = run_nlfr("db", "upgrade", "--db", str(db))
    assert upgrade.returncode == 0, upgrade.stderr

    after = run_nlfr("proof", "export", "--db", str(db), "--run-group", "legacy")
    assert after.returncode == 0, after.stderr
    import json

    payload = json.loads(after.stdout)
    assert payload["summary"]["runs"] == 1
    assert payload["summary"]["artifacts"] == 1


def test_compare_export_v1_db_refuses_before_projection(tmp_path: Path) -> None:
    """C1 repro: compare export against a v1 DB is exit 2 guidance, not a crash."""

    db = tmp_path / "nlfr.sqlite"
    _build_v1_db(db)

    result = run_nlfr(
        "compare", "export", "--db", str(db), "--left", "legacy", "--right", "legacy"
    )

    assert result.returncode == 2, result.stdout + result.stderr
    assert "nlfr db upgrade --db" in result.stderr
    assert "Traceback" not in result.stderr


def test_db_upgrade_refuses_nonexistent_path_creates_nothing(tmp_path: Path) -> None:
    """`nlfr db upgrade` upgrades an EXISTING DB; a typo must not fabricate one."""

    missing = tmp_path / "typo" / "nested" / "nlfr.sqlite"

    result = run_nlfr("db", "upgrade", "--db", str(missing))

    assert result.returncode == 2, result.stdout + result.stderr
    assert "refusing to create one" in result.stderr
    assert "never creates one" in result.stderr
    assert not missing.exists()
    assert not missing.parent.exists()


def test_db_upgrade_refuses_future_version_db(tmp_path: Path) -> None:
    """A DB newer than this build cannot be downgraded; upgrade refuses cleanly."""

    db = tmp_path / "nlfr.sqlite"
    _build_future_db(db)

    result = run_nlfr("db", "upgrade", "--db", str(db))

    assert result.returncode == 2, result.stdout + result.stderr
    assert "refusing to downgrade" in result.stderr
    assert "Traceback" not in result.stderr
    assert _user_version(db) == SCHEMA_VERSION + 1  # untouched
