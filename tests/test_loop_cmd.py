"""`nlfr loop` — the native evaluate → fix → revalidate driver.

End-to-end mechanics with a fake bazel shim (red first invocation, green
second) and the committed deterministic stub agent
(`scripts/spark-stub-claude.sh`): iteration 1 goes red and is honestly
attributed, the verdict's first next step dispatches the fix with the
recorded evidence excerpt, iteration 2 validates green, a compare projection
is exported, and the loop summary + per-iteration evaluation proof blocks
land in the evidence DB. The blocker path (toolchain-signature red) must stop
the loop with exit 2 and never dispatch a fix; the iteration cap must exit 1
without a retry spiral.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect

ROOT = Path(__file__).resolve().parents[1]
STUB_CLAUDE = ROOT / "scripts" / "spark-stub-claude.sh"
HIDDEN_TARGET = "//tasks:escalation_policy_test"

_FAKE_BAZEL = """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

STATE = Path({state!r})
MODE = {mode!r}  # "red_then_green" or "toolchain"

args = sys.argv[1:]
if "--version" in args:
    print("bazel 7.4.1")
    raise SystemExit(0)

def flag(prefix):
    for arg in args:
        if arg.startswith(prefix):
            return arg[len(prefix):]
    return None

count = int(STATE.read_text()) if STATE.exists() else 0
STATE.write_text(str(count + 1))
red = MODE == "toolchain" or count == 0

label = {label!r}
events = [
    {{"id": {{"started": {{}}}}, "started": {{"command": "test"}}}},
    {{"id": {{"targetConfigured": {{"label": label}}}},
      "configured": {{"targetKind": "py_test rule"}}}},
    {{"id": {{"targetCompleted": {{"label": label}}}},
      "completed": {{"success": (not red), "targetKind": "py_test rule"}}}},
]
if red:
    events.append({{"id": {{"buildFinished": {{}}}},
                    "finished": {{"exitCode": {{"name": "TESTS_FAILED", "code": 3}}}}}})
else:
    events.append({{"id": {{"buildFinished": {{}}}},
                    "finished": {{"exitCode": {{"name": "SUCCESS", "code": 0}}}}}})

bep = flag("--build_event_json_file=")
if bep:
    Path(bep).write_text("\\n".join(json.dumps(e) for e in events) + "\\n")
profile = flag("--profile=")
if profile:
    Path(profile).write_text("{{}}")
exec_log = flag("--execution_log_json_file=")
if exec_log:
    Path(exec_log).write_text("[]")

if MODE == "toolchain":
    sys.stderr.write("/bin/sh: bazel-real: command not found\\n")
    raise SystemExit(127)
if red:
    sys.stderr.write(
        "FAIL: " + label + " (see test.log)\\n"
        "AssertionError: escalation_tier(50, 61) expected a second escalation\\n"
    )
    raise SystemExit(3)
print("PASS: all targets")
raise SystemExit(0)
"""


def _write_fake_bazel(tmp_path: Path, mode: str) -> Path:
    shim = tmp_path / "fake-bazel.py"
    shim.write_text(
        _FAKE_BAZEL.format(
            state=str(tmp_path / "fake-bazel-state.txt"),
            mode=mode,
            label=HIDDEN_TARGET,
        ),
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return shim


def _run_loop(tmp_path: Path, *extra: str, mode: str = "red_then_green"):
    shim = _write_fake_bazel(tmp_path, mode)
    out = tmp_path / "loop-out"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "loop",
            "--scenario", "two-act-underspec",
            "--mode", "cache-only",
            "--skip-nativelink",
            "--no-remote-cache",
            "--claude-bin", str(STUB_CLAUDE),
            "--bazel-bin", str(shim),
            "--run-group-prefix", "looptest",
            "--output-dir", str(out),
            *extra,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, out


def test_loop_red_then_green_closes_the_loop(tmp_path: Path) -> None:
    result, out = _run_loop(tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout

    summary = json.loads((out / "loop-summary.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == "nlfr.loop.v1"
    assert summary["outcome"] == "fixed_and_green"
    assert summary["source_kind"] == "derived_v1"

    iterations = summary["iterations"]
    assert len(iterations) == 2
    assert iterations[0]["run_group"] == "looptest-iter1"
    assert iterations[0]["status"] == "failed"
    assert iterations[0]["action_taken"] == "dispatch_fix_with_evidence"
    assert iterations[0]["provenance_class"] == "stub_receipt_v1"
    assert iterations[1]["status"] == "completed"
    assert iterations[1]["action_taken"] == "none_complete"

    checks = summary["checks"]
    assert checks["first_iteration_red"] is True
    assert checks["honest_classification"] is True
    assert checks["fix_receipt_present"] is True
    assert checks["final_green"] is True
    assert checks["compare_exported"] is True
    assert isinstance(checks["warm_cache_final"], bool)

    # The fix actually landed: the stub's act-2 module carries the second window.
    fixed = (out / "workspace" / "tasks" / "escalation.py").read_text(encoding="utf-8")
    assert "SECOND_STALENESS_WINDOW" in fixed

    # Per-iteration verdicts were recorded INTO the evidence DB (loop closure).
    conn = connect(out / "nlfr.sqlite")
    count = conn.execute(
        "SELECT COUNT(*) FROM proof_blocks WHERE block_kind = 'evaluation'"
    ).fetchone()[0]
    assert count == 2
    conn.close()

    compare_path = out / "projections" / "compare-looptest-iter1-vs-looptest-iter2.json"
    assert compare_path.exists()
    compare = json.loads(compare_path.read_text(encoding="utf-8"))
    assert compare["projection_kind"] == "compare"

    # Verdict files exported per iteration, derived_v1, with the excerpt handed on.
    verdict1 = json.loads((out / "verdicts" / "iter1-verdict.json").read_text())
    assert verdict1["next_steps"][0]["action"] == "dispatch_fix_with_evidence"
    assert verdict1["failure_evidence"]["excerpt_sha256"]

    # No raw prompt text may land anywhere under the output dir.
    stitched = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in out.rglob("*")
        if path.is_file() and path.suffix in {".json", ".md", ".txt"}
    )
    assert "You are a coding agent" not in stitched


def test_loop_toolchain_red_blocks_without_dispatch(tmp_path: Path) -> None:
    result, out = _run_loop(tmp_path, mode="toolchain")
    assert result.returncode == 2, result.stderr + result.stdout

    blocker = json.loads((out / "loop-blocker.json").read_text(encoding="utf-8"))
    assert blocker["schema_version"] == "nlfr.loop.blocker.v1"
    assert "toolchain" in blocker["reason"]

    summary = json.loads((out / "loop-summary.json").read_text(encoding="utf-8"))
    assert summary["outcome"] == "blocked"
    assert len(summary["iterations"]) == 1
    assert summary["iterations"][0]["action_taken"] == "record_environment_blocker"

    # The fake bazel ran exactly once: no fix was dispatched into a broken env.
    state = (tmp_path / "fake-bazel-state.txt").read_text()
    assert state.strip() == "1"


def test_loop_iteration_cap_exits_one(tmp_path: Path) -> None:
    result, out = _run_loop(tmp_path, "--max-iterations", "1")
    assert result.returncode == 1, result.stderr + result.stdout
    summary = json.loads((out / "loop-summary.json").read_text(encoding="utf-8"))
    assert summary["outcome"] == "iteration_cap_red"
    assert len(summary["iterations"]) == 1
    assert summary["checks"]["final_green"] is False


def test_loop_refuses_nonempty_output_dir(tmp_path: Path) -> None:
    out = tmp_path / "loop-out"
    out.mkdir()
    (out / "stale.txt").write_text("prior run debris\n", encoding="utf-8")
    result, _ = _run_loop(tmp_path)
    assert result.returncode == 2
    assert "not empty" in result.stderr
    assert "Traceback" not in result.stderr


def test_loop_blocks_honestly_when_run_emits_no_metadata(tmp_path: Path) -> None:
    # `nlfr run --mode <bogus>` is an argparse error: rc 2, empty stdout. The
    # loop must emit a blocker, not a traceback.
    result, out = _run_loop(tmp_path, "--mode", "definitely-bogus")
    assert result.returncode == 2, result.stderr + result.stdout
    assert "Traceback" not in result.stderr
    blocker = json.loads((out / "loop-blocker.json").read_text(encoding="utf-8"))
    assert "no run metadata" in blocker["reason"]


def test_loop_resolves_relative_tool_paths(tmp_path: Path) -> None:
    # Found live: agent-invoke execs the CLI from a scratch cwd, so a relative
    # --claude-bin must be absolutized by the loop before dispatch.
    shim = _write_fake_bazel(tmp_path, "red_then_green")
    out = tmp_path / "loop-out-rel"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "loop",
            "--scenario", "two-act-underspec",
            "--mode", "cache-only",
            "--skip-nativelink",
            "--no-remote-cache",
            "--claude-bin", "scripts/spark-stub-claude.sh",
            "--bazel-bin", str(shim),
            "--run-group-prefix", "relbin",
            "--output-dir", str(out),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    summary = json.loads((out / "loop-summary.json").read_text(encoding="utf-8"))
    assert summary["outcome"] == "fixed_and_green"


def test_loop_help_registered() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "nlfr", "loop", "--help"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    for flag in ("--scenario", "--max-iterations", "--claude-bin", "--bazel-bin"):
        assert flag in result.stdout
