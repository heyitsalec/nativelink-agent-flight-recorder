"""Evaluator core: truth-labeled verdicts + next-step reasoning over evidence.

These tests prove the closed-loop "brain" is honest: verdicts are deterministic
functions of recorded evidence, always ``derived_v1`` with weakest-input
confidence, next-step precedence is an explicit tested contract, degraded
inputs (missing logs, unattributed failures) degrade the verdict honestly
instead of guessing, and every payload is redact-clean.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nlfr.db import connect, initialize
from nlfr.db.ingest import (
    upsert_cache_event,
    upsert_change,
    upsert_failure,
    upsert_run,
    upsert_target,
)
from nlfr.evaluator import (
    EVALUATION_SCHEMA_VERSION,
    TOOLCHAIN_FAILURE_SIGNATURES,
    classify_validation_failure,
    evaluate_run_group,
    failure_excerpt,
)
from nlfr.projectors.compare import MissingRunGroupError

RUN_GROUP = "loop-iter1"
HIDDEN_TARGET = "//tasks:escalation_policy_test"
CHANGED_PATH = "tasks/escalation.py"
FIXED_TS = "2026-07-09T00:00:00.000000Z"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed(
    db_path: Path,
    *,
    run_group: str = RUN_GROUP,
    failed: bool = False,
    change_after: str | None = "def escalation_tier():\n    return 1\n",
    low_confidence_row: bool = False,
) -> None:
    """Seed one recorded validation run: target, cache events, optional failure.

    ``change_after`` seeds a recorded agent change whose after-bytes are known,
    so tests can put matching (validated) or different (pending-edit) content
    into a workspace copy.
    """

    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario="two-act-underspec-act1",
        mode="cache-only",
        status="failed" if failed else "completed",
        started_at=FIXED_TS,
        ended_at=FIXED_TS,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    upsert_target(
        conn,
        stable_key=f"target:{run_group}",
        run_id=run_id,
        label=HIDDEN_TARGET,
        target_kind="py_test",
        status="FAILED" if failed else "PASSED",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    upsert_cache_event(
        conn,
        stable_key=f"cache:{run_group}:0",
        run_id=run_id,
        event_key="cache-0",
        event_kind="action_cache",
        hit=False,
        source_kind="collectable_v1",
        confidence="low" if low_confidence_row else "high",
        evidence_refs=["execution-log:test"],
        redaction_state="safe",
    )
    if failed:
        upsert_failure(
            conn,
            stable_key=f"failure:{run_group}:0",
            run_id=run_id,
            failure_kind="target_completed",
            message=f"{HIDDEN_TARGET} completed unsuccessfully",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["bep:target-completed:failure"],
            redaction_state="safe",
        )
    if change_after is not None:
        upsert_change(
            conn,
            stable_key=f"change:{run_group}:0",
            run_id=run_id,
            change_kind="bounded_agent_v1",
            path=CHANGED_PATH,
            before_hash="0" * 64,
            after_hash=_sha256(change_after),
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"change:{CHANGED_PATH}"],
            redaction_state="safe",
        )
    conn.commit()
    conn.close()


def _artifact_root(tmp_path: Path, stderr: str, stdout: str = "") -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    (root / "bazel.stderr.txt").write_text(stderr, encoding="utf-8")
    if stdout:
        (root / "bazel.stdout.txt").write_text(stdout, encoding="utf-8")
    return root


def _evaluate(tmp_path: Path, **kwargs):
    conn = connect(tmp_path / "nlfr.sqlite")
    try:
        return evaluate_run_group(conn, kwargs.pop("run_group", RUN_GROUP), **kwargs)
    finally:
        conn.close()


HONEST_STDERR = (
    "INFO: Analyzed 5 targets\n"
    f"FAIL: {HIDDEN_TARGET} (see /Users/somebody/logs/test.log)\n"
    "AssertionError: expected tier 2 after 60 days\n"
)


def _actions(verdict: dict) -> list[str]:
    return [step["action"] for step in verdict["next_steps"]]


def test_green_run_group_yields_none_complete(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=False)
    verdict = _evaluate(tmp_path)
    assert verdict["schema_version"] == EVALUATION_SCHEMA_VERSION
    assert verdict["status"]["status"] == "ok"
    assert verdict["classification"]["classification"] == "first_pass_success"
    assert _actions(verdict) == ["none_complete"]
    assert verdict["source_kind"] == "derived_v1"
    assert verdict["confidence"] == "high"


def test_red_honest_yields_dispatch_fix_with_evidence(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=True)
    root = _artifact_root(tmp_path, HONEST_STDERR)
    verdict = _evaluate(
        tmp_path, artifact_root=root, attribution_target=HIDDEN_TARGET
    )
    assert verdict["status"]["status"] == "failed"
    classification = verdict["classification"]
    assert classification["classification"] == "scenario_validation_failure"
    assert classification["honest_scenario_failure"] is True
    assert classification["attribution_target_referenced"] is True
    assert _actions(verdict)[0] == "dispatch_fix_with_evidence"
    evidence = verdict["failure_evidence"]
    assert "FAIL" in evidence["excerpt"]
    assert evidence["excerpt_sha256"] == _sha256(evidence["excerpt"])
    step = verdict["next_steps"][0]
    assert step["source_kind"] == "derived_v1"
    assert CHANGED_PATH in step["inputs"]["changed_paths"]
    assert HIDDEN_TARGET in verdict["failures"][0]["attributed_targets"]


def test_toolchain_red_yields_environment_blocker_first(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=True)
    stderr = f"/bin/sh: bazel: command not found\nFAIL: {HIDDEN_TARGET}\n"
    root = _artifact_root(tmp_path, stderr)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / CHANGED_PATH).parent.mkdir(parents=True, exist_ok=True)
    (workspace / CHANGED_PATH).write_text("pending edit\n", encoding="utf-8")
    verdict = _evaluate(
        tmp_path,
        artifact_root=root,
        attribution_target=HIDDEN_TARGET,
        workspace=workspace,
    )
    assert verdict["classification"]["classification"] == "toolchain_failure"
    assert _actions(verdict)[0] == "record_environment_blocker"


def test_red_without_logs_degrades_honestly(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=True)
    verdict = _evaluate(tmp_path, attribution_target=HIDDEN_TARGET)
    classification = verdict["classification"]
    assert classification["classification"] == "unclassified"
    assert classification["reason"] == "raw_logs_unavailable"
    assert verdict["failure_evidence"] is None
    assert _actions(verdict)[0] == "attach_missing_evidence"
    assert "raw_validation_logs" in verdict["next_steps"][0]["inputs"]["missing"]


def test_pending_workspace_edit_outranks_dispatch(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=True)
    root = _artifact_root(tmp_path, HONEST_STDERR)
    workspace = tmp_path / "ws"
    (workspace / CHANGED_PATH).parent.mkdir(parents=True, exist_ok=True)
    (workspace / CHANGED_PATH).write_text("edited but unvalidated\n", encoding="utf-8")
    verdict = _evaluate(
        tmp_path,
        artifact_root=root,
        attribution_target=HIDDEN_TARGET,
        workspace=workspace,
    )
    actions = _actions(verdict)
    assert actions[0] == "rerun_validation"
    assert "dispatch_fix_with_evidence" in actions
    assert actions.index("rerun_validation") < actions.index("dispatch_fix_with_evidence")


def test_validated_workspace_does_not_trigger_rerun(tmp_path: Path) -> None:
    content = "def escalation_tier():\n    return 1\n"
    _seed(tmp_path / "nlfr.sqlite", failed=True, change_after=content)
    root = _artifact_root(tmp_path, HONEST_STDERR)
    workspace = tmp_path / "ws"
    (workspace / CHANGED_PATH).parent.mkdir(parents=True, exist_ok=True)
    (workspace / CHANGED_PATH).write_text(content, encoding="utf-8")
    verdict = _evaluate(
        tmp_path,
        artifact_root=root,
        attribution_target=HIDDEN_TARGET,
        workspace=workspace,
    )
    assert "rerun_validation" not in _actions(verdict)


def test_unattributed_red_requests_attribution(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=True)
    root = _artifact_root(tmp_path, "FAIL: //other:target failed\n")
    verdict = _evaluate(
        tmp_path, artifact_root=root, attribution_target=HIDDEN_TARGET
    )
    classification = verdict["classification"]
    assert classification["classification"] == "unattributed_failure"
    assert classification["attribution_target_referenced"] is False
    assert _actions(verdict)[0] == "attach_missing_evidence"
    assert "failure_attribution" in verdict["next_steps"][0]["inputs"]["missing"]


def test_verdict_is_derived_and_redact_clean(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=True)
    root = _artifact_root(tmp_path, HONEST_STDERR)
    verdict = _evaluate(
        tmp_path, artifact_root=root, attribution_target=HIDDEN_TARGET
    )
    assert verdict["source_kind"] == "derived_v1"
    payload = json.dumps(verdict)
    assert "/Users/" not in payload
    assert verdict["evidence_refs"]


def test_confidence_uses_weakest_consulted_input(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=False, low_confidence_row=True)
    verdict = _evaluate(tmp_path)
    assert verdict["confidence"] == "low"


def test_missing_run_group_raises(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite", failed=False)
    with pytest.raises(MissingRunGroupError):
        _evaluate(tmp_path, run_group="no-such-group")


def test_classify_without_attribution_target(tmp_path: Path) -> None:
    root = _artifact_root(tmp_path, "FAIL: //tasks:something\n")
    result = classify_validation_failure(root)
    assert result["classification"] == "unattributed_failure"
    assert result["attribution_target_referenced"] is None


def test_spark_wrappers_still_delegate(tmp_path: Path) -> None:
    from nlfr import spark

    root = _artifact_root(tmp_path, HONEST_STDERR)
    via_spark = spark.classify_validation_failure(root, hidden_target=HIDDEN_TARGET)
    via_evaluator = classify_validation_failure(
        root, attribution_target=HIDDEN_TARGET
    )
    assert via_spark["classification"] == via_evaluator["classification"]
    assert via_spark["hidden_target_referenced"] is True
    assert spark.TOOLCHAIN_FAILURE_SIGNATURES == TOOLCHAIN_FAILURE_SIGNATURES
    assert spark.failure_excerpt(root) == failure_excerpt(root)
