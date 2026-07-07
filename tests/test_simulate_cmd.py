import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from nlfr.commands.simulate_cmd import _derive_patch_applied


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
    # patch_applied is DERIVED from the before/after hashes the sim actually
    # produced (GitHub issue #56), not a hardcoded literal. It is True here
    # *because* the affected file's content hash changed when the diff applied.
    change = provenance["change"]
    affected = change["affected_paths"]
    assert affected == ["tasks/priority_test.py"]
    before = change["before_hashes"]["tasks/priority_test.py"]
    after = change["after_hashes"]["tasks/priority_test.py"]
    assert before is not None and after is not None
    assert before != after, "the patch must change the file hash — that is the evidence"
    assert change["patch_applied"] is True
    assert change["patch_applied"] == _derive_patch_applied(affected, change["before_hashes"], change["after_hashes"])
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


def test_simulate_bounded_llm_patch_records_hashed_prompt_provenance(tmp_path) -> None:
    output_dir = tmp_path / "agent-sim"

    result = run_nlfr(
        "simulate",
        "--scenario",
        "llm-bounded-patch",
        "--output-dir",
        str(output_dir),
        "--skip-run",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    scenario = payload["scenarios"][0]
    provenance = json.loads(Path(scenario["provenance_path"]).read_text())

    agent = provenance["agent"]
    assert agent["kind"] == "bounded_llm_v1"
    assert agent["model"] == "demo-bounded-llm"
    assert agent["prompt_sha256"] == (
        "5f787e73d6d3f8b65082f2d922e670104c580461abff1185780c76ed13a300a6"
    )
    # Hashed-prompt evidence ref is present; the raw prompt is never stored.
    assert "prompt:sha256:5f787e73" in " ".join(provenance["evidence_refs"])
    assert "prompt" not in agent  # only the hash, never a raw prompt field

    with sqlite3.connect(output_dir / "nlfr.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        proof = conn.execute("SELECT payload FROM proof_blocks").fetchone()
    stored = json.loads(proof["payload"])
    assert stored["agent"]["prompt_sha256"].startswith("5f787e73")
    assert "prompt" not in stored["agent"]


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


def test_derive_patch_applied_reflects_hash_evidence() -> None:
    # The flag is a function of evidence, not a constant: it flips with the
    # hashes. A changed file -> True; identical before/after -> False.
    paths = ["tasks/priority_test.py"]
    assert _derive_patch_applied(paths, {"tasks/priority_test.py": "aaa"}, {"tasks/priority_test.py": "bbb"}) is True
    assert _derive_patch_applied(paths, {"tasks/priority_test.py": "aaa"}, {"tasks/priority_test.py": "aaa"}) is False
    # New file (absent before) counts as a change; no affected paths -> no evidence.
    assert _derive_patch_applied(["new.py"], {"new.py": None}, {"new.py": "ccc"}) is True
    assert _derive_patch_applied([], {}, {}) is False


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
