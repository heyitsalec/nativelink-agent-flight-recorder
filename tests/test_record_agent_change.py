import json
import os
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record-agent-change.sh"


def run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_record_agent_change_dry_run_emits_hashed_provenance(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_text = "Add a leaf test for priority_band backlog.\n"
    prompt_file.write_text(prompt_text, encoding="utf-8")

    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "--change-path", "README.md", "--model", "composer-2.5", "--prompt-file", str(prompt_file)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["model"] == "composer-2.5"
    assert payload["change_path"] == "README.md"
    assert payload["source_kind"] == "collectable_v1"

    sidecar = payload["sidecar"]
    assert sidecar["schema_version"] == "nlfr.agent_provenance.sidecar.v1"
    assert sidecar["adapter"] == "record-agent-change.sh"
    agent = sidecar["agent"]
    assert agent["model"] == "composer-2.5"
    assert agent["prompt_sha256"]
    assert "prompt" not in agent
    assert prompt_text not in result.stdout


def test_provenance_sidecar_shape_matches_bounded_patch_contract(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("bounded patch task\n", encoding="utf-8")

    dry = subprocess.run(
        [
            str(SCRIPT),
            "--dry-run",
            "--change-path",
            "tasks/priority_test.py",
            "--model",
            "demo-bounded-llm",
            "--prompt-file",
            str(prompt_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert dry.returncode == 0, dry.stderr
    sidecar = json.loads(dry.stdout)["sidecar"]

    scenario = json.loads((ROOT / "demo" / "scenarios" / "llm-bounded-patch.json").read_text())
    demo_agent = scenario["simulated_agent"]

    assert set(sidecar["agent"]) >= {"kind", "name", "model", "prompt_sha256"}
    assert sidecar["agent"]["model"] == demo_agent["model"] or sidecar["agent"]["model"] == "demo-bounded-llm"
    assert isinstance(sidecar["agent"]["prompt_sha256"], str)
    assert len(sidecar["agent"]["prompt_sha256"]) == 64


def test_generic_run_records_agent_provenance_from_sidecar(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "probe.txt"
    target.write_text("before\n", encoding="utf-8")

    sidecar_path = tmp_path / "sidecar.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema_version": "nlfr.agent_provenance.sidecar.v1",
                "adapter": "test-record-agent-change",
                "agent": {
                    "kind": "cursor_adapter_v1",
                    "name": "test-cursor-agent",
                    "model": "composer-2.5",
                    "prompt_sha256": "abc123" * 10 + "abcd",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = run_nlfr(
        "run",
        "--mode",
        "generic",
        "--scenario",
        "agent-sidecar-probe",
        "--run-group",
        "agent-sidecar",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        "probe.txt",
        "--provenance-sidecar",
        str(sidecar_path),
        "--command",
        f"{sys.executable} -c \"from pathlib import Path; Path('probe.txt').write_text('after\\\\n')\"",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    artifact_root = Path(payload["artifact_root"])
    provenance = json.loads((artifact_root / "agent-provenance.json").read_text())

    assert provenance["schema_version"] == "nlfr.agent_provenance.v1"
    assert provenance["source_kind"] == "collectable_v1"
    assert provenance["agent"]["model"] == "composer-2.5"
    assert provenance["agent"]["prompt_sha256"].startswith("abc123")
    assert "prompt" not in provenance["agent"]
    assert provenance["change"]["affected_paths"] == ["probe.txt"]

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    block = conn.execute(
        "SELECT block_kind, source_kind, payload FROM proof_blocks WHERE block_kind = ?",
        ("agent_provenance",),
    ).fetchone()
    assert block is not None
    assert block["source_kind"] == "collectable_v1"
    stored = json.loads(block["payload"])
    assert stored["agent"]["prompt_sha256"] == provenance["agent"]["prompt_sha256"]
