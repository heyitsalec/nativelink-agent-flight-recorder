import json
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_cache_event, upsert_invocation, upsert_proof_block, upsert_run, upsert_target
from nlfr.projectors.compare import export_compare_projection, list_run_group_index
from nlfr.projectors.proof import export_proof_packet

ROOT = Path(__file__).resolve().parents[1]


def _seed_group(
    conn,
    *,
    run_group: str,
    scenario: str,
    status: str,
    cache_hits: int,
    cache_misses: int,
    agent_provenance: bool,
    worker_identity: bool,
) -> None:
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario=scenario,
        mode="cache-only",
        status=status,
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
    if worker_identity:
        upsert_invocation(
            conn,
            stable_key=f"invocation:{run_group}:bazel",
            run_id=run_id,
            invocation_kind="bazel",
            command=[
                "bazel",
                "test",
                "//tasks:priority_test",
                "--remote_executor=grpc://127.0.0.1:50051",
            ],
            cwd=ROOT,
            exit_code=0,
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["artifact:bazel.stdout.txt"],
            redaction_state="safe",
        )
        upsert_proof_block(
            conn,
            stable_key=f"{run_group}:worker-identity",
            run_id=run_id,
            block_key="worker-admin-identity",
            block_kind="worker_admin_identity_v1",
            title="Worker Identity",
            summary="Direct worker admin stdout observed.",
            payload={
                "events": [{"worker_name": "worker-1", "source": "worker_admin_stdout_v1"}],
            },
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"worker-admin:{run_group}"],
            redaction_state="safe",
        )
    if agent_provenance:
        upsert_proof_block(
            conn,
            stable_key=f"{run_group}:agent-provenance",
            run_id=run_id,
            block_key=f"agent-provenance:{scenario}",
            block_kind="agent_provenance",
            title="Agent Provenance: compare-fixture-agent",
            summary="Bounded agent provenance recorded for compare fixture.",
            payload={
                "scenario_id": scenario,
                "agent": {
                    "name": "compare-fixture-agent",
                    "model": "composer-2.5",
                    "prompt_sha256": "a" * 64,
                },
            },
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"agent-provenance:{run_group}"],
            redaction_state="safe",
        )


def test_compare_export_reports_proof_summary_deltas(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    _seed_group(
        conn,
        run_group="left-group",
        scenario="cold-cache",
        status="completed",
        cache_hits=1,
        cache_misses=2,
        agent_provenance=False,
        worker_identity=False,
    )
    _seed_group(
        conn,
        run_group="right-group",
        scenario="warm-cache",
        status="environment_blocker",
        cache_hits=3,
        cache_misses=0,
        agent_provenance=True,
        worker_identity=True,
    )

    compare = export_compare_projection(conn, "left-group", "right-group")

    assert compare["projection_kind"] == "compare"
    assert compare["left_run_group"] == "left-group"
    assert compare["right_run_group"] == "right-group"
    assert compare["source_kind"] == "derived_v1"
    assert compare["evidence_refs"] == ["run_group:left-group", "run_group:right-group"]

    by_id = {item["id"]: item for item in compare["dimensions"]}
    assert set(by_id) == {
        "run_counts",
        "cache_metrics",
        "worker_identity",
        "agent_provenance",
        "status_deltas",
    }

    for dimension in compare["dimensions"]:
        assert dimension["source_kind"] == "derived_v1"
        assert dimension["evidence_refs"] == ["run_group:left-group", "run_group:right-group"]
        assert dimension["redaction_state"] == "safe"
        assert dimension["claims"]

    assert by_id["run_counts"]["left"]["runs"] == 1
    assert by_id["run_counts"]["right"]["runs"] == 1
    assert by_id["cache_metrics"]["delta"]["hits"] == 2
    assert by_id["cache_metrics"]["delta"]["misses"] == -2
    assert by_id["worker_identity"]["left"]["worker_identity_observed"] is False
    assert by_id["worker_identity"]["right"]["worker_identity_observed"] is True
    assert by_id["agent_provenance"]["left"]["present"] is False
    assert by_id["agent_provenance"]["right"]["present"] is True
    assert by_id["status_deltas"]["delta"]["changed"] is True
    assert by_id["status_deltas"]["delta"]["by_status"]["completed"]["left"] == 1
    assert by_id["status_deltas"]["delta"]["by_status"]["environment_blocker"]["right"] == 1


def test_compare_index_lists_run_groups_with_counts(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    _seed_group(
        conn,
        run_group="alpha",
        scenario="alpha",
        status="completed",
        cache_hits=0,
        cache_misses=0,
        agent_provenance=False,
        worker_identity=False,
    )
    _seed_group(
        conn,
        run_group="beta",
        scenario="beta",
        status="completed",
        cache_hits=0,
        cache_misses=0,
        agent_provenance=False,
        worker_identity=False,
    )

    index = list_run_group_index(conn)
    groups = {item["run_group"]: item["run_count"] for item in index}

    assert groups == {"alpha": 1, "beta": 1}


def test_compare_fixture_proof_packets_are_exportable(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    _seed_group(
        conn,
        run_group="fixture-left",
        scenario="fixture-left",
        status="completed",
        cache_hits=1,
        cache_misses=0,
        agent_provenance=False,
        worker_identity=False,
    )
    _seed_group(
        conn,
        run_group="fixture-right",
        scenario="fixture-right",
        status="completed",
        cache_hits=2,
        cache_misses=1,
        agent_provenance=True,
        worker_identity=False,
    )

    left_proof = export_proof_packet(conn, run_group="fixture-left")
    right_proof = export_proof_packet(conn, run_group="fixture-right")
    compare = export_compare_projection(conn, "fixture-left", "fixture-right")

    fixture_dir = tmp_path / "fixtures" / "compare"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "compare-projection.json").write_text(
        json.dumps(compare, indent=2, sort_keys=True) + "\n"
    )

    loaded = json.loads((fixture_dir / "compare-projection.json").read_text())
    assert loaded["projection_kind"] == "compare"
    assert len(loaded["dimensions"]) == 5
    assert left_proof["run_group"] == "fixture-left"
    assert right_proof["run_group"] == "fixture-right"
