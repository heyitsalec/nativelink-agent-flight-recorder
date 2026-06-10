"""Two-act spark scenario, prompt builders, and harness pieces."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from nlfr.spark import (
    apply_workspace_setup,
    build_act1_prompt,
    build_act2_prompt,
    classify_validation_failure,
    extract_python_file,
    failure_excerpt,
    load_spark_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "demo" / "scenarios" / "two-act-underspec.json"
HARNESS = ROOT / "scripts" / "two-act-spark-proof.sh"
STUB = ROOT / "scripts" / "spark-stub-claude.sh"


def _mini_workspace(tmp_path: Path) -> Path:
    """A minimal stand-in for demo/bazel-monorepo (which is host-local)."""

    ws = tmp_path / "ws"
    (ws / "tasks").mkdir(parents=True)
    (ws / "tasks" / "policy.py").write_text(
        "URGENT_THRESHOLD = 90\nNORMAL_THRESHOLD = 50\n", encoding="utf-8"
    )
    (ws / "tasks" / "priority.py").write_text(
        "from tasks import policy\n", encoding="utf-8"
    )
    (ws / "tasks" / "BUILD.bazel").write_text(
        'py_library(\n    name = "policy",\n    srcs = ["policy.py"],\n)\n',
        encoding="utf-8",
    )
    return ws


def test_scenario_loads_and_documents_design_honesty():
    scenario = load_spark_scenario(SCENARIO_PATH)
    assert scenario["scenario_id"] == "two-act-underspec"
    honesty = scenario["design_honesty"]
    assert "what_the_agent_saw" in honesty
    assert "what_the_agent_could_not_see" in honesty
    assert "retry_policy" in honesty
    # The hidden requirement extends, never contradicts, the visible spec.
    assert "60" in "\n".join(scenario["hidden_validation"]["content_lines"])
    assert "60" not in scenario["task_spec"]


def test_scenario_rejects_raw_prompt_keys(tmp_path: Path):
    payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    payload["acts"]["act1"]["prompt"] = "leak"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="raw prompts"):
        load_spark_scenario(bad)


def test_workspace_setup_writes_hidden_test_and_build_rules(tmp_path: Path):
    scenario = load_spark_scenario(SCENARIO_PATH)
    ws = _mini_workspace(tmp_path)
    written = apply_workspace_setup(scenario, ws)

    hidden_rel = scenario["hidden_validation"]["path"]
    hidden = ws / hidden_rel
    assert hidden.is_file()
    assert hidden_rel in written
    assert "escalation_tier(10, 60)" in hidden.read_text(encoding="utf-8")

    build = (ws / "tasks" / "BUILD.bazel").read_text(encoding="utf-8")
    assert 'name = "escalation"' in build
    assert 'name = "escalation_policy_test"' in build

    # Scenario-documented workspace overrides are applied and hash-recorded:
    # the temp validation workspace must not inherit the demo template's
    # local-remote-execution git_override (broken for cache-only on this host).
    assert "MODULE.bazel" in written
    module = (ws / "MODULE.bazel").read_text(encoding="utf-8")
    assert "git_override(" not in module
    assert "bazel_dep(" not in module
    for override in scenario["workspace_overrides"]:
        assert override.get("reason"), "workspace overrides must document a reason"

    # Idempotent: re-applying does not duplicate BUILD rules.
    apply_workspace_setup(scenario, ws)
    build_again = (ws / "tasks" / "BUILD.bazel").read_text(encoding="utf-8")
    assert build_again.count('name = "escalation_policy_test"') == 1


def test_act1_prompt_is_deterministic_and_omits_hidden_requirement(tmp_path: Path):
    scenario = load_spark_scenario(SCENARIO_PATH)
    ws = _mini_workspace(tmp_path)
    apply_workspace_setup(scenario, ws)
    prompt_a = build_act1_prompt(scenario, ws)
    prompt_b = build_act1_prompt(scenario, ws)
    # Deterministic: a skeptic can rebuild the prompt and verify the receipt hash.
    assert hashlib.sha256(prompt_a.encode()).hexdigest() == hashlib.sha256(
        prompt_b.encode()
    ).hexdigest()
    assert scenario["task_spec"] in prompt_a
    # The hidden second-window requirement never reaches the agent.
    assert "60" not in prompt_a
    assert "escalation_policy_test" not in prompt_a


def test_act2_prompt_embeds_recorded_failure_evidence():
    scenario = load_spark_scenario(SCENARIO_PATH)
    prompt = build_act2_prompt(
        scenario,
        act1_file_content="def escalation_tier(score, age_days):\n    return 'p2'\n",
        failure_evidence="[artifact: bazel.stderr.txt]\nFAIL: //tasks:escalation_policy_test\nassert escalation_tier(10, 60) == \"p0\"\n",
    )
    assert "recorded failure evidence" in prompt
    assert "escalation_tier(10, 60)" in prompt
    assert scenario["task_spec"] in prompt


def test_extract_python_file_parses_first_fenced_block():
    response = "Short sentence.\n\n```python\nVALUE = 1\n```\n\nTrailing prose."
    assert extract_python_file(response) == "VALUE = 1\n"
    bare = "```\nVALUE = 2\n```"
    assert extract_python_file(bare) == "VALUE = 2\n"
    with pytest.raises(ValueError, match="no fenced code block"):
        extract_python_file("no code here")


def test_failure_excerpt_redacts_host_paths(tmp_path: Path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "bazel.stderr.txt").write_text(
        "INFO: ok\nFAIL: //tasks:escalation_policy_test (see /Users/somebody/cache/test.log)\n"
        "assert escalation_tier(10, 60) == \"p0\"\n",
        encoding="utf-8",
    )
    (artifact_root / "bazel.stdout.txt").write_text(
        "FAIL: test_second_staleness_window_escalates_again\n"
        "Traceback (most recent call last):\n"
        '  File "/Users/somebody/sandbox/tasks/escalation_policy_test.py", line 25\n'
        "AssertionError: 'p1' != 'p0'\n",
        encoding="utf-8",
    )
    excerpt = failure_excerpt(artifact_root)
    assert "FAIL: //tasks:escalation_policy_test" in excerpt
    assert "/Users/somebody" not in excerpt
    assert "<redacted-path>" in excerpt
    assert excerpt.startswith("[artifact: bazel.stderr.txt]")
    # Both streams are combined: stderr carries bazel's summary, stdout the
    # failing test's own assertion detail — the part a fixing agent needs.
    assert "[artifact: bazel.stdout.txt]" in excerpt
    assert "AssertionError: 'p1' != 'p0'" in excerpt


HIDDEN_TARGET = "//tasks:escalation_policy_test"


def test_classify_honest_scenario_failure(tmp_path: Path):
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "bazel.stderr.txt").write_text(
        "INFO: Found 2 test targets...\n"
        f"FAIL: {HIDDEN_TARGET} (see /tmp/test.log)\n"
        "INFO: Build completed, 1 test FAILED, 4 total actions\n",
        encoding="utf-8",
    )
    verdict = classify_validation_failure(root, hidden_target=HIDDEN_TARGET)
    assert verdict["classification"] == "scenario_validation_failure"
    assert verdict["honest_scenario_failure"] is True


def test_classify_rejects_toolchain_failure_as_red_leg(tmp_path: Path):
    """Regression: the 2026-06-09 stub run recorded a bazel version mismatch as
    act1 'red'. A toolchain failure must classify as a blocker, never as the
    recorder catching the agent."""

    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "bazel.stderr.txt").write_text(
        "Starting local Bazel server and connecting to it...\n"
        'ERROR: Bazel version 7.4.1 is not compatible with module "rules_rs@0.0.76" '
        "(bazel_compatibility: [>=7.7.0])\n"
        "ERROR: Error computing the main repository mapping: Bazel compatibility check failed\n",
        encoding="utf-8",
    )
    verdict = classify_validation_failure(root, hidden_target=HIDDEN_TARGET)
    assert verdict["classification"] == "toolchain_failure"
    assert verdict["honest_scenario_failure"] is False
    assert any("not compatible with module" in sig for sig in verdict["matched_signatures"])


def test_classify_rejects_failure_unrelated_to_hidden_target(tmp_path: Path):
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "bazel.stderr.txt").write_text(
        "FAIL: //elsewhere:other_test (see /tmp/test.log)\n", encoding="utf-8"
    )
    verdict = classify_validation_failure(root, hidden_target=HIDDEN_TARGET)
    assert verdict["classification"] == "unattributed_failure"
    assert verdict["honest_scenario_failure"] is False


def test_classify_accepts_agent_build_breakage_of_hidden_target(tmp_path: Path):
    """If the agent's code does not even build, bazel reports the hidden test
    target as FAILED TO BUILD — still an honest scenario failure (the agent's
    real output failed real validation)."""

    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "bazel.stdout.txt").write_text(
        "ERROR: /ws/tasks/BUILD.bazel:9:11: Compiling tasks/escalation.py failed\n"
        f"{HIDDEN_TARGET}  FAILED TO BUILD\n",
        encoding="utf-8",
    )
    verdict = classify_validation_failure(root, hidden_target=HIDDEN_TARGET)
    assert verdict["honest_scenario_failure"] is True


def test_failure_excerpt_requires_recorded_failure(tmp_path: Path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "bazel.stdout.txt").write_text("all green\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no failure evidence"):
        failure_excerpt(artifact_root)


def test_stub_claude_emits_claude_shaped_json_for_both_acts():
    act1 = subprocess.run(
        [str(STUB), "-p", "TASK: implement", "--output-format", "json"],
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(act1.stdout)
    assert payload["is_error"] is False
    assert payload["session_id"].startswith("stub-act1-")
    assert "modelUsage" in payload
    body = extract_python_file(payload["result"])
    assert "SECOND" not in body  # act1 best effort: single window only

    act2 = subprocess.run(
        [str(STUB), "-p", "recorded failure evidence: assert", "--output-format", "json"],
        text=True,
        capture_output=True,
        check=True,
    )
    payload2 = json.loads(act2.stdout)
    body2 = extract_python_file(payload2["result"])
    assert "SECOND_STALENESS_WINDOW_DAYS = 60" in body2

    version = subprocess.run([str(STUB), "--version"], text=True, capture_output=True, check=True)
    assert "stub-claude" in version.stdout


def test_stub_act1_module_genuinely_fails_hidden_test(tmp_path: Path):
    """The stub's act1 module is a faithful spec implementation that really
    fails the hidden second-window requirement when executed — the red leg is
    real execution, not scripted corruption.

    The hidden test runs EXACTLY as bazel py_test runs it: the file executed
    as a plain script. (Regression: an earlier draft used bare ``def test_*``
    functions, which script execution never calls — the hidden test passed
    vacuously and act1 went green on the first stub proof run.)"""

    import sys as _sys

    scenario = load_spark_scenario(SCENARIO_PATH)
    pkg = tmp_path / "tasks"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "policy.py").write_text(
        "URGENT_THRESHOLD = 90\nNORMAL_THRESHOLD = 50\n", encoding="utf-8"
    )

    hidden_path = tmp_path / scenario["hidden_validation"]["path"]
    hidden_path.parent.mkdir(parents=True, exist_ok=True)
    hidden_path.write_text(
        "\n".join(scenario["hidden_validation"]["content_lines"]) + "\n",
        encoding="utf-8",
    )

    def run_hidden_as_bazel_would() -> subprocess.CompletedProcess:
        # bazel py_test executes the file as a script with the runfiles root
        # importable; PYTHONPATH stands in for the runfiles root here.
        return subprocess.run(
            [_sys.executable, str(hidden_path)],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(tmp_path)},
            text=True,
            capture_output=True,
            check=False,
        )

    act1 = subprocess.run(
        [str(STUB), "-p", "TASK: implement", "--output-format", "json"],
        text=True,
        capture_output=True,
        check=True,
    )
    module = extract_python_file(json.loads(act1.stdout)["result"])
    (pkg / "escalation.py").write_text(module, encoding="utf-8")

    result = run_hidden_as_bazel_would()
    assert result.returncode != 0, result.stdout + result.stderr
    assert "test_second_staleness_window_escalates_again" in result.stderr
    # The recorded failure evidence names expected vs actual tiers.
    assert "'p0'" in result.stderr

    # And the act2 fix passes the same hidden requirement.
    act2 = subprocess.run(
        [str(STUB), "-p", "recorded failure evidence", "--output-format", "json"],
        text=True,
        capture_output=True,
        check=True,
    )
    fixed = extract_python_file(json.loads(act2.stdout)["result"])
    (pkg / "escalation.py").write_text(fixed, encoding="utf-8")
    result2 = run_hidden_as_bazel_would()
    assert result2.returncode == 0, result2.stdout + result2.stderr


def test_harness_records_blocker_without_toolchain(tmp_path: Path):
    """Outside nix develop the harness must record an honest blocker, exit 2."""

    if shutil.which("nativelink") or shutil.which("native-link"):
        pytest.skip("nativelink available; blocker path not reachable")
    out = tmp_path / "two-act"
    result = subprocess.run(
        [str(HARNESS)],
        cwd=ROOT,
        env={
            **dict(**__import__("os").environ),
            "NLFR_TWO_ACT_OUTPUT": str(out),
            "NLFR_SPARK_CLAUDE_BIN": str(STUB),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    blocker = json.loads((out / "environment-blocker.json").read_text())
    assert blocker["status"] == "environment_blocker"
    assert blocker["source_kind"] == "collectable_v1"
