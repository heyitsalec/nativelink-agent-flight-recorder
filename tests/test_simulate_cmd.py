import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_simulate_command_mutates_workspace_and_records_provenance(tmp_path) -> None:
    output_dir = tmp_path / "agent-sim"

    result = run_nlfr(
        "simulate",
        "--scenario",
        "safe-leaf-change",
        "--output-dir",
        str(output_dir),
        "--skip-run",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    scenario = payload["scenarios"][0]
    workspace = Path(scenario["workspace"])
    provenance_path = Path(scenario["provenance_path"])

    assert scenario["scenario_id"] == "safe-leaf-change"
    assert scenario["build"]["status"] == "simulated_only"
    assert "test_priority_band_marks_backlog_work" in (
        workspace / "tasks" / "priority_test.py"
    ).read_text()
    assert provenance_path.exists()

    provenance = json.loads(provenance_path.read_text())
    assert provenance["agent"]["name"] == "demo-leaf-worker"
    assert provenance["change"]["patch_applied"] is True
    assert provenance["build"]["run_id"] == scenario["build"]["run_id"]
    assert "run:" in " ".join(provenance["evidence_refs"])

    with sqlite3.connect(output_dir / "nlfr.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT status, source_kind FROM runs").fetchone()
        change = conn.execute("SELECT path, source_kind FROM changes").fetchone()
        proof = conn.execute(
            "SELECT title, source_kind, payload FROM proof_blocks"
        ).fetchone()

    assert run["status"] == "simulated_only"
    assert run["source_kind"] == "simulated_v1"
    assert change["path"] == "tasks/priority_test.py"
    assert change["source_kind"] == "simulated_v1"
    assert proof["title"] == "Agent Provenance: demo-leaf-worker"
    assert json.loads(proof["payload"])["scenario_id"] == "safe-leaf-change"


def test_simulate_command_records_build_blocker_provenance(tmp_path) -> None:
    output_dir = tmp_path / "agent-sim"

    result = run_nlfr(
        "simulate",
        "--scenario",
        "safe-leaf-change",
        "--output-dir",
        str(output_dir),
        "--skip-nativelink",
        "--bazel-executable",
        "definitely-missing-bazel-for-nlfr",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    scenario = payload["scenarios"][0]

    assert scenario["build"]["status"] == "environment_blocker"
    assert scenario["build"]["returncode"] == 1
    assert Path(scenario["build"]["artifact_root"], "agent-provenance.json").exists()

    provenance = json.loads(Path(scenario["provenance_path"]).read_text())
    assert provenance["build"]["status"] == "environment_blocker"
    assert f"run:{scenario['build']['run_id']}" in provenance["evidence_refs"]

    with sqlite3.connect(output_dir / "nlfr.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT status, source_kind FROM runs").fetchone()
        artifact = conn.execute(
            "SELECT artifact_key, source_kind FROM artifacts WHERE artifact_key = ?",
            ("agent-provenance.json",),
        ).fetchone()
        proof = conn.execute(
            "SELECT summary, source_kind, evidence_refs FROM proof_blocks"
        ).fetchone()

    assert run["status"] == "environment_blocker"
    assert run["source_kind"] == "collectable_v1"
    assert artifact["source_kind"] == "simulated_v1"
    assert "environment_blocker" in proof["summary"]
    assert proof["source_kind"] == "simulated_v1"
    assert f"run:{scenario['build']['run_id']}" in proof["evidence_refs"]


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
