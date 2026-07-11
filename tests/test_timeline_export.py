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


def _verdict_payload(ts: str, status: str, action: str, group: str = "loop-iter1") -> dict:
    return {
        "schema_version": "nlfr.evaluation.v1",
        "generated_at": ts,
        "run_group": group,
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
        payload=_verdict_payload(f"2026-07-11T0{base_hour}:10:00Z", status, action, group),
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
                "run_group": group,
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
    assert projection["redaction_state"] == "redacted"  # rolled up, not hardcoded


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
    assert chapter["lineage"] == "selfheal"
    assert chapter["source_kind"] == "derived_v1"
    # the chapter spans a redacted receipt event — the rollup must say so
    assert chapter["redaction_state"] == "redacted"


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


def test_unrelated_lineage_green_never_closes_anothers_dispatch(tmp_path: Path) -> None:
    """The cross-contamination attack from review: featureA dispatches and never
    goes green; featureB (unrelated) passes later. featureB's green must NOT
    close featureA's chapter — it stays honestly open."""

    db = tmp_path / "mixed" / "nlfr.sqlite"
    db.parent.mkdir()
    conn = initialize(connect(db))
    a_run = upsert_run(
        conn, stable_key="run:featureA", run_group="featureA",
        scenario="loop", mode="cache-only", status="failed",
        started_at="2026-07-11T10:00:00Z",
        source_kind="collectable_v1", confidence="high",
        evidence_refs=["run:featureA"], redaction_state="safe",
    )
    upsert_proof_block(
        conn, stable_key=f"{a_run}:evaluation", run_id=a_run,
        block_key="evaluation", block_kind="evaluation",
        title="Evaluation verdict", summary="status=failed",
        payload={
            "schema_version": "nlfr.evaluation.v1",
            "generated_at": "2026-07-11T10:05:00Z",
            "run_group": "featureA",
            "status": {"status": "failed", "failure_count": 1},
            "classification": {"classification": "scenario_validation_failure"},
            "next_steps": [{"action": "dispatch_fix_with_evidence"}],
        },
        source_kind="derived_v1", confidence="medium",
        evidence_refs=["run-group:featureA"], redaction_state="safe",
    )
    b_run = upsert_run(
        conn, stable_key="run:featureB", run_group="featureB",
        scenario="record", mode="cache-only", status="completed",
        started_at="2026-07-11T10:20:00Z",
        source_kind="collectable_v1", confidence="high",
        evidence_refs=["run:featureB"], redaction_state="safe",
    )
    upsert_proof_block(
        conn, stable_key=f"{b_run}:evaluation", run_id=b_run,
        block_key="evaluation", block_kind="evaluation",
        title="Evaluation verdict", summary="status=ok",
        payload={
            "schema_version": "nlfr.evaluation.v1",
            "generated_at": "2026-07-11T10:30:00Z",
            "run_group": "featureB",
            "status": {"status": "ok", "failure_count": 0},
            "classification": {"classification": "first_pass_success"},
            "next_steps": [{"action": "none_complete"}],
        },
        source_kind="derived_v1", confidence="medium",
        evidence_refs=["run-group:featureB"], redaction_state="safe",
    )
    conn.commit()
    conn.close()
    ro = connect_readonly(db)
    try:
        projection = build_timeline_projection([("mixed", ro)])
    finally:
        ro.close()
    chapters = projection["chapters"]
    assert len(chapters) == 1
    assert chapters[0]["lineage"] == "featureA"
    assert chapters[0]["open"] is True
    assert chapters[0]["end_ts"] is None


def test_second_dispatch_supersedes_as_its_own_open_beat(tmp_path: Path) -> None:
    """Two dispatches in one lineage before a green: the first attempt stays an
    honestly open chapter (no green ever closed IT); the second is its own
    beat, closed by the lineage's green."""

    red = tmp_path / "r" / "nlfr.sqlite"
    red2 = tmp_path / "r2" / "nlfr.sqlite"
    green = tmp_path / "g" / "nlfr.sqlite"
    for path in (red, red2, green):
        path.parent.mkdir()
    _seed(red, group="heal-red", base_hour=1)

    conn = initialize(connect(red2))
    run_id = upsert_run(
        conn, stable_key="run:heal-red-r2", run_group="heal-red-r2",
        scenario="loop", mode="cache-only", status="failed",
        started_at="2026-07-11T01:30:00Z",
        source_kind="collectable_v1", confidence="high",
        evidence_refs=["run:heal-red-r2"], redaction_state="safe",
    )
    upsert_proof_block(
        conn, stable_key=f"{run_id}:evaluation", run_id=run_id,
        block_key="evaluation", block_kind="evaluation",
        title="Evaluation verdict", summary="status=failed",
        payload={
            "schema_version": "nlfr.evaluation.v1",
            "generated_at": "2026-07-11T01:40:00Z",
            "run_group": "heal-red-r2",
            "status": {"status": "failed", "failure_count": 1},
            "classification": {"classification": "scenario_validation_failure"},
            "next_steps": [{"action": "dispatch_fix_with_evidence"}],
        },
        source_kind="derived_v1", confidence="medium",
        evidence_refs=["run-group:heal-red-r2"], redaction_state="safe",
    )
    conn.commit()
    conn.close()
    _seed(green, group="heal-green", base_hour=2)

    sources = [
        ("r", connect_readonly(red)),
        ("r2", connect_readonly(red2)),
        ("g", connect_readonly(green)),
    ]
    try:
        projection = build_timeline_projection(sources)
    finally:
        for _, ro in sources:
            ro.close()
    chapters = projection["chapters"]
    assert len(chapters) == 2
    assert [chapter["lineage"] for chapter in chapters] == ["heal", "heal"]
    first, second = chapters
    assert first["open"] is True and first["end_ts"] is None
    assert second["open"] is False and second["end_ts"] == "2026-07-11T02:10:00Z"


def test_zero_event_projection_is_contract_valid(tmp_path: Path) -> None:
    import jsonschema

    db = tmp_path / "empty" / "nlfr.sqlite"
    db.parent.mkdir()
    conn = initialize(connect(db))
    conn.commit()
    conn.close()
    ro = connect_readonly(db)
    try:
        projection = build_timeline_projection([("empty", ro)])
    finally:
        ro.close()
    assert projection["summary"]["events"] == 0
    assert projection["span"] == {"start": None, "end": None}
    assert projection["chapters"] == []
    contract = json.loads((ROOT / "contracts" / "timeline_projection.v1.json").read_text())
    jsonschema.Draft202012Validator(contract).validate(projection)


def test_identical_timestamps_keep_stable_indexes(tmp_path: Path) -> None:
    db = tmp_path / "same-ts" / "nlfr.sqlite"
    db.parent.mkdir()
    conn = initialize(connect(db))
    for name in ("alpha", "beta"):
        upsert_run(
            conn, stable_key=f"run:{name}", run_group=name,
            scenario="record", mode="cache-only", status="completed",
            started_at="2026-07-11T05:00:00Z",
            source_kind="collectable_v1", confidence="high",
            evidence_refs=[f"run:{name}"], redaction_state="safe",
        )
    conn.commit()
    conn.close()
    ro = connect_readonly(db)
    try:
        projection = build_timeline_projection([("same-ts", ro)])
    finally:
        ro.close()
    assert [event["index"] for event in projection["events"]] == [0, 1]
    assert projection["summary"]["events"] == 2


def test_cli_db_and_db_root_overlap_deduplicates(tmp_path: Path) -> None:
    root = tmp_path / "record-root"
    (root / "groupA").mkdir(parents=True)
    (root / "groupB").mkdir(parents=True)
    _seed(root / "groupA" / "nlfr.sqlite", group="groupA-red", base_hour=1)
    _seed(root / "groupB" / "nlfr.sqlite", group="groupB-green", base_hour=2)
    out = tmp_path / "timeline.json"
    result = run_nlfr(
        "timeline", "export",
        "--db", str(root / "groupA" / "nlfr.sqlite"),
        "--db-root", str(root),
        "--output", str(out),
    )
    assert result.returncode == 0, result.stderr
    projection = json.loads(out.read_text(encoding="utf-8"))
    # groupA passed twice (explicit + discovered) must count once
    assert sorted(projection["sources"]) == ["groupA", "groupB"]
    assert projection["summary"]["runs"] == 2
