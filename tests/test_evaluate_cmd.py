"""`nlfr evaluate` command: verdict export, exit codes, --record proof block.

CLI-boundary tests for the evaluator: exit-code contract (0 evaluated, 1 only
behind --fail-on-action-required, 2 cannot-evaluate), output routing, and the
--record path that writes the verdict back into the evidence DB as an
idempotent `evaluation` proof block — the reasoning becoming flight-recorder
evidence is the loop-closure claim, so it gets its own tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_failure, upsert_run, upsert_target
from nlfr.projectors.proof import export_proof_packet

ROOT = Path(__file__).resolve().parents[1]
RUN_GROUP = "evaluate-cmd-test"


def run_nlfr(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _seed(db_path: Path, *, failed: bool) -> None:
    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{RUN_GROUP}",
        run_group=RUN_GROUP,
        scenario="loop-test",
        mode="cache-only",
        status="failed" if failed else "completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{RUN_GROUP}"],
        redaction_state="safe",
    )
    upsert_target(
        conn,
        stable_key=f"target:{RUN_GROUP}",
        run_id=run_id,
        label="//tasks:example_test",
        target_kind="py_test",
        status="FAILED" if failed else "PASSED",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["bep:target-completed"],
        redaction_state="safe",
    )
    if failed:
        upsert_failure(
            conn,
            stable_key=f"failure:{RUN_GROUP}:0",
            run_id=run_id,
            failure_kind="target_completed",
            message="//tasks:example_test completed unsuccessfully",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["bep:failure"],
            redaction_state="safe",
        )
    conn.commit()
    conn.close()


def test_evaluate_streams_verdict_json(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=False)
    result = run_nlfr("evaluate", "--db", str(db), "--run-group", RUN_GROUP)
    assert result.returncode == 0
    verdict = json.loads(result.stdout)
    assert verdict["schema_version"] == "nlfr.evaluation.v1"
    assert verdict["next_steps"][0]["action"] == "none_complete"


def test_evaluate_red_still_exits_zero_without_flag(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=True)
    result = run_nlfr("evaluate", "--db", str(db), "--run-group", RUN_GROUP)
    assert result.returncode == 0
    verdict = json.loads(result.stdout)
    assert verdict["status"]["status"] == "failed"


def test_fail_on_action_required_gates_exit_code(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=True)
    red = run_nlfr(
        "evaluate", "--db", str(db), "--run-group", RUN_GROUP,
        "--fail-on-action-required",
    )
    assert red.returncode == 1

    green_db = tmp_path / "green" / "nlfr.sqlite"
    green_db.parent.mkdir()
    _seed(green_db, failed=False)
    green = run_nlfr(
        "evaluate", "--db", str(green_db), "--run-group", RUN_GROUP,
        "--fail-on-action-required",
    )
    assert green.returncode == 0


def test_missing_db_and_missing_group_exit_two(tmp_path: Path) -> None:
    missing = run_nlfr("evaluate", "--db", str(tmp_path / "absent.sqlite"))
    assert missing.returncode == 2
    assert missing.stderr.strip()
    assert "Traceback" not in missing.stderr

    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=False)
    unknown = run_nlfr("evaluate", "--db", str(db), "--run-group", "no-such-group")
    assert unknown.returncode == 2
    assert "no-such-group" in unknown.stderr
    assert "Traceback" not in unknown.stderr


def test_output_writes_json_file(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=False)
    out = tmp_path / "projections" / "evaluate.json"
    result = run_nlfr(
        "evaluate", "--db", str(db), "--run-group", RUN_GROUP,
        "--output", str(out),
    )
    assert result.returncode == 0
    verdict = json.loads(out.read_text(encoding="utf-8"))
    assert verdict["run_group"] == RUN_GROUP


def test_markdown_format_writes_sidecar(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=True)
    out = tmp_path / "evaluate.md"
    result = run_nlfr(
        "evaluate", "--db", str(db), "--run-group", RUN_GROUP,
        "--format", "markdown", "--output", str(out),
    )
    assert result.returncode == 0
    markdown = out.read_text(encoding="utf-8")
    assert "Evaluation verdict" in markdown
    assert "next step" in markdown.lower()
    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == "nlfr.evaluation.v1"


def test_record_writes_idempotent_evaluation_block(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db, failed=True)
    for _ in range(2):
        result = run_nlfr(
            "evaluate", "--db", str(db), "--run-group", RUN_GROUP, "--record"
        )
        assert result.returncode == 0

    conn = connect(db)
    count = conn.execute(
        "SELECT COUNT(*) FROM proof_blocks WHERE block_kind = 'evaluation'"
    ).fetchone()[0]
    assert count == 1
    packet = export_proof_packet(conn, run_group=RUN_GROUP)
    evaluation_blocks = [b for b in packet["blocks"] if b.get("kind") == "evaluation"]
    assert len(evaluation_blocks) == 1
    payload = evaluation_blocks[0]["payload"]
    assert payload["schema_version"] == "nlfr.evaluation.v1"
    assert evaluation_blocks[0]["source_kind"] == "derived_v1"
    conn.close()
