import json
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_action,
    upsert_artifact,
    upsert_cache_event,
    upsert_change,
    upsert_failure,
    upsert_invocation,
    upsert_proof_block,
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


def seed_agent_loop_db(tmp_path):
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="run:agent-loop",
        run_group="agent-loop",
        scenario="llm-bounded-patch",
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:run.json"],
        redaction_state="safe",
    )
    target_id = upsert_target(
        conn,
        stable_key="target:agent-loop",
        run_id=run_id,
        label="//tasks:priority_test",
        target_kind="py_test",
        status="passed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    upsert_cache_event(
        conn,
        stable_key="cache:agent-loop",
        run_id=run_id,
        target_id=target_id,
        event_key="agent-loop-cache",
        event_kind="action_cache",
        hit=True,
        source_kind="derived_v1",
        confidence="medium",
        evidence_refs=["execution-log:agent-loop"],
        redaction_state="safe",
    )
    upsert_change(
        conn,
        stable_key="run:agent-loop:change:llm-bounded-patch:tasks/priority_test.py",
        run_id=run_id,
        change_kind="safe_leaf",
        path="tasks/priority_test.py",
        before_hash="a" * 64,
        after_hash="b" * 64,
        summary="llm-bounded-patch touched tasks/priority_test.py",
        source_kind="simulated_v1",
        confidence="medium",
        evidence_refs=["scenario:llm-bounded-patch", "prompt:sha256:5f78"],
        redaction_state="safe",
    )
    upsert_proof_block(
        conn,
        stable_key="run:agent-loop:proof:agent-provenance:llm-bounded-patch",
        run_id=run_id,
        block_key="agent-provenance:llm-bounded-patch",
        block_kind="agent_provenance",
        title="Agent Provenance: demo-bounded-llm-worker",
        summary="llm-bounded-patch patch recorded with build status completed.",
        payload={
            "scenario_id": "llm-bounded-patch",
            "agent": {
                "kind": "bounded_llm_v1",
                "name": "demo-bounded-llm-worker",
                "model": "demo-bounded-llm",
                "prompt_sha256": "5f787e73d6d3f8b65082f2d922e670104c580461abff1185780c76ed13a300a6",
                "input_signal": "redacted",
            },
            "change": {
                "change_class": "safe_leaf",
                "patch_sha256": "c" * 64,
            },
            "build": {"status": "completed"},
        },
        source_kind="simulated_v1",
        confidence="medium",
        evidence_refs=["scenario:llm-bounded-patch"],
        redaction_state="safe",
    )
    return conn


def test_action_graph_projects_agent_patch_validation_chain(tmp_path):
    graph = export_action_graph(seed_agent_loop_db(tmp_path), run_group="agent-loop")

    assert graph["summary"]["changes"] == 1
    assert graph["summary"]["agents"] == 1

    agent_nodes = [node for node in graph["nodes"] if node["kind"] == "agent"]
    change_nodes = [node for node in graph["nodes"] if node["kind"] == "change"]
    run_nodes = [node for node in graph["nodes"] if node["kind"] == "run"]
    assert len(agent_nodes) == 1
    assert len(change_nodes) == 1

    agent = agent_nodes[0]
    assert agent["source_kind"] == "simulated_v1"
    assert agent["payload"]["model"] == "demo-bounded-llm"
    assert agent["payload"]["prompt_sha256"].startswith("5f787e73")
    # Raw prompt must never appear anywhere in the projection.
    assert "raw_prompt" not in json.dumps(graph)

    change = change_nodes[0]
    assert change["source_kind"] == "simulated_v1"
    assert change["label"] == "tasks/priority_test.py"

    authored = [edge for edge in graph["edges"] if edge["kind"] == "authored_change"]
    validated = [edge for edge in graph["edges"] if edge["kind"] == "validated_by"]
    assert len(authored) == 1
    assert authored[0]["from"] == agent["id"]
    assert authored[0]["to"] == change["id"]
    assert len(validated) == 1
    assert validated[0]["from"] == change["id"]
    assert validated[0]["to"] == run_nodes[0]["id"]

    # The validated run carries the validation + cache evidence tail.
    assert any(node["kind"] == "target" for node in graph["nodes"])
    assert any(node["kind"] == "cache_event" for node in graph["nodes"])


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


def seed_cold_warm_db(tmp_path):
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    cold_run_id = upsert_run(
        conn,
        stable_key="run:cold-cache",
        run_group="cold-warm",
        scenario="cold-cache",
        mode="cache-only",
        status="completed",
        started_at="2026-06-06T12:00:00.000000Z",
        ended_at="2026-06-06T12:00:30.000000Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:cold-run.json"],
        redaction_state="safe",
    )
    warm_run_id = upsert_run(
        conn,
        stable_key="run:warm-cache",
        run_group="cold-warm",
        scenario="warm-cache",
        mode="cache-only",
        status="completed",
        started_at="2026-06-06T12:01:00.000000Z",
        ended_at="2026-06-06T12:01:10.000000Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:warm-run.json"],
        redaction_state="safe",
    )
    for run_id, hits, misses in (
        (cold_run_id, 1, 3),
        (warm_run_id, 4, 0),
    ):
        for index in range(hits):
            upsert_cache_event(
                conn,
                stable_key=f"cache:{run_id}:hit:{index}",
                run_id=run_id,
                event_key=f"hit-{index}",
                event_kind="action_cache",
                hit=True,
                source_kind="derived_v1",
                confidence="medium",
                evidence_refs=["bep:cache"],
                redaction_state="safe",
            )
        for index in range(misses):
            upsert_cache_event(
                conn,
                stable_key=f"cache:{run_id}:miss:{index}",
                run_id=run_id,
                event_key=f"miss-{index}",
                event_kind="action_cache",
                hit=False,
                source_kind="derived_v1",
                confidence="medium",
                evidence_refs=["bep:cache"],
                redaction_state="safe",
            )
        upsert_invocation(
            conn,
            stable_key=f"invocation:{run_id}",
            run_id=run_id,
            invocation_kind="bazel",
            command=["bazel", "test", "//tasks:priority_test"],
            cwd=tmp_path,
            exit_code=0,
            started_at="2026-06-06T12:00:00.000000Z" if run_id == cold_run_id else "2026-06-06T12:01:00.000000Z",
            ended_at="2026-06-06T12:00:30.000000Z" if run_id == cold_run_id else "2026-06-06T12:01:10.000000Z",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["artifact:bazel.stdout.txt"],
            redaction_state="safe",
        )
    return conn


def test_proof_packet_emits_cache_economics_for_cold_warm_group(tmp_path):
    proof = export_proof_packet(seed_cold_warm_db(tmp_path), run_group="cold-warm")

    block = next(item for item in proof["blocks"] if item["id"] == "cache_economics")
    assert block["source_kind"] == "derived_v1"
    assert block["metrics"]["legs"] == 2
    assert block["metrics"]["warm_hit_rate_higher"] is True
    assert block["metrics"]["warm_duration_lower"] is True
    assert block["payload"]["comparison"]["hit_rate_delta"] == 0.75
    assert block["payload"]["comparison"]["duration_delta_seconds"] == -20.0
    cold_leg = next(leg for leg in block["payload"]["legs"] if leg["scenario"] == "cold-cache")
    warm_leg = next(leg for leg in block["payload"]["legs"] if leg["scenario"] == "warm-cache")
    assert cold_leg["hit_rate"] == 0.25
    assert warm_leg["hit_rate"] == 1.0
    assert cold_leg["duration_seconds"] == 30.0
    assert warm_leg["duration_seconds"] == 10.0
    assert any("higher cache hit_rate" in claim for claim in block["claims"])
    assert any("lower duration" in claim for claim in block["claims"])


def test_proof_packet_bounds_remote_execution_claims(tmp_path):
    proof = export_proof_packet(seed_remote_exec_db(tmp_path), run_group="local-exec")

    block = next(item for item in proof["blocks"] if item["id"] == "remote_execution")
    assert block["title"] == "Remote Execution Boundary"
    assert block["source_kind"] == "collectable_v1"
    assert block["confidence"] == "high"
    assert block["metrics"]["remote_executor_invocations"] == 1
    assert block["metrics"]["worker_identity_observed"] is False
    assert block["metrics"]["scheduler_assignment_observed"] is False
    endpoint = block["payload"]["remote_executor_endpoints"][0]
    assert endpoint["label"] == "grpc://127.0.0.1:50051"
    assert len(endpoint["fingerprint"]) == 16
    assert endpoint["redacted"] is False
    assert "scheduler_assignment" in block["payload"]["unsupported_claims"]
    assert "action_placement" in block["payload"]["unsupported_claims"]
    assert "load_distribution" in block["payload"]["unsupported_claims"]
    claim_text = " ".join(block["claims"])
    assert "configuration intent" in claim_text
    assert "worker identity" in claim_text


def seed_local_path_db(tmp_path):
    """Seed a run whose invocation carries real absolute local paths.

    This reproduces the issue #60 dogfood blocker: ``nlfr record`` stores the
    adopter's real ``cwd`` and the injected ``--build_event_json_file=<abs>``
    flag, both self-labelled ``redaction_state: safe`` at record time. Returns
    the connection plus the two absolute paths the projection must scrub.
    """

    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    workspace = tmp_path / "workspace"
    bep = tmp_path / "data" / "nlfr-record" / "grp" / "runs" / "r1" / "artifacts" / "bazel-bep.json"
    run_id = upsert_run(
        conn,
        stable_key="run:paths",
        run_group="grp",
        scenario="record",
        mode="record",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:run.json"],
        redaction_state="safe",
    )
    upsert_invocation(
        conn,
        stable_key="run:paths:invocation:bazel",
        run_id=run_id,
        invocation_kind="bazel",
        command=["bazel", "test", f"--build_event_json_file={bep}", "//tasks:priority_test"],
        cwd=str(workspace),
        exit_code=0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:bazel.stdout.txt"],
        redaction_state="safe",
    )
    return conn, workspace, bep


def test_action_graph_scrubs_local_paths_at_sharing_boundary(tmp_path):
    conn, workspace, bep = seed_local_path_db(tmp_path)
    graph = export_action_graph(conn, run_group="grp")

    serialized = json.dumps(graph)
    # Grep-style: no absolute local path substring survives into the shared JSON.
    assert str(workspace) not in serialized
    assert str(bep) not in serialized
    assert str(tmp_path) not in serialized

    invocation = next(node for node in graph["nodes"] if node["kind"] == "invocation")
    # Scrubbed content -> honestly relabelled 'redacted' (never 'safe').
    assert invocation["redaction_state"] == "redacted"
    # Basenames preserved so the projection stays interpretable.
    assert invocation["payload"]["cwd"] == "[REDACTED:abs_path]/workspace"
    assert any(
        "[REDACTED:abs_path]/bazel-bep.json" in part
        for part in invocation["payload"]["command"]
    )
    # A Bazel label is not a path and is preserved verbatim.
    assert "//tasks:priority_test" in invocation["payload"]["command"]

    # A node with no local paths keeps its recorded 'safe' label untouched.
    run_node = next(node for node in graph["nodes"] if node["kind"] == "run")
    assert run_node["redaction_state"] == "safe"


def test_runway_scrubs_local_paths_at_sharing_boundary(tmp_path):
    conn, workspace, bep = seed_local_path_db(tmp_path)
    runway = export_validation_runway(conn, run_group="grp")

    serialized = json.dumps(runway)
    assert str(workspace) not in serialized
    assert str(bep) not in serialized
    assert str(tmp_path) not in serialized

    invocation = next(event for event in runway["events"] if event["lane"] == "bazel")
    assert invocation["redaction_state"] == "redacted"
    assert invocation["payload"]["cwd"] == "[REDACTED:abs_path]/workspace"
    assert any(
        "[REDACTED:abs_path]/bazel-bep.json" in part
        for part in invocation["payload"]["command"]
    )


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
