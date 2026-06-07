import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from nlfr.projectors.remote_execution import UNSUPPORTED_REMOTE_EXECUTION_CLAIMS

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fleet_claims_audit.py"

MATRIX_TOP_LEVEL_KEYS = {
    "status",
    "recorded_at",
    "source_kind",
    "confidence",
    "redaction_state",
    "evidence_refs",
    "broker_rule",
    "supported_collectable_ceiling",
    "claims",
}

CLAIM_ROW_KEYS = {
    "claim_id",
    "v1_policy",
    "parser",
    "sqlite_proof_block",
    "canvas_lens",
    "one_pager",
}


def _build_matrix() -> dict:
    spec = importlib.util.spec_from_file_location("fleet_claims_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_matrix()


def test_build_matrix_claim_schema() -> None:
    payload = _build_matrix()

    assert MATRIX_TOP_LEVEL_KEYS <= set(payload.keys())
    assert payload["status"] == "research_only"
    assert payload["source_kind"] == "derived_v1"
    assert payload["confidence"] == "high"
    assert payload["redaction_state"] == "safe"
    assert isinstance(payload["evidence_refs"], list) and payload["evidence_refs"]
    assert isinstance(payload["supported_collectable_ceiling"], list)
    assert isinstance(payload["claims"], list)

    for row in payload["claims"]:
        assert CLAIM_ROW_KEYS <= set(row.keys())
        assert row["canvas_lens"] == "remote_boundary"
        assert row["one_pager"] == "explicitly_unproven"


def test_build_matrix_includes_all_unsupported_claims() -> None:
    payload = _build_matrix()
    claim_ids = {row["claim_id"] for row in payload["claims"]}

    assert claim_ids == set(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS)
    assert len(payload["claims"]) == len(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS)


def test_worker_identity_row_documents_parser() -> None:
    payload = _build_matrix()
    worker_row = next(row for row in payload["claims"] if row["claim_id"] == "worker_identity")

    assert worker_row["v1_policy"] == "conditional"
    assert worker_row["parser"] == "nlfr.ingest.worker_admin_stdout.parse_worker_admin_stdout"
    assert worker_row["sqlite_proof_block"] == "worker_admin_identity_v1"
    assert worker_row.get("collectable_when")
    assert worker_row.get("projection_behavior")


def test_fleet_claims_audit_subprocess_writes_matrix(tmp_path: Path) -> None:
    output = tmp_path / "claim-matrix.json"
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output.is_file()

    payload = json.loads(output.read_text(encoding="utf-8"))
    claim_ids = {row["claim_id"] for row in payload["claims"]}
    assert claim_ids == set(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS)

    worker_row = next(row for row in payload["claims"] if row["claim_id"] == "worker_identity")
    assert worker_row["parser"] == "nlfr.ingest.worker_admin_stdout.parse_worker_admin_stdout"
