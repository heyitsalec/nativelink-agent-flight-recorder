import hashlib
import json

import pytest

from nlfr.artifacts import ArtifactExistsError, read_manifest, write_artifact
from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_artifact, upsert_run
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


def test_v1_database_upgrades_to_v2_without_losing_rows(tmp_path):
    """A populated pre-PR (v1) database upgrades cleanly to the artifact-ref v2.

    Builds a real v1 spine (core schema only, user_version=1, no
    artifact_references), populates it, then reopens under current (v2) code and
    asserts the upgrade preserves existing rows and is idempotent on a second
    reopen.
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

    # Reopen under current code: migrate() must lift v1 -> v2.
    conn = connect(db_path)
    migrate(conn)
    assert _user_version(conn) == SCHEMA_VERSION == 2
    assert "artifact_references" in table_names(conn)

    # The pre-existing row is intact and unchanged.
    row = conn.execute(
        "SELECT id, run_group, status FROM runs WHERE stable_key = ?",
        ("legacy-run:cache-only",),
    ).fetchone()
    assert row["id"] == run_id
    assert row["run_group"] == "legacy"
    assert row["status"] == "completed"

    # The widened presence CHECK accepts the new local_present value.
    with conn:
        conn.execute(
            "INSERT INTO artifact_references (id, stable_key, run_id, reference_key, presence) "
            "VALUES (?, ?, ?, ?, ?)",
            ("ar-1", "legacy-run:artifact_reference:a", run_id, "legacy:artifact:a", "local_present"),
        )
    conn.close()

    # A second reopen is idempotent: still v2, rows preserved, no error.
    conn = connect(db_path)
    initialize(conn)
    assert _user_version(conn) == 2
    assert conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) AS c FROM artifact_references").fetchone()["c"] == 1
