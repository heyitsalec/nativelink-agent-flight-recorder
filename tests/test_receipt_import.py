"""`nlfr receipt import` — cloud/pod agent receipts, honestly downgraded.

The import path accepts an `nlfr.agent_receipt.v1` file produced by an
invocation NLFR did NOT observe (CI runner, k8s pod, hosted agent session).
The honesty contract under test: the imported provenance class is
`receipt_imported_v1` — never `receipt_verified_v1` — and the receipt summary
is stamped `live: false` / `observed_by_nlfr: false`, so BOTH the graph and
compare projections render `receipt_verified: false` for a claude/success
receipt that merely arrived as a file. Invalid or privacy-violating receipts
are rejected with exit 2 and write nothing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from nlfr.db import connect, initialize
from nlfr.db.ingest import upsert_run
from nlfr.projectors.compare import export_compare_projection
from nlfr.projectors.graph import export_action_graph

ROOT = Path(__file__).resolve().parents[1]
RUN_GROUP = "pod-build"


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


def _valid_receipt() -> dict:
    return {
        "schema_version": "nlfr.agent_receipt.v1",
        "captured_at": "2026-07-09T00:00:00.000000Z",
        "status": "success",
        "cli": {
            "name": "claude",
            "version": "2.1.0",
            "command": ["claude", "-p", "<prompt-file>", "--output-format", "json"],
        },
        "prompt_sha256": "a" * 64,
        "response_sha256": "b" * 64,
        "response_chars": 512,
        "model": {
            "requested": None,
            "resolved": "claude-opus-4-8",
            "resolved_all": ["claude-opus-4-8"],
        },
        "session_id": "sess-pod-0001",
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
        },
        "num_turns": 1,
        "duration_ms": 1200,
        "duration_api_ms": 1100,
        "total_cost_usd": None,
        "result_subtype": "success",
        "api_error_status": None,
        "api_error_code": None,
        "source_kind": "collectable_v1",
        "confidence": "high",
        "evidence_refs": ["prompt:sha256:" + "a" * 64, "cli:claude"],
        "redaction_state": "redacted",
    }


def _seed(db_path: Path, run_group: str = RUN_GROUP) -> None:
    conn = initialize(connect(db_path))
    upsert_run(
        conn,
        stable_key=f"run:{run_group}",
        run_group=run_group,
        scenario="pod-validation",
        mode="cache-only",
        status="completed",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=[f"run:{run_group}"],
        redaction_state="safe",
    )
    conn.commit()
    conn.close()


def _import_receipt(tmp_path: Path, receipt: dict, run_group: str = RUN_GROUP):
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return run_nlfr(
        "receipt", "import",
        "--receipt", str(receipt_path),
        "--db", str(tmp_path / "nlfr.sqlite"),
        "--run-group", run_group,
    )


def test_import_attaches_receipt_imported_provenance(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite")
    result = _import_receipt(tmp_path, _valid_receipt())
    assert result.returncode == 0, result.stderr

    conn = connect(tmp_path / "nlfr.sqlite")
    row = conn.execute(
        "SELECT payload FROM proof_blocks WHERE block_kind = 'agent_provenance'"
    ).fetchone()
    assert row is not None
    payload = json.loads(row[0])
    agent = payload["agent"]
    assert agent["provenance_class"] == "receipt_imported_v1"
    receipt_summary = agent["receipt"]
    assert receipt_summary["live"] is False
    assert receipt_summary["observed_by_nlfr"] is False
    assert payload["source_kind"] == "collectable_v1"
    assert payload["confidence"] == "medium"
    artifact = conn.execute(
        "SELECT sha256 FROM artifacts WHERE artifact_key LIKE 'agent-receipt-imported%'"
    ).fetchone()
    assert artifact is not None
    conn.close()


def test_imported_receipt_never_renders_verified(tmp_path: Path) -> None:
    db = tmp_path / "nlfr.sqlite"
    _seed(db)
    _seed(db, run_group="pod-build-2")
    assert _import_receipt(tmp_path, _valid_receipt()).returncode == 0
    assert _import_receipt(tmp_path, _valid_receipt(), run_group="pod-build-2").returncode == 0

    conn = connect(db)
    graph = export_action_graph(conn, run_group=RUN_GROUP)
    agent_nodes = [n for n in graph["nodes"] if n.get("kind") == "agent"]
    assert agent_nodes, "imported receipt must surface an agent node"
    for node in agent_nodes:
        assert node["payload"]["receipt_verified"] is False
        assert node["payload"]["provenance_class"] == "receipt_imported_v1"

    compare = export_compare_projection(conn, RUN_GROUP, "pod-build-2")
    agent_dimension = next(
        d for d in compare["dimensions"] if d["id"] == "agent_provenance"
    )
    for side in ("left", "right"):
        entries = agent_dimension[side]["blocks"]
        assert entries, f"{side} side must carry the imported provenance block"
        for entry in entries:
            assert entry["receipt_verified"] is False
            assert entry["provenance_class"] == "receipt_imported_v1"
    conn.close()


def test_schema_invalid_receipt_rejected(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite")
    bad = _valid_receipt()
    bad["schema_version"] = "bogus.v9"
    result = _import_receipt(tmp_path, bad)
    assert result.returncode == 2
    assert "schema_version" in result.stderr
    assert "Traceback" not in result.stderr

    conn = connect(tmp_path / "nlfr.sqlite")
    assert conn.execute("SELECT COUNT(*) FROM proof_blocks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0
    conn.close()


def test_raw_prompt_receipt_rejected(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite")
    leaky = _valid_receipt()
    leaky["prompt"] = "the raw prompt that must never be stored"
    result = _import_receipt(tmp_path, leaky)
    assert result.returncode == 2
    assert "prompt" in result.stderr

    conn = connect(tmp_path / "nlfr.sqlite")
    assert conn.execute("SELECT COUNT(*) FROM proof_blocks").fetchone()[0] == 0
    conn.close()


def test_unknown_run_group_rejected(tmp_path: Path) -> None:
    _seed(tmp_path / "nlfr.sqlite")
    result = _import_receipt(tmp_path, _valid_receipt(), run_group="absent-group")
    assert result.returncode == 2
    assert "absent-group" in result.stderr


def test_receipt_import_help_registered() -> None:
    result = run_nlfr("receipt", "import", "--help")
    assert result.returncode == 0
    assert "--receipt" in result.stdout
