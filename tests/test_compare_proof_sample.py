import json
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_cache_event, upsert_proof_block, upsert_run, upsert_target
from nlfr.projectors.compare import export_compare_projection

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_SAMPLE = ROOT / "docs" / "proof-samples" / "compare-summary.json"
PROJECTION_SAMPLE = ROOT / "docs" / "proof-samples" / "compare-projection-sample.json"

EXPECTED_DIMENSION_IDS = {
    "run_counts",
    "cache_metrics",
    "worker_identity",
    "agent_provenance",
    "status_deltas",
}


def _seed_compare_fixture_db(db_path: Path, *, run_group: str, cache_hits: int, cache_misses: int, agent: bool) -> None:
    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario=run_group,
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    target_id = upsert_target(
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
    for index in range(cache_hits):
        upsert_cache_event(
            conn,
            stable_key=f"cache:{run_group}:hit:{index}",
            run_id=run_id,
            target_id=target_id,
            event_key=f"hit-{index}",
            event_kind="action_cache",
            hit=True,
            source_kind="derived_v1",
            confidence="medium",
            evidence_refs=[f"execution-log:{run_group}"],
            redaction_state="safe",
        )
    for index in range(cache_misses):
        upsert_cache_event(
            conn,
            stable_key=f"cache:{run_group}:miss:{index}",
            run_id=run_id,
            target_id=target_id,
            event_key=f"miss-{index}",
            event_kind="action_cache",
            hit=False,
            source_kind="derived_v1",
            confidence="medium",
            evidence_refs=[f"execution-log:{run_group}"],
            redaction_state="safe",
        )
    if agent:
        upsert_proof_block(
            conn,
            stable_key=f"{run_group}:agent-provenance",
            run_id=run_id,
            block_key=f"agent-provenance:{run_group}",
            block_kind="agent_provenance",
            title="Agent Provenance: canvas-dev-agent",
            summary="Bounded agent provenance recorded for compare proof.",
            payload={
                "scenario_id": run_group,
                "agent": {
                    "name": "canvas-dev-agent",
                    "model": "composer-2.5",
                    "prompt_sha256": "b" * 64,
                },
            },
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"agent-provenance:{run_group}"],
            redaction_state="safe",
        )


def test_compare_summary_sample_shape() -> None:
    sample = json.loads(SUMMARY_SAMPLE.read_text(encoding="utf-8"))

    for key in (
        "status",
        "left_run_group",
        "right_run_group",
        "left_db",
        "right_db",
        "compare_projection",
        "dimension_ids",
        "summary",
        "source_kind",
        "confidence",
        "redaction_state",
        "evidence_refs",
    ):
        assert key in sample

    assert sample["status"] == "ok"
    assert sample["source_kind"] == "derived_v1"
    assert sample["confidence"] == "medium"
    assert sample["redaction_state"] == "safe"
    assert set(sample["dimension_ids"]) == EXPECTED_DIMENSION_IDS
    assert sample["left_run_group"] == "record-proof"
    assert sample["right_run_group"] == "canvas-dev"
    assert sample["evidence_refs"] == [
        "run_group:record-proof",
        "run_group:canvas-dev",
    ]
    assert sample["summary"]["dimensions"] == 5
    assert "<repo>" in sample["left_db"]
    assert "<repo>" in sample["right_db"]
    assert "<repo>" in sample["compare_projection"]
    assert "/Users/" not in json.dumps(sample)


def test_compare_projection_sample_shape() -> None:
    sample = json.loads(PROJECTION_SAMPLE.read_text(encoding="utf-8"))

    assert sample["projection_kind"] == "compare"
    assert sample["schema_version"] == 1
    assert sample["source_kind"] == "derived_v1"
    assert sample["left_run_group"] == "record-proof"
    assert sample["right_run_group"] == "canvas-dev"
    assert set(item["id"] for item in sample["dimensions"]) == EXPECTED_DIMENSION_IDS

    for dimension in sample["dimensions"]:
        assert dimension["source_kind"] == "derived_v1"
        assert dimension["redaction_state"] == "safe"
        assert dimension["evidence_refs"] == [
            "run_group:record-proof",
            "run_group:canvas-dev",
        ]
        assert dimension["claims"]

    assert sample["summary"] == {
        "dimensions": 5,
        "left_artifacts": 0,
        "left_runs": 1,
        "right_artifacts": 0,
        "right_runs": 1,
    }


def test_compare_proof_sample_matches_fixture_export(tmp_path) -> None:
    db_path = tmp_path / "nlfr.sqlite"
    _seed_compare_fixture_db(db_path, run_group="record-proof", cache_hits=1, cache_misses=0, agent=False)
    _seed_compare_fixture_db(db_path, run_group="canvas-dev", cache_hits=2, cache_misses=1, agent=True)

    conn = connect(db_path)
    compare = export_compare_projection(conn, "record-proof", "canvas-dev")

    summary_sample = json.loads(SUMMARY_SAMPLE.read_text(encoding="utf-8"))
    projection_sample = json.loads(PROJECTION_SAMPLE.read_text(encoding="utf-8"))

    assert set(item["id"] for item in compare["dimensions"]) == EXPECTED_DIMENSION_IDS
    assert compare["summary"] == summary_sample["summary"]
    assert compare["left_run_group"] == summary_sample["left_run_group"]
    assert compare["right_run_group"] == summary_sample["right_run_group"]

    by_id = {item["id"]: item for item in compare["dimensions"]}
    sample_by_id = {item["id"]: item for item in projection_sample["dimensions"]}

    assert by_id["run_counts"]["delta"] == sample_by_id["run_counts"]["delta"]
    assert by_id["cache_metrics"]["delta"] == sample_by_id["cache_metrics"]["delta"]
    assert by_id["worker_identity"]["left"]["worker_identity_observed"] is False
    assert by_id["agent_provenance"]["right"]["present"] is True
    assert by_id["status_deltas"]["delta"]["changed"] is False
