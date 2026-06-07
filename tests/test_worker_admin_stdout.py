import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_invocation, upsert_proof_block, upsert_run
from nlfr.ingest.worker_admin_stdout import parse_worker_admin_stdout
from nlfr.projectors import export_action_graph, export_proof_packet


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "worker-admin"
BAZEL_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "bazel"


def _run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_parse_worker_admin_stdout_extracts_identity_lines() -> None:
    events = parse_worker_admin_stdout(
        FIXTURE_ROOT / "nativelink.stdout.txt",
        evidence_ref="collectable_v1:nativelink.stdout.txt",
    )

    assert len(events) == 2
    assert events[0].worker_name == "worker-demo-alpha"
    assert events[0].line_number == 2
    assert events[0].evidence_ref == "collectable_v1:nativelink.stdout.txt"
    assert events[1].worker_name == "worker-demo-beta"
    assert events[1].line_number == 3


def test_parse_worker_admin_stdout_ignores_unmatched_lines(tmp_path) -> None:
    path = tmp_path / "nativelink.stdout.txt"
    path.write_text(
        "INFO server ready\n"
        "DEBUG unrelated worker log\n"
    )

    assert parse_worker_admin_stdout(path) == []


def test_ingest_command_creates_worker_admin_identity_proof_block(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    shutil.copy(BAZEL_FIXTURE_ROOT / "bep.jsonl", artifact_root / "bazel.bep.json")
    shutil.copy(
        BAZEL_FIXTURE_ROOT / "execution-log.json",
        artifact_root / "bazel.execution-log.json",
    )
    shutil.copy(
        FIXTURE_ROOT / "nativelink.stdout.txt",
        artifact_root / "nativelink.stdout.txt",
    )
    (artifact_root / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_worker_admin",
                "run_key": "worker-evidence:fixture",
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
    assert payload["counts"]["proof_blocks"] == 1

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        block = conn.execute("SELECT * FROM proof_blocks").fetchone()

    assert block["block_kind"] == "worker_admin_identity_v1"
    assert block["source_kind"] == "collectable_v1"
    stored_payload = json.loads(block["payload"])
    assert len(stored_payload["events"]) == 2
    assert stored_payload["events"][0]["worker_name"] == "worker-demo-alpha"


def test_ingest_skips_worker_admin_proof_block_without_identity_lines(tmp_path) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    shutil.copy(BAZEL_FIXTURE_ROOT / "bep.jsonl", artifact_root / "bazel.bep.json")
    (artifact_root / "nativelink.stdout.txt").write_text("INFO server ready\n")

    result = _run_nlfr(
        "ingest",
        str(artifact_root),
        "--database",
        str(database_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"].get("proof_blocks", 0) == 0


def test_projections_promote_worker_identity_when_direct_rows_exist(tmp_path) -> None:
    conn = initialize(connect(tmp_path / "nlfr.sqlite"))
    run_id = upsert_run(
        conn,
        stable_key="run:worker-evidence",
        run_group="worker-evidence",
        scenario="worker-evidence-proof",
        mode="local-exec",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:nativelink.stdout.txt"],
        redaction_state="safe",
    )
    upsert_invocation(
        conn,
        stable_key="invocation:worker-evidence:bazel",
        run_id=run_id,
        invocation_kind="bazel",
        command=[
            "bazel",
            "test",
            "//tasks:priority_test",
            "--remote_executor=grpc://127.0.0.1:50051",
        ],
        cwd=tmp_path,
        exit_code=0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:bazel.stdout.txt"],
        redaction_state="safe",
    )
    events = parse_worker_admin_stdout(
        FIXTURE_ROOT / "nativelink.stdout.txt",
        evidence_ref="collectable_v1:nativelink.stdout.txt",
    )
    upsert_proof_block(
        conn,
        stable_key="run:worker-evidence:proof:worker-admin-identity",
        run_id=run_id,
        block_key="worker-admin-identity",
        block_kind="worker_admin_identity_v1",
        title="Worker Admin Identity",
        summary="fixture worker identity",
        payload={
            "events": [
                {
                    "worker_name": event.worker_name,
                    "line_number": event.line_number,
                    "evidence_ref": event.evidence_ref,
                }
                for event in events
            ]
        },
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["collectable_v1:nativelink.stdout.txt"],
        redaction_state="safe",
    )

    graph = export_action_graph(conn, run_group="worker-evidence")
    proof = export_proof_packet(conn, run_group="worker-evidence")

    worker_nodes = [node for node in graph["nodes"] if node["kind"] == "worker"]
    assert len(worker_nodes) == 2
    assert {node["label"] for node in worker_nodes} == {
        "worker-demo-alpha",
        "worker-demo-beta",
    }
    assert all(node["source_kind"] == "collectable_v1" for node in worker_nodes)
    assert any(edge["kind"] == "observed_worker_identity" for edge in graph["edges"])

    config = next(
        node for node in graph["nodes"] if node["kind"] == "remote_execution_config"
    )
    assert config["payload"]["worker_identity_observed"] is True
    assert "worker_identity" not in config["payload"]["unsupported_claims"]
    assert "scheduler_assignment" in config["payload"]["unsupported_claims"]

    remote_block = next(block for block in proof["blocks"] if block["id"] == "remote_execution")
    assert remote_block["metrics"]["worker_identity_observed"] is True
    assert "worker_identity" not in remote_block["payload"]["unsupported_claims"]
    assert any(
        block["kind"] == "worker_admin_identity_v1" for block in proof["blocks"]
    )
