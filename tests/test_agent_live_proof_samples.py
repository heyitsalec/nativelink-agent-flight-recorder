import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agent-live-proof.sh"
BLOCKER_SAMPLE = ROOT / "docs" / "proof-samples" / "agent-live-blocker-sample.json"
SUMMARY_SAMPLE = ROOT / "docs" / "proof-samples" / "agent-live-summary-sample.json"
PROMPT_FIXTURE = ROOT / "demo" / "scenarios" / "tier1" / "fixtures" / "prompt-meta.txt"


def test_agent_live_blocker_sample_shape() -> None:
    sample = json.loads(BLOCKER_SAMPLE.read_text(encoding="utf-8"))

    for key in (
        "status",
        "reason",
        "next_step",
        "proof_script",
        "nlfr_agent_live",
        "scenario_id",
        "run_group",
        "source_kind",
        "confidence",
        "redaction_state",
        "evidence_refs",
        "claim_boundary",
    ):
        assert key in sample

    assert sample["status"] == "environment_blocker"
    assert sample["proof_script"] == "agent-live-proof.sh"
    assert sample["nlfr_agent_live"] is True
    assert sample["source_kind"] == "collectable_v1"
    assert sample["confidence"] == "high"
    assert sample["redaction_state"] == "safe"
    assert sample["scenario_id"] == "agent-live"
    assert sample["run_group"] == "agent-live"
    assert "cursor" in sample["reason"].lower()
    assert sample["evidence_refs"] == ["script:agent-live-proof.sh"]
    assert "/Users/" not in json.dumps(sample)


def test_agent_live_blocker_sample_matches_script_probe(tmp_path: Path) -> None:
    out = tmp_path / "agent-live-proof"
    env = os.environ.copy()
    env["NLFR_AGENT_LIVE_OUTPUT"] = str(out)
    env["NLFR_CURSOR_BIN"] = str(tmp_path / "missing-cursor")
    env.pop("NLFR_AGENT_LIVE_FORCE_BLOCKER", None)
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads((out / "environment-blocker.json").read_text(encoding="utf-8"))
    sample = json.loads(BLOCKER_SAMPLE.read_text(encoding="utf-8"))

    for key in (
        "status",
        "proof_script",
        "nlfr_agent_live",
        "scenario_id",
        "run_group",
        "source_kind",
        "confidence",
        "redaction_state",
        "evidence_refs",
        "next_step",
        "claim_boundary",
    ):
        assert payload[key] == sample[key]

    assert "cursor" in payload["reason"].lower()


def test_agent_live_summary_sample_shape() -> None:
    sample = json.loads(SUMMARY_SAMPLE.read_text(encoding="utf-8"))

    for key in (
        "status",
        "proof_script",
        "nlfr_agent_live",
        "scenario_id",
        "run_group",
        "run_id",
        "mode",
        "change_path",
        "agent",
        "agent_source_kind",
        "validation_source_kind",
        "chain_complete",
        "graph_node_kinds",
        "graph_edge_kinds",
        "projection_summary",
        "source_kind",
        "confidence",
        "redaction_state",
        "evidence_refs",
        "claim_boundary",
    ):
        assert key in sample

    assert sample["status"] == "completed"
    assert sample["proof_script"] == "agent-live-proof.sh"
    assert sample["nlfr_agent_live"] is True
    assert sample["source_kind"] == "collectable_v1"
    assert sample["agent_source_kind"] == "collectable_v1"
    assert sample["validation_source_kind"] == "collectable_v1"
    assert sample["chain_complete"] is True
    assert sample["agent"]["kind"] == "cursor_adapter_v1"
    assert sample["agent"]["model"] == "composer-2.5"
    assert len(sample["agent"]["prompt_sha256"]) == 64
    assert "prompt" not in sample["agent"]
    assert PROMPT_FIXTURE.read_text(encoding="utf-8") not in json.dumps(sample)
    assert "<repo>" in sample["workload"]["output_dir"]
    assert sample["cursor_cli"] == "<cursor>"
    assert "/Users/" not in json.dumps(sample)
    assert sample["graph_node_kinds"]["agent"] >= 1
    assert sample["graph_node_kinds"]["change"] >= 1
    assert sample["graph_node_kinds"]["run"] >= 1
    assert "authored_change" in sample["graph_edge_kinds"]
    assert "validated_by" in sample["graph_edge_kinds"]


def test_agent_live_dry_run_prompt_sha256_matches_summary_sample() -> None:
    result = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    dry = json.loads(result.stdout)
    sample = json.loads(SUMMARY_SAMPLE.read_text(encoding="utf-8"))

    assert dry["prompt_sha256"] == sample["agent"]["prompt_sha256"]
    assert dry["model"] == sample["agent"]["model"]
    assert dry["change_path"] == sample["change_path"][0]
    assert dry["adapter"]["sidecar"]["agent"]["kind"] == "cursor_adapter_v1"
