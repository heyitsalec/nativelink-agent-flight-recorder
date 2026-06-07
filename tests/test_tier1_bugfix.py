import hashlib
import json
import os
import subprocess
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_cache_event,
    upsert_change,
    upsert_proof_block,
    upsert_run,
    upsert_target,
)
from nlfr.projectors.graph import export_action_graph


ROOT = Path(__file__).resolve().parents[1]
BUGFIX_DIR = ROOT / "tests" / "fixtures" / "agent-scenarios" / "bugfix"
SCENARIO = ROOT / "demo" / "scenarios" / "tier1" / "agent-bugfix-1.json"
PROMPT_FIXTURE = ROOT / "demo" / "scenarios" / "tier1" / "fixtures" / "prompt-bugfix.txt"
SETUP = ROOT / "scripts" / "tier1-bugfix-setup.sh"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bugfix_scenario_prompt_hash_matches_fixture():
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    agent = scenario["record"]["agent"]
    assert agent["kind"] == "cursor_adapter_v1"
    assert agent["prompt_sha256"] == _sha256_file(PROMPT_FIXTURE)
    assert "prompt" not in agent


def test_bugfix_sidecar_fixture_is_collectable_v1():
    sidecar = json.loads((BUGFIX_DIR / "sidecar.cursor_adapter_v1.json").read_text(encoding="utf-8"))
    assert sidecar["source_kind"] == "collectable_v1"
    assert sidecar["agent"]["kind"] == "cursor_adapter_v1"
    assert sidecar["agent"]["model"] == "composer-2.5"
    dumped = json.dumps(sidecar)
    assert "raw_prompt" not in dumped
    assert "prompt" not in sidecar["agent"]


def test_bugfix_setup_broken_fails_check():
    subprocess.run([str(SETUP), "--state", "broken"], cwd=ROOT, check=True)
    env = os.environ.copy()
    env["NLFR_SKIP_BAZEL"] = "1"
    result = subprocess.run(
        [str(SETUP), "--check"],
        cwd=ROOT,
        env=env,
        check=False,
    )
    try:
        assert result.returncode != 0
    finally:
        subprocess.run([str(SETUP), "--restore"], cwd=ROOT, check=True)


def test_bugfix_setup_fixed_passes_check():
    subprocess.run([str(SETUP), "--state", "fixed"], cwd=ROOT, check=True)
    env = os.environ.copy()
    env["NLFR_SKIP_BAZEL"] = "1"
    try:
        result = subprocess.run(
            [str(SETUP), "--check"],
            cwd=ROOT,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    finally:
        subprocess.run([str(SETUP), "--restore"], cwd=ROOT, check=True)


def _seed_bugfix_collectable_db(tmp_path):
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="run:agent-bugfix-1",
        run_group="agent-bugfix-1",
        scenario="agent-bugfix-1",
        mode="generic",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:run.json"],
        redaction_state="safe",
    )
    target_id = upsert_target(
        conn,
        stable_key="target:agent-bugfix-1",
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
        stable_key="cache:agent-bugfix-1",
        run_id=run_id,
        target_id=target_id,
        event_key="agent-bugfix-cache",
        event_kind="action_cache",
        hit=True,
        source_kind="derived_v1",
        confidence="medium",
        evidence_refs=["execution-log:agent-bugfix-1"],
        redaction_state="safe",
    )
    upsert_change(
        conn,
        stable_key="run:agent-bugfix-1:change:tasks/priority_test.py",
        run_id=run_id,
        change_kind="safe_leaf",
        path="tasks/priority_test.py",
        before_hash="a" * 64,
        after_hash="b" * 64,
        summary="agent-bugfix-1 touched tasks/priority_test.py",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["scenario:agent-bugfix-1"],
        redaction_state="safe",
    )
    upsert_proof_block(
        conn,
        stable_key="run:agent-bugfix-1:proof:agent-provenance",
        run_id=run_id,
        block_key="agent-provenance:agent-bugfix-1",
        block_kind="agent_provenance",
        title="Agent Provenance: tier1-bugfix-agent",
        summary="Tier1 bugfix collectable provenance.",
        payload={
            "scenario_id": "agent-bugfix-1",
            "agent": {
                "kind": "cursor_adapter_v1",
                "name": "tier1-bugfix-agent",
                "model": "composer-2.5",
                "prompt_sha256": "a0c42719429deb3badd19b9baa0016b08abf08fb282db95f39a817024852ac58",
            },
            "change": {
                "change_class": "safe_leaf",
                "patch_sha256": "d" * 64,
            },
            "build": {"status": "completed"},
        },
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["scenario:agent-bugfix-1"],
        redaction_state="redacted",
    )
    return conn


def test_cursor_adapter_graph_chain_uses_collectable_v1(tmp_path):
    graph = export_action_graph(_seed_bugfix_collectable_db(tmp_path), run_group="agent-bugfix-1")
    agent_nodes = [node for node in graph["nodes"] if node["kind"] == "agent"]
    assert len(agent_nodes) == 1
    agent = agent_nodes[0]
    assert agent["source_kind"] == "collectable_v1"
    assert agent["payload"]["model"] == "composer-2.5"
    assert agent["payload"]["prompt_sha256"].startswith("a0c42719")
    assert "raw_prompt" not in json.dumps(graph)

    authored = [edge for edge in graph["edges"] if edge["kind"] == "authored_change"]
    validated = [edge for edge in graph["edges"] if edge["kind"] == "validated_by"]
    assert len(authored) == 1
    assert len(validated) == 1
