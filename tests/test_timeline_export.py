"""Timeline projection: the replayable flight record (`nlfr timeline export`).

The canvas Replay lens renders only this projection, so these tests pin its
honesty guarantees: events copy the truth quad from the rows/blocks they were
read from, timestamps are recorded ones, repair-loop chapters are derived
purely from verdict events (a dispatch with no green close stays honestly
``open``), multi-database merges keep per-event source labels, and the whole
payload is redact-clean.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_proof_block, upsert_run
from nlfr.db.connection import connect_readonly
from nlfr.projectors.timeline import build_timeline_projection

ROOT = Path(__file__).resolve().parents[1]


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


def _verdict_payload(ts: str, status: str, action: str) -> dict:
    return {
        "schema_version": "nlfr.evaluation.v1",
        "generated_at": ts,
        "run_group": "loop-iter1",
        "status": {"status": status, "failure_count": 0 if status == "ok" else 1},
        "classification": {"classification": "scenario_validation_failure"},
        "next_steps": [{"action": action}],
    }


def _seed(db_path: Path, *, group: str, base_hour: int) -> None:
    conn = initialize(connect(db_path))
    run_id = upsert_run(
        conn,
        stable_key=f"run:{group}",
        run_group=group,
        scenario="loop",
        mode="cache-only",
        status="failed" if base_hour == 1 else "completed",
        started_at=f"2026-07-11T0{base_hour}:00:00Z",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{group}"],
        redaction_state="safe",
    )
    action = "dispatch_fix_with_evidence" if base_hour == 1 else "none_complete"
    status = "failed" if base_hour == 1 else "ok"
    upsert_proof_block(
        conn,
        stable_key=f"{run_id}:evaluation",
        run_id=run_id,
        block_key="evaluation",
        block_kind="evaluation",
        title="Evaluation verdict",
        summary=f"status={status}",
        payload=_verdict_payload(f"2026-07-11T0{base_hour}:10:00Z", status, action),
        source_kind="derived_v1",
        confidence="medium",
        evidence_refs=[f"run-group:{group}"],
        redaction_state="safe",
    )
    if base_hour == 1:
        upsert_proof_block(
            conn,
            stable_key=f"{run_id}:agent-receipt",
            run_id=run_id,
            block_key="agent-provenance",
            block_kind="agent_provenance",
            title="Agent provenance",
            summary="receipted fix",
            payload={
                "schema_version": "nlfr.agent_provenance.v1",
                "generated_at": f"2026-07-11T0{base_hour}:20:00Z",
                "agent": {
                    "name": "loop-fix",
                    "model": "claude-fable-5",
                    "provenance_class": "receipt_verified_v1",
                    "prompt_sha256": "a" * 64,
                    "receipt": {
                        "captured_at": f"2026-07-11T0{base_hour}:20:00Z",
                        "model_resolved": "claude-fable-5",
                        "status": "success",
                        "session_id": "sess-1",
                        "usage": {"output_tokens": 111},
                    },
                },
            },
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=["receipt:sha256:" + "b" * 64],
            redaction_state="redacted",
        )
    conn.commit()
    conn.close()


def _projection(tmp_path: Path) -> dict:
    red = tmp_path / "red" / "nlfr.sqlite"
    green = tmp_path / "green" / "nlfr.sqlite"
    red.parent.mkdir()
    green.parent.mkdir()
    _seed(red, group="selfheal-red", base_hour=1)
    _seed(green, group="selfheal-green", base_hour=2)
    sources = [
        ("red", connect_readonly(red)),
        ("green", connect_readonly(green)),
    ]
    try:
        return build_timeline_projection(sources)
    finally:
        for _, conn in sources:
            conn.close()


def test_events_merge_chronologically_with_source_labels(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    assert projection["projection_kind"] == "timeline"
    kinds = [event["kind"] for event in projection["events"]]
    assert kinds == ["run", "verdict", "receipt", "run", "verdict"]
    timestamps = [event["ts"] for event in projection["events"]]
    assert timestamps == sorted(timestamps)
    assert [event["index"] for event in projection["events"]] == list(range(5))
    assert projection["events"][0]["source"] == "red"
    assert projection["events"][3]["source"] == "green"
    assert projection["summary"] == {
        "events": 5,
        "runs": 2,
        "verdicts": 2,
        "receipts": 1,
        "repair_loops": 1,
    }


def test_events_copy_truth_labels_from_rows(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    run_event = projection["events"][0]
    assert run_event["source_kind"] == "collectable_v1"
    assert run_event["confidence"] == "high"
    verdict_event = projection["events"][1]
    assert verdict_event["source_kind"] == "derived_v1"
    receipt_event = projection["events"][2]
    assert receipt_event["detail"]["provenance_class"] == "receipt_verified_v1"
    assert receipt_event["detail"]["output_tokens"] == 111
    assert projection["source_kind"] == "derived_v1"


def test_repair_chapter_spans_dispatch_to_green(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    chapters = projection["chapters"]
    assert len(chapters) == 1
    chapter = chapters[0]
    assert chapter["kind"] == "repair_loop"
    assert chapter["open"] is False
    assert chapter["start_ts"] == "2026-07-11T01:10:00Z"
    assert chapter["end_ts"] == "2026-07-11T02:10:00Z"
    # dispatch verdict, the receipt + green run between, the closing verdict
    assert chapter["event_indexes"] == [1, 2, 3, 4]
    assert chapter["source_kind"] == "derived_v1"


def test_dispatch_without_green_close_stays_open(tmp_path: Path) -> None:
    db = tmp_path / "only-red" / "nlfr.sqlite"
    db.parent.mkdir()
    _seed(db, group="selfheal-red", base_hour=1)
    conn = connect_readonly(db)
    try:
        projection = build_timeline_projection([("only-red", conn)])
    finally:
        conn.close()
    assert len(projection["chapters"]) == 1
    assert projection["chapters"][0]["open"] is True
    assert projection["chapters"][0]["end_ts"] is None


def test_projection_is_redact_clean_and_contract_valid(tmp_path: Path) -> None:
    import jsonschema

    projection = _projection(tmp_path)
    assert "/Users/" not in json.dumps(projection)
    contract = json.loads((ROOT / "contracts" / "timeline_projection.v1.json").read_text())
    jsonschema.Draft202012Validator(contract).validate(projection)


def test_cli_export_merges_db_root(tmp_path: Path) -> None:
    root = tmp_path / "record-root"
    (root / "selfheal-red").mkdir(parents=True)
    (root / "selfheal-green").mkdir(parents=True)
    _seed(root / "selfheal-red" / "nlfr.sqlite", group="selfheal-red", base_hour=1)
    _seed(root / "selfheal-green" / "nlfr.sqlite", group="selfheal-green", base_hour=2)
    out = tmp_path / "timeline.json"
    result = run_nlfr(
        "timeline", "export", "--db-root", str(root), "--output", str(out)
    )
    assert result.returncode == 0, result.stderr
    projection = json.loads(out.read_text(encoding="utf-8"))
    assert projection["summary"]["events"] == 5
    assert projection["summary"]["repair_loops"] == 1
    assert sorted(projection["sources"]) == ["selfheal-green", "selfheal-red"]


def test_cli_missing_db_exits_two(tmp_path: Path) -> None:
    result = run_nlfr("timeline", "export", "--db", str(tmp_path / "absent.sqlite"))
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
