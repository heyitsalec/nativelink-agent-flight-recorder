import hashlib
import json

import pytest

from nlfr.artifacts import ArtifactExistsError, read_manifest, write_artifact
from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_artifact, upsert_run
from nlfr.db.schema import CORE_TABLES


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
