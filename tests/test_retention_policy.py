"""Tests for v1 retention policy constants and proof packet hook."""

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run
from nlfr.projectors.proof import export_proof_packet
from nlfr.retention_policy import (
    INDEX_ONLY,
    NO_AUTO_PURGE,
    OPERATOR_MANAGED,
    proof_retention_block,
    retention_policy_summary,
)


def test_retention_policy_constants() -> None:
    assert INDEX_ONLY == "index_only"
    assert NO_AUTO_PURGE == "no_auto_purge"
    assert OPERATOR_MANAGED == "operator_managed"


def test_retention_policy_summary() -> None:
    summary = retention_policy_summary()

    assert summary == {
        "version": 1,
        "discovery": INDEX_ONLY,
        "purge": NO_AUTO_PURGE,
        "lifecycle": OPERATOR_MANAGED,
    }


def test_proof_retention_block_truth_labels() -> None:
    block = proof_retention_block()

    assert block["discovery"] == INDEX_ONLY
    assert block["purge"] == NO_AUTO_PURGE
    assert block["lifecycle"] == OPERATOR_MANAGED
    assert block["source_kind"] == "derived_v1"
    assert block["confidence"] == "high"
    assert block["redaction_state"] == "safe"
    assert block["evidence_refs"] == []
    assert len(block["claims"]) == 3
    assert "index-only" in block["claims"][0]
    assert "does not auto-purge" in block["claims"][1]
    assert "operator-managed" in block["claims"][2]


def test_proof_export_includes_retention_block(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    upsert_run(
        conn,
        stable_key="run:retention-fixture",
        run_group="retention-fixture",
        scenario="retention-fixture",
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:retention-fixture"],
        redaction_state="safe",
    )

    proof = export_proof_packet(conn, run_group="retention-fixture")

    assert "retention" in proof
    assert proof["retention"]["discovery"] == INDEX_ONLY
    assert proof["retention"]["purge"] == NO_AUTO_PURGE
    assert proof["retention"]["lifecycle"] == OPERATOR_MANAGED
    assert proof["retention"]["claims"]
