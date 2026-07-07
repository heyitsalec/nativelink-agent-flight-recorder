import hashlib
import json
import sqlite3

import pytest

from nlfr.artifacts import ArtifactExistsError, read_manifest, write_artifact
from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_artifact, upsert_artifact_reference, upsert_run
from nlfr.db.schema import CORE_TABLES, MIGRATIONS, SCHEMA_VERSION, migrate


def table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def column_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_initialize_creates_core_tables_with_truth_labels(tmp_path):
    conn = connect(tmp_path / "nlfr.sqlite")

    initialize(conn)

    assert set(CORE_TABLES) <= table_names(conn)
    for table in CORE_TABLES:
        assert {"source_kind", "confidence", "evidence_refs", "redaction_state"} <= (
            column_names(conn, table)
        )

    artifact_columns = column_names(conn, "artifacts")
    assert {
        "sha256",
        "producer_command",
        "config_hash",
        "redaction_state",
    } <= artifact_columns


def test_ingest_helpers_are_idempotent_by_stable_key(tmp_path):
    conn = connect(tmp_path / "nlfr.sqlite")
    initialize(conn)

    run_id = upsert_run(
        conn,
        stable_key="scenario:tri-agent-loop:cache-only",
        run_group="latest",
        scenario="tri-agent-loop",
        mode="cache-only",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["manifest:run"],
        redaction_state="safe",
    )
    duplicate_run_id = upsert_run(
        conn,
        stable_key="scenario:tri-agent-loop:cache-only",
        run_group="latest",
        scenario="tri-agent-loop",
        mode="cache-only",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["manifest:run"],
        redaction_state="safe",
    )

    assert duplicate_run_id == run_id
    assert conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"] == 1

    artifact_id = upsert_artifact(
        conn,
        stable_key="artifact:stdout",
        run_id=run_id,
        artifact_key="stdout",
        artifact_path="artifacts/stdout.txt",
        manifest_path="artifact_manifest.json",
        sha256="a" * 64,
        size_bytes=12,
        producer_command=["nlfr", "run", "--mode", "cache-only"],
        config_hash="cfg-cache-only",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:tri-agent-loop"],
        redaction_state="safe",
    )
    duplicate_artifact_id = upsert_artifact(
        conn,
        stable_key="artifact:stdout",
        run_id=run_id,
        artifact_key="stdout",
        artifact_path="artifacts/stdout.txt",
        manifest_path="artifact_manifest.json",
        sha256="a" * 64,
        size_bytes=12,
        producer_command=["nlfr", "run", "--mode", "cache-only"],
        config_hash="cfg-cache-only",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:tri-agent-loop"],
        redaction_state="safe",
    )

    assert duplicate_artifact_id == artifact_id
    row = conn.execute("SELECT * FROM artifacts").fetchone()
    assert row["producer_command"] == json.dumps(
        ["nlfr", "run", "--mode", "cache-only"], separators=(",", ":")
    )
    assert row["evidence_refs"] == json.dumps(
        ["run:tri-agent-loop"], separators=(",", ":")
    )
    assert conn.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"] == 1


def test_write_artifact_records_manifest_and_refuses_overwrite(tmp_path):
    artifact_root = tmp_path / "artifacts"
    payload = b"first stdout payload\n"

    entry = write_artifact(
        artifact_root,
        artifact_key="logs/stdout.txt",
        data=payload,
        producer_command=["nlfr", "run", "--mode", "cache-only"],
        config_hash="cfg-cache-only",
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["invocation:run"],
    )

    assert entry.sha256 == hashlib.sha256(payload).hexdigest()
    assert (artifact_root / "logs" / "stdout.txt").read_bytes() == payload

    manifest = read_manifest(artifact_root)
    assert manifest["schema_version"] == 1
    assert manifest["artifacts"] == [
        {
            "artifact_key": "logs/stdout.txt",
            "path": "logs/stdout.txt",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "producer_command": ["nlfr", "run", "--mode", "cache-only"],
            "config_hash": "cfg-cache-only",
            "redaction_state": "safe",
            "source_kind": "collectable_v1",
            "confidence": "high",
            "evidence_refs": ["invocation:run"],
        }
    ]

    same_entry = write_artifact(
        artifact_root,
        artifact_key="logs/stdout.txt",
        data=payload,
        producer_command=["nlfr", "run", "--mode", "cache-only"],
        config_hash="cfg-cache-only",
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["invocation:run"],
    )
    assert same_entry == entry

    with pytest.raises(ArtifactExistsError):
        write_artifact(
            artifact_root,
            artifact_key="logs/stdout.txt",
            data=b"mutated stdout payload\n",
            producer_command=["nlfr", "run", "--mode", "cache-only"],
            config_hash="cfg-cache-only",
            redaction_state="safe",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["invocation:run"],
        )

    assert (artifact_root / "logs" / "stdout.txt").read_bytes() == payload
    assert read_manifest(artifact_root) == manifest


def _user_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


# The artifact_references table as commit 4406a0a first shipped it in schema
# version 2 — reproducing the NARROW presence CHECK that predates v3's
# 'local_present'. Embedded here (not fetched from git) so the regression is
# reproducible from the test alone. NOTE: only the presence/digest_verified
# CHECK clauses under test are reproduced faithfully; 4406a0a's unrelated
# source_kind/confidence/redaction_state CHECK clauses are deliberately elided —
# they play no role in this regression.
OLD_NARROW_V2_ARTIFACT_REFERENCES = """
CREATE TABLE IF NOT EXISTS artifact_references (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    target_id TEXT REFERENCES targets(id) ON DELETE SET NULL,
    reference_key TEXT NOT NULL,
    name TEXT,
    uri TEXT,
    local_path TEXT,
    declared_digest TEXT,
    declared_size_bytes INTEGER,
    computed_digest TEXT,
    digest_verified INTEGER CHECK (digest_verified IS NULL OR digest_verified IN (0, 1)),
    presence TEXT CHECK (presence IS NULL OR presence IN
        ('local_verified','local_mismatch','missing','unverified_remote_reference')),
    verification_note TEXT,
    source_kind TEXT,
    confidence TEXT NOT NULL DEFAULT 'unknown',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    redaction_state TEXT NOT NULL DEFAULT 'unknown',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(run_id, reference_key)
);
CREATE INDEX IF NOT EXISTS idx_artifact_references_run_id ON artifact_references(run_id);
"""


def test_v1_database_upgrades_to_latest_without_losing_rows(tmp_path):
    """A populated pre-PR (v1) database upgrades cleanly to the latest schema.

    Builds a real v1 spine (core schema only, user_version=1, no
    artifact_references), populates it, then reopens under current code and asserts
    the upgrade preserves existing rows, accepts the widened presence vocabulary,
    and is idempotent on a second reopen.
    """

    db_path = tmp_path / "nlfr.sqlite"

    # Build a genuine v1 database: apply only the first migration (the pre-PR core
    # schema) and stamp user_version=1, exactly as pre-PR code left it.
    v1_migration = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1_migration.sql)
        conn.execute("PRAGMA user_version = 1")
    assert _user_version(conn) == 1
    assert "artifact_references" not in table_names(conn)

    # Populate the v1 database with a run row that must survive the migration.
    run_id = upsert_run(
        conn,
        stable_key="legacy-run:cache-only",
        run_group="legacy",
        scenario="legacy-run",
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:legacy"],
        redaction_state="safe",
    )
    conn.close()

    # Reopen under current code: migrate() must lift v1 -> latest.
    conn = connect(db_path)
    migrate(conn)
    assert _user_version(conn) == SCHEMA_VERSION
    assert "artifact_references" in table_names(conn)

    # The pre-existing row is intact and unchanged.
    row = conn.execute(
        "SELECT id, run_group, status FROM runs WHERE stable_key = ?",
        ("legacy-run:cache-only",),
    ).fetchone()
    assert row["id"] == run_id
    assert row["run_group"] == "legacy"
    assert row["status"] == "completed"

    # The widened presence CHECK accepts the local_present value.
    with conn:
        conn.execute(
            "INSERT INTO artifact_references (id, stable_key, run_id, reference_key, presence) "
            "VALUES (?, ?, ?, ?, ?)",
            ("ar-1", "legacy-run:artifact_reference:a", run_id, "legacy:artifact:a", "local_present"),
        )
    conn.close()

    # A second reopen is idempotent: still latest, rows preserved, no error.
    conn = connect(db_path)
    initialize(conn)
    assert _user_version(conn) == SCHEMA_VERSION
    assert conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) AS c FROM artifact_references").fetchone()["c"] == 1


def test_old_narrow_v2_database_migrates_to_v3_and_accepts_local_present(tmp_path):
    """Regression: a DB stamped v2 under the OLD narrow presence CHECK upgrades to v3.

    An early feat/artifact-verify checkout (commit 4406a0a) shipped
    ``artifact_references`` with a narrow presence CHECK that lacked
    ``local_present``. A prior fix widened that CHECK by EDITING the version-2
    migration SQL in place — but ``migrate()`` skips any migration whose version a
    DB already has and ``CREATE TABLE IF NOT EXISTS`` is a no-op, so a DB already
    stamped v2 kept the narrow CHECK forever and ``upsert`` of a ``local_present``
    row raised ``RuntimeError``. This test constructs exactly that stuck DB (via raw
    SQL, no git dependency) and proves the version-3 rebuild migration widens the
    CHECK on an existing database while preserving its rows and staying idempotent.
    """

    db_path = tmp_path / "nlfr.sqlite"

    # Build a genuine OLD-narrow v2 database: real v1 core schema + the verbatim
    # narrow-CHECK artifact_references, stamped user_version=2.
    v1_migration = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1_migration.sql)
        conn.executescript(OLD_NARROW_V2_ARTIFACT_REFERENCES)
        conn.execute("PRAGMA user_version = 2")
    assert _user_version(conn) == 2

    # Seed a run and an artifact_reference row that must survive the rebuild.
    run_id = upsert_run(
        conn,
        stable_key="legacy-run:narrow-v2",
        run_group="legacy",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:legacy"],
        redaction_state="safe",
    )
    with conn:
        conn.execute(
            "INSERT INTO artifact_references (id, stable_key, run_id, reference_key, name, presence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("ar-narrow", "legacy:artifact_reference:a", run_id, "legacy:artifact:a", "a.txt", "missing"),
        )

    # Prove the OLD narrow CHECK is really in force: local_present is rejected today.
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute(
                "INSERT INTO artifact_references (id, stable_key, run_id, reference_key, presence) "
                "VALUES (?, ?, ?, ?, ?)",
                ("ar-reject", "legacy:artifact_reference:reject", run_id, "legacy:artifact:reject", "local_present"),
            )
    conn.close()

    # Reopen under current code: migrate() must lift the stuck v2 DB to v3.
    conn = connect(db_path)
    migrate(conn)
    assert _user_version(conn) == SCHEMA_VERSION == 3

    # Existing rows are intact after the table rebuild.
    row = conn.execute(
        "SELECT run_id, name, presence FROM artifact_references WHERE id = ?",
        ("ar-narrow",),
    ).fetchone()
    assert row["run_id"] == run_id
    assert row["name"] == "a.txt"
    assert row["presence"] == "missing"
    assert conn.execute("SELECT COUNT(*) AS c FROM artifact_references").fetchone()["c"] == 1
    # Foreign keys survive the drop/rename and the run FK still resolves.
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    # The interim rebuild table was cleaned up.
    assert "artifact_references_v3_rebuild" not in table_names(conn)

    # The widened CHECK now accepts a local_present upsert that previously raised.
    ref_id = upsert_artifact_reference(
        conn,
        stable_key="legacy:artifact_reference:present",
        run_id=run_id,
        reference_key="legacy:artifact:present",
        presence="local_present",
        source_kind="collectable_v1",
        confidence="medium",
        evidence_refs=["ref:present"],
        redaction_state="safe",
    )
    assert conn.execute(
        "SELECT presence FROM artifact_references WHERE id = ?", (ref_id,)
    ).fetchone()["presence"] == "local_present"
    conn.close()

    # A second reopen is idempotent: still v3, rows preserved, no rebuild churn.
    conn = connect(db_path)
    initialize(conn)
    assert _user_version(conn) == SCHEMA_VERSION == 3
    assert conn.execute("SELECT COUNT(*) AS c FROM artifact_references").fetchone()["c"] == 2
    assert "artifact_references_v3_rebuild" not in table_names(conn)


def test_migration_scripts_are_wrapped_in_single_transactions():
    """Every migration runs as one explicit transaction, version stamp included.

    ``executescript()`` is NOT atomic across statements; without the wrap, an
    interruption mid-way through the v3 table rebuild (after ``DROP TABLE
    artifact_references``, before the rename) loses the table permanently and
    the replay destroys the copied rows in the temp table.
    """

    from nlfr.db.schema import atomic_migration_script

    for migration in MIGRATIONS:
        script = atomic_migration_script(migration)
        assert script.lstrip().startswith("BEGIN IMMEDIATE;")
        assert script.rstrip().endswith("COMMIT;")
        assert f"PRAGMA user_version = {migration.version};" in script


def test_v3_rebuild_is_atomic_under_mid_script_failure(tmp_path):
    """Fault injection: a failure after the destructive DROP rolls back fully.

    Emulates an interruption late in the v3 rebuild by injecting a failing
    statement just before COMMIT. All-or-nothing means the original table, its
    rows, and the version stamp must all be untouched — and the real migration
    must still complete cleanly afterwards.
    """

    from nlfr.db.schema import atomic_migration_script

    db_path = tmp_path / "nlfr.sqlite"
    v1_migration = next(m for m in MIGRATIONS if m.version == 1)
    conn = connect(db_path)
    with conn:
        conn.executescript(v1_migration.sql)
        conn.executescript(OLD_NARROW_V2_ARTIFACT_REFERENCES)
        conn.execute("PRAGMA user_version = 2")
    run_id = upsert_run(
        conn,
        stable_key="legacy-run:atomicity",
        run_group="legacy",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:legacy"],
        redaction_state="safe",
    )
    with conn:
        conn.execute(
            "INSERT INTO artifact_references (id, stable_key, run_id, reference_key, name, presence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("ar-atomic", "legacy:artifact_reference:atomic", run_id, "legacy:artifact:atomic", "a.txt", "missing"),
        )

    v3_migration = next(m for m in MIGRATIONS if m.version == 3)
    script = atomic_migration_script(v3_migration)
    broken = script.replace("COMMIT;", "INSERT INTO nlfr_no_such_table VALUES (1);\nCOMMIT;")
    assert broken != script
    with pytest.raises(sqlite3.OperationalError):
        conn.executescript(broken)
    conn.rollback()

    # All-or-nothing: the canonical table, its row, and the stamp are untouched.
    assert "artifact_references" in table_names(conn)
    assert conn.execute("SELECT COUNT(*) AS c FROM artifact_references").fetchone()["c"] == 1
    assert _user_version(conn) == 2

    # The real migration still lifts the DB cleanly after the failed attempt.
    migrate(conn)
    assert _user_version(conn) == SCHEMA_VERSION == 3
    assert conn.execute("SELECT COUNT(*) AS c FROM artifact_references").fetchone()["c"] == 1


def test_copy_column_list_matches_live_table_schema(tmp_path):
    """The hand-maintained v3 copy-column list cannot drift from the real DDL."""

    from nlfr.db.schema import _ARTIFACT_REFERENCE_COPY_COLUMNS

    conn = connect(tmp_path / "nlfr.sqlite")
    initialize(conn)
    live = [row["name"] for row in conn.execute("PRAGMA table_info(artifact_references)")]
    copy_columns = [column.strip() for column in _ARTIFACT_REFERENCE_COPY_COLUMNS.split(",")]
    assert copy_columns == live


def test_v3_replay_after_lost_stamp_is_lossless(tmp_path):
    """Replaying the v3 rebuild on an already-widened table loses nothing.

    Defensive: with the stamp inside the migration transaction this state
    should be unreachable, but a replay must still be harmless.
    """

    db_path = tmp_path / "nlfr.sqlite"
    conn = connect(db_path)
    initialize(conn)
    run_id = upsert_run(
        conn,
        stable_key="replay-run",
        run_group="replay",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:replay"],
        redaction_state="safe",
    )
    upsert_artifact_reference(
        conn,
        stable_key="replay:artifact_reference:present",
        run_id=run_id,
        reference_key="replay:artifact:present",
        presence="local_present",
        source_kind="collectable_v1",
        confidence="medium",
        evidence_refs=["ref:present"],
        redaction_state="safe",
    )
    conn.execute("PRAGMA user_version = 2")
    conn.close()

    conn = connect(db_path)
    initialize(conn)
    assert _user_version(conn) == SCHEMA_VERSION == 3
    row = conn.execute(
        "SELECT presence FROM artifact_references WHERE stable_key = ?",
        ("replay:artifact_reference:present",),
    ).fetchone()
    assert row["presence"] == "local_present"
