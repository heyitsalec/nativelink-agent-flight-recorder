"""Fixture-backed local-exec fleet evidence ingest tests."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_invocation
from nlfr.projectors import export_action_graph, export_proof_packet


ROOT = Path(__file__).resolve().parents[1]
WORKER_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "worker-admin"
BAZEL_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "bazel"


def _run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "nlfr", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _build_local_exec_fleet_artifact_root(tmp_path: Path) -> Path:
    artifact_root = tmp_path / "runs" / "run_worker_evidence" / "artifacts"
    artifact_root.mkdir(parents=True)
    shutil.copy(BAZEL_FIXTURE_ROOT / "bep.jsonl", artifact_root / "bazel.bep.json")
    shutil.copy(
        BAZEL_FIXTURE_ROOT / "execution-log.json",
        artifact_root / "bazel.execution-log.json",
    )
    shutil.copy(
        WORKER_FIXTURE_ROOT / "nativelink.stdout.txt",
        artifact_root / "nativelink.stdout.txt",
    )
    (artifact_root / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_worker_evidence",
                "run_key": "worker-evidence:local-exec:2026-06-06T12:00:00.000000Z",
                "run_group": "worker-evidence",
                "scenario": "worker-evidence-proof",
                "mode": "local-exec",
                "artifact_root": str(artifact_root),
            }
        )
        + "\n"
    )
    return artifact_root


def test_ingest_local_exec_fleet_artifact_root_creates_worker_admin_identity_block(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "nlfr.sqlite"
    artifact_root = _build_local_exec_fleet_artifact_root(tmp_path)

    result = _run_nlfr(
        "ingest",
        str(artifact_root),
        "--database",
        str(database_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_metadata"]["mode"] == "local-exec"
    assert payload["run_metadata"]["run_group"] == "worker-evidence"
    assert payload["counts"]["targets"] == 2
    assert payload["counts"]["cache_events"] == 2
    assert payload["counts"]["proof_blocks"] == 1

    conn = initialize(connect(database_path))
    upsert_invocation(
        conn,
        stable_key=f"{payload['run_key']}:invocation:bazel",
        run_id=payload["run_id"],
        invocation_kind="bazel",
        command=[
            "bazel",
            "test",
            "//tasks:priority_test",
            "--remote_executor=grpc://127.0.0.1:50051",
        ],
        cwd=artifact_root,
        exit_code=0,
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["artifact:nativelink.stdout.txt", "artifact:bazel.bep.json"],
        redaction_state="safe",
    )

    block = conn.execute("SELECT * FROM proof_blocks").fetchone()
    target = conn.execute(
        "SELECT source_kind FROM targets WHERE label = ?",
        ("//tasks:priority_test",),
    ).fetchone()
    proof = export_proof_packet(conn, run_group="worker-evidence")
    graph = export_action_graph(conn, run_group="worker-evidence")

    assert block["block_kind"] == "worker_admin_identity_v1"
    assert block["block_key"] == "worker-admin-identity"
    assert block["source_kind"] == "collectable_v1"
    assert block["confidence"] == "high"
    assert block["redaction_state"] == "safe"
    stored_payload = json.loads(block["payload"])
    assert len(stored_payload["events"]) == 2
    assert stored_payload["events"][0]["worker_name"] == "worker-demo-alpha"
    assert stored_payload["events"][1]["worker_name"] == "worker-demo-beta"
    assert target["source_kind"] == "collectable_v1"

    identity_block = next(
        item for item in proof["blocks"] if item["kind"] == "worker_admin_identity_v1"
    )
    assert identity_block["source_kind"] == "collectable_v1"
    assert identity_block["confidence"] == "high"
    assert "collectable_v1:nativelink.stdout.txt" in identity_block["evidence_refs"]

    remote_block = next(block for block in proof["blocks"] if block["id"] == "remote_execution")
    assert remote_block["metrics"]["worker_identity_observed"] is True
    assert "worker_identity" not in remote_block["payload"]["unsupported_claims"]

    worker_nodes = [node for node in graph["nodes"] if node["kind"] == "worker"]
    assert {node["label"] for node in worker_nodes} == {
        "worker-demo-alpha",
        "worker-demo-beta",
    }
