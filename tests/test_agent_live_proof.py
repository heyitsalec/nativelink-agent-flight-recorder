import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agent-live-proof.sh"
PROMPT_FIXTURE = ROOT / "demo" / "scenarios" / "tier1" / "fixtures" / "prompt-meta.txt"


def test_agent_live_proof_dry_run_contract(tmp_path: Path) -> None:
    result = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["proof_script"] == "agent-live-proof.sh"
    assert payload["nlfr_agent_live"] is True
    assert payload["source_kind"] == "collectable_v1"
    assert payload["confidence"] == "high"
    assert payload["redaction_state"] == "safe"
    assert payload["change_path"] == "adapters/cursor/README.md"
    assert payload["model"] == "composer-2.5"
    assert payload["prompt_sha256"]
    assert len(payload["prompt_sha256"]) == 64

    adapter = payload["adapter"]
    assert adapter["status"] == "dry_run"
    assert adapter["source_kind"] == "collectable_v1"
    agent = adapter["sidecar"]["agent"]
    assert agent["kind"] == "cursor_adapter_v1"
    assert "prompt" not in agent
    assert PROMPT_FIXTURE.read_text(encoding="utf-8") not in result.stdout


def test_agent_live_proof_blocker_without_cursor(tmp_path: Path) -> None:
    out = tmp_path / "agent-live-proof"
    env = os.environ.copy()
    env["NLFR_AGENT_LIVE_OUTPUT"] = str(out)
    env["NLFR_AGENT_LIVE_FORCE_BLOCKER"] = "1"
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    blocker = out / "environment-blocker.json"
    assert blocker.is_file()
    payload = json.loads(blocker.read_text(encoding="utf-8"))
    assert payload["status"] == "environment_blocker"
    assert payload["proof_script"] == "agent-live-proof.sh"
    assert payload["nlfr_agent_live"] is True
    assert payload["source_kind"] == "collectable_v1"
    assert payload["confidence"] == "high"
    assert payload["redaction_state"] == "safe"
    assert "script:agent-live-proof.sh" in payload["evidence_refs"]
    assert payload["scenario_id"] == "agent-live"
    assert payload["run_group"] == "agent-live"


def test_agent_live_proof_blocker_when_cursor_missing(tmp_path: Path) -> None:
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
    blocker = out / "environment-blocker.json"
    assert blocker.is_file()
    payload = json.loads(blocker.read_text(encoding="utf-8"))
    assert payload["status"] == "environment_blocker"
    assert "cursor" in payload["reason"].lower()


@pytest.mark.skipif(
    os.environ.get("NLFR_RUN_AGENT_LIVE") != "1",
    reason="set NLFR_RUN_AGENT_LIVE=1 with Cursor CLI on PATH for live collectable proof",
)
def test_agent_live_proof_live_chain_complete() -> None:
    out = ROOT / "data" / "agent-live-proof"
    env = os.environ.copy()
    env["NLFR_AGENT_LIVE_OUTPUT"] = str(out)
    env.pop("NLFR_AGENT_LIVE_FORCE_BLOCKER", None)
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = out / "summary.json"
    assert summary.is_file()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["chain_complete"] is True
    assert payload["nlfr_agent_live"] is True
    assert payload["proof_script"] == "agent-live-proof.sh"
    assert payload["source_kind"] == "collectable_v1"
    assert payload["agent"]["prompt_sha256"]
    assert "prompt" not in json.dumps(payload)
