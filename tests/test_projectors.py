import json
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_action,
    upsert_artifact,
    upsert_cache_event,
    upsert_failure,
    upsert_invocation,
    upsert_run,
    upsert_target,
)
from nlfr.projectors import (
    export_action_graph,
    export_proof_packet,
    export_validation_runway,
)

ROOT = Path(__file__).resolve().parents[1]


def seed_projection_db(tmp_path):
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="run:projection",
        run_group="latest",
        scenario="agent-loop",
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:run.json"],
        redaction_state="safe",
    )
    target_id = upsert_target(
        conn,
        stable_key="target:priority",
        run_id=run_id,
        label="//tasks:priority_test",
        target_kind="py_test",
        status="passed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    action_id = upsert_action(
        conn,
        stable_key="action:test",
        run_id=run_id,
        target_id=target_id,
        action_key="test-action",
        mnemonic="PyTest",
        status="cache_hit",
        source_kind="derived_v1",
        confidence="medium",
        evidence_refs=["execution-log:test-action"],
        redaction_state="safe",
    )
    upsert_cache_event(
        conn,
        stable_key="cache:test-action",
        run_id=run_id,
        target_id=target_id,
        action_id=action_id,
        event_key="test-action-cache",
        event_kind="action_cache",
        hit=True,
        digest="sha256:abc",
        source_kind="derived_v1",
        confidence="medium",
        evidence_refs=["execution-log:test-action"],
        redaction_state="safe",
    )
    upsert_invocation(
        conn,
        stable_key="invocation:bazel",
        run_id=run_id,
        invocation_kind="bazel",
        command=["bazel", "test", "//tasks:priority_test"],
        cwd=tmp_path,
        exit_code=0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:bazel.stdout.txt"],
        redaction_state="safe",
    )
    upsert_artifact(
        conn,
        stable_key="artifact:run",
        run_id=run_id,
        artifact_key="run.json",
        artifact_path="run.json",
        manifest_path="artifact_manifest.json",
        sha256="b" * 64,
        size_bytes=100,
        content_type="application/json",
        producer_command=["nlfr", "run"],
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["manifest:run"],
        redaction_state="safe",
    )
    upsert_failure(
        conn,
        stable_key="failure:none",
        run_id=run_id,
        failure_kind="none",
        message="no failures in fixture",
        source_kind="simulated_v1",
        confidence="low",
        evidence_refs=["fixture:projection"],
        redaction_state="safe",
    )
    return conn


def seed_remote_exec_db(tmp_path, command=None):
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="run:local-exec",
        run_group="local-exec",
        scenario="local-exec-proof",
        mode="local-exec",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:run.json"],
        redaction_state="safe",
    )
    upsert_invocation(
        conn,
        stable_key="invocation:local-exec:bazel",
        run_id=run_id,
        invocation_kind="bazel",
        command=command
        or [
            "bazel",
            "test",
            "//tasks:priority_test",
            "--remote_cache=grpc://127.0.0.1:50051",
            "--remote_executor=grpc://127.0.0.1:50051",
            "--remote_instance_name=main",
        ],
        cwd=tmp_path,
        exit_code=0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:bazel.stdout.txt", "artifact:run.json"],
        redaction_state="safe",
    )
    return conn


def test_action_graph_projection_preserves_truth_labels(tmp_path):
    graph = export_action_graph(seed_projection_db(tmp_path), run_group="latest")

    assert graph["projection_kind"] == "action_graph"
    assert graph["summary"]["runs"] == 1
    assert graph["summary"]["cache_events"] == 1
    cache_nodes = [node for node in graph["nodes"] if node["kind"] == "cache_event"]
    assert cache_nodes[0]["source_kind"] == "derived_v1"
    assert cache_nodes[0]["confidence"] == "medium"
    assert cache_nodes[0]["evidence_refs"] == ["execution-log:test-action"]
    assert any(edge["kind"] == "observed_cache_event" for edge in graph["edges"])


def test_action_graph_projects_remote_execution_configuration_only_when_observed(tmp_path):
    graph = export_action_graph(seed_remote_exec_db(tmp_path), run_group="local-exec")

    config_nodes = [
        node for node in graph["nodes"] if node["kind"] == "remote_execution_config"
    ]
    assert len(config_nodes) == 1
    config = config_nodes[0]
    assert config["label"] == "grpc://127.0.0.1:50051"
    assert config["status"] == "configured"
    assert config["source_kind"] == "derived_v1"
    assert config["confidence"] == "high"
    assert config["payload"]["configured_only"] is True
    assert config["payload"]["remote_executor_arg_present"] is True
    assert config["payload"]["remote_executor_arg_count"] == 1
    assert config["payload"]["endpoint_redacted"] is False
    assert "worker_identity" in config["payload"]["unsupported_claims"]
    assert any(edge["kind"] == "configured_remote_execution" for edge in graph["edges"])


def test_remote_execution_projection_uses_effective_executor_and_redacts_private_endpoint(
    tmp_path,
):
    command = [
        "bazel",
        "test",
        "//tasks:priority_test",
        "--remote_executor=grpc://first.internal:50051",
        "--remote_executor=grpc://second.internal:50052",
    ]
    conn = seed_remote_exec_db(tmp_path, command=command)
    graph = export_action_graph(conn, run_group="local-exec")
    config = next(
        node for node in graph["nodes"] if node["kind"] == "remote_execution_config"
    )

    assert "first.internal" not in json.dumps(graph)
    assert "second.internal" not in json.dumps(graph)
    assert config["label"].startswith("grpc://<redacted>:50052#")
    assert config["payload"]["endpoint_redacted"] is True
    assert config["payload"]["remote_executor_arg_count"] == 2

    proof = export_proof_packet(conn, run_group="local-exec")
    block = next(item for item in proof["blocks"] if item["id"] == "remote_execution")
    endpoint = block["payload"]["remote_executor_endpoints"][0]
    assert endpoint["label"].startswith("grpc://<redacted>:50052#")
    assert endpoint["redacted"] is True
    assert block["metrics"]["remote_executor_overrides"] == 1


def test_runway_projection_groups_operator_events(tmp_path):
    runway = export_validation_runway(seed_projection_db(tmp_path), run_group="latest")

    assert runway["projection_kind"] == "validation_runway"
    assert runway["summary"]["events"] >= 5
    assert {lane["id"] for lane in runway["lanes"]} >= {"run", "bazel", "cache"}
    assert any(event["lane"] == "cache" for event in runway["events"])
    assert any(event["lane"] == "failure" for event in runway["events"])


def test_proof_packet_projection_summarizes_claim_boundaries(tmp_path):
    proof = export_proof_packet(seed_projection_db(tmp_path), run_group="latest")

    assert proof["projection_kind"] == "proof_packet"
    assert proof["summary"]["cache_events"] == 1
    scope = proof["blocks"][0]
    assert scope["title"] == "Proof Scope"
    assert "does not claim remote worker assignment" in " ".join(scope["claims"])
    cache = next(block for block in proof["blocks"] if block["id"] == "cache")
    assert cache["metrics"]["hits"] == 1
    assert cache["metrics"]["hit_rate"] == 1.0


def test_proof_packet_bounds_remote_execution_claims(tmp_path):
    proof = export_proof_packet(seed_remote_exec_db(tmp_path), run_group="local-exec")

    block = next(item for item in proof["blocks"] if item["id"] == "remote_execution")
    assert block["title"] == "Remote Execution Boundary"
    assert block["source_kind"] == "derived_v1"
    assert block["confidence"] == "high"
    assert block["metrics"]["remote_executor_invocations"] == 1
    assert block["metrics"]["worker_identity_observed"] is False
    assert block["metrics"]["scheduler_assignment_observed"] is False
    endpoint = block["payload"]["remote_executor_endpoints"][0]
    assert endpoint["label"] == "grpc://127.0.0.1:50051"
    assert len(endpoint["fingerprint"]) == 16
    assert endpoint["redacted"] is False
    assert "scheduler_assignment" in block["payload"]["unsupported_claims"]
    claim_text = " ".join(block["claims"])
    assert "configuration intent" in claim_text
    assert "worker identity" in claim_text


def test_projection_contracts_are_valid_json_documents() -> None:
    import json

    for name in (
        "canvas_projection.v1.json",
        "proof_packet.v1.json",
        "artifact_manifest.v1.json",
    ):
        payload = json.loads((ROOT / "contracts" / name).read_text())
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert payload["title"].startswith("NLFR")
