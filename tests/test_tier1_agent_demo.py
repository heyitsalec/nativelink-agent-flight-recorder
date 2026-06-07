import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TIER1_DIR = ROOT / "demo" / "scenarios" / "tier1"
TIER1_DEMO = ROOT / "scripts" / "tier1-agent-demo.sh"
COMPARE_AGENT_RUNS = ROOT / "scripts" / "compare-agent-runs.sh"

TIER1_SCENARIOS = [
    "agent-bugfix-1.json",
    "agent-feature-compare.json",
    "agent-change-meta.json",
]

DEFAULT_COMPARE_GROUPS = ["record-proof", "canvas-dev", "agent-bugfix-1"]

TIER1_OUTPUT_DIRS = [
    "data/agent-bugfix-1",
    "data/agent-feature-compare",
    "data/agent-change",
]


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_forbidden_prompt(obj: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"prompt", "raw_prompt"}:
                violations.append(f"{path}.{key}" if path else key)
            violations.extend(walk_forbidden_prompt(value, f"{path}.{key}" if path else key))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            violations.extend(walk_forbidden_prompt(item, f"{path}[{index}]"))
    return violations


def validate_tier1_scenario(scenario_path: Path) -> dict[str, Any]:
    payload = load_json(scenario_path)

    violations = walk_forbidden_prompt(payload)
    if violations:
        raise AssertionError(f"forbidden prompt fields in {scenario_path.name}: {violations}")

    assert payload.get("schema_version") == "nlfr.tier1.scenario.v1"

    agent = payload.get("record", {}).get("agent", {})
    assert agent.get("kind") == "cursor_adapter_v1"

    fixture_rel = agent.get("prompt_fixture", "")
    fixture_path = TIER1_DIR / fixture_rel
    assert fixture_rel and fixture_path.is_file(), f"prompt_fixture missing: {fixture_rel}"

    expected_hash = agent.get("prompt_sha256", "")
    actual_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    assert expected_hash == actual_hash, (
        f"prompt_sha256 mismatch in {scenario_path.name}: expected {expected_hash}, got {actual_hash}"
    )

    return payload


@pytest.mark.parametrize("scenario_name", TIER1_SCENARIOS)
def test_tier1_scenario_json_schema(scenario_name: str) -> None:
    payload = validate_tier1_scenario(TIER1_DIR / scenario_name)

    assert payload["record"]["adapter"] == "record-agent-change.sh"
    assert payload["record"]["agent"]["model"]
    assert payload["record"]["change_paths"]
    assert payload["run_group"]
    assert payload["act"] in {1, 2, 3}


def test_tier1_scenario_run_groups_match_output_dirs() -> None:
    expected = {
        "agent-bugfix-1.json": ("agent-bugfix-1", "data/agent-bugfix-1", 1),
        "agent-feature-compare.json": ("agent-feature-compare", "data/agent-feature-compare", 2),
        "agent-change-meta.json": ("agent-change", "data/agent-change", 3),
    }
    for scenario_name, (run_group, output_dir, act) in expected.items():
        payload = load_json(TIER1_DIR / scenario_name)
        assert payload["run_group"] == run_group
        assert payload["record"]["output_dir"] == output_dir
        assert payload["act"] == act


def test_tier1_agent_demo_dry_run_exits_zero() -> None:
    result = run_script(TIER1_DEMO, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "tier1-agent-demo dry-run complete" in result.stdout + result.stderr


def test_tier1_agent_demo_dry_run_json_plan() -> None:
    result = run_script(TIER1_DEMO, "--dry-run", "--json")
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["source_kind"] == "derived_v1"
    assert len(payload["acts"]) == 3
    assert payload["compare_plan"]["pair_count"] == 3
    assert payload["compare_plan"]["run_groups"] == DEFAULT_COMPARE_GROUPS

    run_groups = [act["run_group"] for act in payload["acts"]]
    assert run_groups == ["agent-bugfix-1", "agent-feature-compare", "agent-change"]

    for act in payload["acts"]:
        assert act["commands"]
        for command in act["commands"]:
            assert "record-agent-change.sh" in command
            assert "--dry-run" in command


def test_tier1_agent_demo_dry_run_single_act() -> None:
    result = run_script(TIER1_DEMO, "--dry-run", "--act", "1", "--json")
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert len(payload["acts"]) == 1
    assert payload["acts"][0]["act"] == 1
    assert payload["acts"][0]["run_group"] == "agent-bugfix-1"


def test_tier1_agent_demo_dry_run_does_not_create_sqlite() -> None:
    before = {
        path: path.exists()
        for rel in TIER1_OUTPUT_DIRS
        for path in [ROOT / rel / "nlfr.sqlite"]
    }

    result = run_script(TIER1_DEMO, "--dry-run")
    assert result.returncode == 0, result.stderr

    after = {
        path: path.exists()
        for rel in TIER1_OUTPUT_DIRS
        for path in [ROOT / rel / "nlfr.sqlite"]
    }
    assert before == after


def test_compare_agent_runs_dry_run_exits_zero() -> None:
    result = run_script(COMPARE_AGENT_RUNS, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "compare-agent-runs dry-run complete" in result.stdout


def test_compare_agent_runs_dry_run_json_plan() -> None:
    result = run_script(COMPARE_AGENT_RUNS, "--dry-run", "--json")
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["source_kind"] == "derived_v1"
    assert payload["pair_count"] == 3
    assert payload["run_groups"] == DEFAULT_COMPARE_GROUPS
    assert len(payload["pairs"]) == 3

    pair_labels = [(pair["left"], pair["right"]) for pair in payload["pairs"]]
    assert pair_labels == [
        ("record-proof", "canvas-dev"),
        ("canvas-dev", "agent-bugfix-1"),
        ("record-proof", "agent-bugfix-1"),
    ]

    for pair in payload["pairs"]:
        assert pair["left_db"].endswith("/nlfr.sqlite")
        assert pair["right_db"].endswith("/nlfr.sqlite")
        assert pair["compare_projection"].endswith(f"compare-{pair['left']}-vs-{pair['right']}.json")
