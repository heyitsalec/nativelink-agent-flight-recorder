import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run
from nlfr.ingest.bazel import (
    parse_bazel_bep,
    parse_bazel_execution_log,
    parse_bazel_profile,
)
from nlfr.ingest.sqlite import ingest_evidence_bundle
from nlfr.projectors import export_proof_packet


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "bazel"
WORKER_ADMIN_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "worker-admin"


def _stage_bazel_artifact_fixtures(artifact_root: Path) -> None:
    artifact_root.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_ROOT / "bep.jsonl", artifact_root / "bazel.bep.json")
    shutil.copy(
        FIXTURE_ROOT / "execution-log.json",
        artifact_root / "bazel.execution-log.json",
    )


def test_parse_bep_extracts_targets_actions_test_results_and_failures() -> None:
    bundle = parse_bazel_bep(
        FIXTURE_ROOT / "bep.jsonl",
        source_kind="simulated_v1",
        evidence_ref="fixture:simulated_v1:bep.jsonl",
    )

    targets = {target.label: target for target in bundle.targets}
    assert targets["//tasks:priority_test"].target_kind == "py_test rule"
    assert targets["//tasks:priority_test"].status == "PASSED"
    assert targets["//tasks:flaky_test"].status == "FAILED"
    assert targets["//tasks:flaky_test"].source_kind == "simulated_v1"
    assert targets["//tasks:flaky_test"].confidence == "high"

    actions = {action.action_key: action for action in bundle.actions}
    assert (
        "//tasks:priority_test:test:run=1:shard=1:attempt=1" in actions
    )
    assert actions["//tasks:priority_test:test:run=1:shard=1:attempt=1"].status == "PASSED"
    assert actions["//tasks:priority_test:action:1"].mnemonic == "PythonTestSetup"

    assert len(bundle.failures) == 2
    messages = {failure.message for failure in bundle.failures}
    assert any("expected stable priority ordering" in message for message in messages)
    assert any("Bazel finished with TESTS_FAILED" in message for message in messages)
    assert all(
        "fixture:simulated_v1:bep.jsonl" in failure.evidence_refs
        for failure in bundle.failures
    )


def test_parse_execution_log_extracts_cache_events_with_fixture_truth_labels() -> None:
    bundle = parse_bazel_execution_log(
        FIXTURE_ROOT / "execution-log.json",
        source_kind="simulated_v1",
        evidence_ref="fixture:simulated_v1:execution-log.json",
    )

    events = {event.event_key: event for event in bundle.cache_events}
    hit = events["//tasks:priority_test:PyTest:sha256:1111222233334444"]
    miss = events["//tasks:flaky_test:PyTest:sha256:aaaabbbbccccdddd"]

    assert hit.event_kind == "remote_cache_hit"
    assert hit.hit is True
    assert hit.source_kind == "simulated_v1"
    assert hit.confidence == "high"
    assert miss.event_kind == "cache_miss"
    assert miss.hit is False


def test_parse_profile_derives_cache_events_with_medium_confidence() -> None:
    bundle = parse_bazel_profile(
        FIXTURE_ROOT / "profile.json",
        evidence_ref="fixture:simulated_v1:profile.json",
    )

    events = {event.event_key: event for event in bundle.cache_events}
    hit = events["profile://tasks:priority_test:PyTest:sha256:1111222233334444"]
    placeholder = events["profile://tasks:flaky_test:PyTest:202"]

    assert hit.event_kind == "remote_cache_hit"
    assert hit.hit is True
    assert hit.source_kind == "derived_v1"
    assert hit.confidence == "medium"
    assert placeholder.event_kind == "action_cache_observed"
    assert placeholder.hit is None
    assert placeholder.source_kind == "derived_v1"
    assert placeholder.confidence == "low"


def test_ingest_evidence_bundle_preserves_truth_labels_and_evidence_refs(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="fixture-run:cache-only",
        run_group="fixture",
        scenario="fixture-run",
        mode="cache-only",
        status="completed",
        source_kind="simulated_v1",
        confidence="high",
        evidence_refs=["fixture:simulated_v1"],
        redaction_state="safe",
    )

    bundle = parse_bazel_bep(
        FIXTURE_ROOT / "bep.jsonl",
        source_kind="simulated_v1",
        evidence_ref="fixture:simulated_v1:bep.jsonl",
    )
    bundle.extend(
        parse_bazel_execution_log(
            FIXTURE_ROOT / "execution-log.json",
            source_kind="simulated_v1",
            evidence_ref="fixture:simulated_v1:execution-log.json",
        )
    )
    counts = ingest_evidence_bundle(
        conn,
        run_id=run_id,
        run_stable_key="fixture-run:cache-only",
        bundle=bundle,
    )

    assert counts == {
        "targets": 2,
        "actions": 3,
        "cache_events": 2,
        "failures": 2,
        # Both testActionOutput logs point at file:///tmp/... paths that do not
        # exist on the test host, so honest verification marks them missing.
        "artifact_references": 2,
    }

    references = conn.execute(
        "SELECT reference_key, presence, digest_verified, source_kind, confidence "
        "FROM artifact_references ORDER BY reference_key"
    ).fetchall()
    assert {row["presence"] for row in references} == {"missing"}
    assert all(row["digest_verified"] is None for row in references)
    # Missing local files must not carry a high-confidence presence claim; the
    # simulated fixture keeps its simulated_v1 kind but is downgraded to low.
    assert {row["source_kind"] for row in references} == {"simulated_v1"}
    assert {row["confidence"] for row in references} == {"low"}

    target = conn.execute(
        "SELECT source_kind, confidence, evidence_refs, redaction_state "
        "FROM targets WHERE label = ?",
        ("//tasks:flaky_test",),
    ).fetchone()
    assert target["source_kind"] == "simulated_v1"
    assert target["confidence"] == "high"
    assert json.loads(target["evidence_refs"]) == ["fixture:simulated_v1:bep.jsonl"]
    assert target["redaction_state"] == "safe"

    cache_event = conn.execute(
        "SELECT hit, source_kind, confidence, evidence_refs "
        "FROM cache_events WHERE digest = ?",
        ("sha256:1111222233334444",),
    ).fetchone()
    assert cache_event["hit"] == 1
    assert cache_event["source_kind"] == "simulated_v1"
    assert cache_event["confidence"] == "high"
    assert json.loads(cache_event["evidence_refs"]) == [
        "fixture:simulated_v1:execution-log.json"
    ]


def test_ingest_command_loads_fixture_files_into_sqlite(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    result = _run_nlfr(
        "ingest",
        "--database",
        str(database_path),
        "--run-key",
        "fixture-run:cache-only",
        "--bep",
        str(FIXTURE_ROOT / "bep.jsonl"),
        "--execution-log",
        str(FIXTURE_ROOT / "execution-log.json"),
        "--source-kind",
        "simulated_v1",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"]["targets"] == 2
    assert payload["counts"]["cache_events"] == 2

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT source_kind FROM runs").fetchone()
        failure_count = conn.execute("SELECT COUNT(*) AS count FROM failures").fetchone()

    assert run["source_kind"] == "simulated_v1"
    assert failure_count["count"] == 2


def test_ingest_command_attaches_artifact_dir_to_run_metadata(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    conn = initialize(connect(database_path))
    existing_run_id = upsert_run(
        conn,
        stable_key="cold-cache:cache-only:2026-06-06T12:00:00.000000Z",
        run_group="cold-warm",
        scenario="cold-cache",
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["run:existing"],
        redaction_state="safe",
    )

    artifact_root = tmp_path / "runs" / "run_existing" / "artifacts"
    _stage_bazel_artifact_fixtures(artifact_root)
    shutil.copy(FIXTURE_ROOT / "profile.json", artifact_root / "bazel.profile.json")
    (artifact_root / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_existing",
                "run_key": "cold-cache:cache-only:2026-06-06T12:00:00.000000Z",
                "run_group": "cold-warm",
                "scenario": "cold-cache",
                "mode": "cache-only",
                "artifact_root": str(artifact_root),
            }
        )
        + "\n"
    )

    result = _run_nlfr(
        "ingest",
        str(artifact_root),
        "--database",
        str(database_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_id"] == existing_run_id
    assert payload["run_key"] == "cold-cache:cache-only:2026-06-06T12:00:00.000000Z"
    assert payload["run_metadata"]["run_group"] == "cold-warm"
    assert payload["counts"]["targets"] == 2
    assert payload["counts"]["cache_events"] == 4

    with sqlite3.connect(database_path) as verify_conn:
        verify_conn.row_factory = sqlite3.Row
        run_count = verify_conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
        target = verify_conn.execute(
            "SELECT run_id, source_kind FROM targets WHERE label = ?",
            ("//tasks:priority_test",),
        ).fetchone()
        run = verify_conn.execute(
            "SELECT status, run_group, scenario, mode FROM runs WHERE id = ?",
            (existing_run_id,),
        ).fetchone()

    assert run_count["count"] == 1
    assert target["run_id"] == existing_run_id
    assert target["source_kind"] == "collectable_v1"
    assert run["status"] == "completed"
    assert run["run_group"] == "cold-warm"
    assert run["scenario"] == "cold-cache"
    assert run["mode"] == "cache-only"


def test_ingest_command_converts_worker_readiness_to_proof_block(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    artifact_root = tmp_path / "runs" / "run_worker" / "artifacts"
    _stage_bazel_artifact_fixtures(artifact_root)
    (artifact_root / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_worker",
                "run_key": "local-exec-proof:local-exec:2026-06-06T12:00:00.000000Z",
                "run_group": "local-exec",
                "scenario": "local-exec-proof",
                "mode": "local-exec",
                "artifact_root": str(artifact_root),
            }
        )
        + "\n"
    )
    (artifact_root / "worker-readiness.json").write_text(
        json.dumps(
            {
                "status": "worker_endpoints_ready",
                "phase": "ports",
                "expected_workers": 1,
                "configured_workers": 1,
                "source_kind": "collectable_v1",
                "confidence": "high",
                "redaction_state": "safe",
                "evidence_refs": [
                    "config:local-execution.json5",
                    "script:local-exec-proof.sh",
                ],
                "unsupported_claims": [
                    "worker_identity",
                    "action_placement",
                    "queue_time",
                    "scheduler_assignment",
                ],
                "worker_api_endpoints": [
                    {
                        "label": "grpc://127.0.0.1:50061",
                        "fingerprint": "localfingerprint",
                        "redacted": False,
                    }
                ],
            }
        )
        + "\n"
    )

    result = _run_nlfr(
        "ingest",
        str(artifact_root),
        "--database",
        str(database_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"]["proof_blocks"] == 1

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        block = conn.execute("SELECT * FROM proof_blocks").fetchone()
        proof = export_proof_packet(conn, run_group="local-exec")

    assert block["block_key"] == "worker-readiness"
    assert block["block_kind"] == "worker_readiness_boundary"
    assert block["title"] == "Worker Readiness Boundary"
    assert "Worker identity" in block["summary"]
    stored_payload = json.loads(block["payload"])
    assert stored_payload["status"] == "worker_endpoints_ready"
    assert "worker_identity" in stored_payload["unsupported_claims"]

    proof_block = next(
        item for item in proof["blocks"] if item["title"] == "Worker Readiness Boundary"
    )
    assert proof_block["source_kind"] == "collectable_v1"
    assert proof_block["payload"]["status"] == "worker_endpoints_ready"


def test_ingest_command_discovers_nativelink_stdout_with_bazel_fixtures(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    artifact_root = tmp_path / "artifacts"
    _stage_bazel_artifact_fixtures(artifact_root)
    shutil.copy(
        WORKER_ADMIN_FIXTURE_ROOT / "nativelink.stdout.txt",
        artifact_root / "nativelink.stdout.txt",
    )
    (artifact_root / "run.json").write_text(
        json.dumps(
            {
                "run_key": "worker-evidence:local-exec:2026-06-06T12:00:00.000000Z",
                "run_group": "worker-evidence",
                "scenario": "worker-evidence-proof",
                "mode": "local-exec",
                "artifact_root": str(artifact_root),
            }
        )
        + "\n"
    )

    result = _run_nlfr(
        "ingest",
        str(artifact_root),
        "--database",
        str(database_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"]["targets"] == 2
    assert payload["counts"]["proof_blocks"] == 1

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        block = conn.execute("SELECT block_kind FROM proof_blocks").fetchone()

    assert block["block_kind"] == "worker_admin_identity_v1"


def test_ingest_command_rejects_run_metadata_without_bazel_evidence(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "run.json").write_text(
        json.dumps(
            {
                "run_key": "missing-evidence:cache-only:2026-06-06T12:00:00.000000Z",
                "run_group": "cold-warm",
                "scenario": "missing-evidence",
                "mode": "cache-only",
            }
        )
        + "\n"
    )

    result = _run_nlfr(
        "ingest",
        str(artifact_root),
        "--database",
        str(tmp_path / "nlfr.sqlite"),
        "--json",
    )

    assert result.returncode == 2
    assert "no Bazel evidence files found" in result.stderr


def _run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
