"""Receipt-verified agent provenance through nlfr run + projections."""

import json
import os
import subprocess
import sys
from pathlib import Path

from nlfr.agent_receipt import build_receipt, sha256_text
from nlfr.db import connect, initialize
from nlfr.projectors.compare import export_compare_projection
from nlfr.projectors.graph import export_action_graph

ROOT = Path(__file__).resolve().parents[1]

PROMPT_TEXT = "RECEIPT-TEST-PROMPT never stored\n"

CLI_RESULT = {
    "subtype": "success",
    "is_error": False,
    "duration_ms": 1000,
    "duration_api_ms": 800,
    "num_turns": 1,
    "result": "ok\n",
    "session_id": "abcd1234-receipt-session",
    "total_cost_usd": 0.0,
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "modelUsage": {"claude-sonnet-4-5-20250929": {"output_tokens": 5}},
}


def _write_receipt(tmp_path: Path, *, cli_name: str = "claude") -> Path:
    receipt = build_receipt(
        cli_result=CLI_RESULT,
        prompt_sha256=sha256_text(PROMPT_TEXT),
        cli_name=cli_name,
        cli_version="2.1.162 (Claude Code)",
        requested_model=None,
        sanitized_command=[cli_name, "-p", "<prompt:sha256>", "--output-format", "json"],
        status="success",
    )
    path = tmp_path / f"receipt-{cli_name}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_sidecar(tmp_path: Path, *, model: str = "operator-typed-model") -> Path:
    sidecar = {
        "schema_version": "nlfr.agent_provenance.sidecar.v1",
        "adapter": "test-two-act",
        "change_class": "bounded_agent_v1",
        "agent": {
            "kind": "claude_code_adapter_v1",
            "name": "receipt-test-agent",
            "model": model,
            "prompt_sha256": sha256_text(PROMPT_TEXT),
        },
        "change_before_hashes": {"probe.txt": None},
    }
    path = tmp_path / "sidecar.json"
    path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    return path


def _run_nlfr(*args: str) -> subprocess.CompletedProcess[str]:
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


def _generic_run_with_receipt(tmp_path: Path, receipt_path: Path | None) -> tuple[dict, Path]:
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    (workspace / "probe.txt").write_text("agent output\n", encoding="utf-8")
    sidecar = _write_sidecar(tmp_path)
    output_dir = tmp_path / "out"
    args = [
        "run",
        "--mode",
        "generic",
        "--scenario",
        "receipt-probe",
        "--run-group",
        "receipt-probe",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--change-path",
        "probe.txt",
        "--provenance-sidecar",
        str(sidecar),
        "--command",
        "true",
        "--json",
    ]
    if receipt_path is not None:
        args.extend(["--agent-receipt", str(receipt_path)])
    result = _run_nlfr(*args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), output_dir


def test_live_receipt_upgrades_agent_provenance(tmp_path: Path):
    receipt_path = _write_receipt(tmp_path, cli_name="claude")
    payload, output_dir = _generic_run_with_receipt(tmp_path, receipt_path)

    artifact_root = Path(payload["artifact_root"])
    provenance = json.loads((artifact_root / "agent-provenance.json").read_text())
    assert provenance["source_kind"] == "collectable_v1"
    agent = provenance["agent"]
    assert agent["provenance_class"] == "receipt_verified_v1"
    # Model comes from the SERVER-resolved id, not the operator-typed label.
    assert agent["model"] == "claude-sonnet-4-5-20250929"
    assert agent["model_label_operator"] == "operator-typed-model"
    assert agent["receipt"]["session_id"] == CLI_RESULT["session_id"]
    assert agent["receipt"]["live"] is True
    assert any(ref.startswith("receipt:sha256:") for ref in provenance["evidence_refs"])

    # Receipt is an immutable artifact in the manifest.
    manifest = json.loads((artifact_root / "artifact_manifest.json").read_text())
    keys = {entry["artifact_key"] for entry in manifest["artifacts"]}
    assert "agent-receipt.json" in keys
    stored_receipt = json.loads((artifact_root / "agent-receipt.json").read_text())
    assert stored_receipt["prompt_sha256"] == sha256_text(PROMPT_TEXT)
    assert PROMPT_TEXT.strip() not in (artifact_root / "agent-receipt.json").read_text()


def test_receipt_surfaces_on_graph_agent_node(tmp_path: Path):
    receipt_path = _write_receipt(tmp_path, cli_name="claude")
    _, output_dir = _generic_run_with_receipt(tmp_path, receipt_path)

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    graph = export_action_graph(conn, run_group="receipt-probe")
    agents = [node for node in graph["nodes"] if node["kind"] == "agent"]
    assert len(agents) == 1
    agent_node = agents[0]
    assert agent_node["source_kind"] == "collectable_v1"
    payload = agent_node["payload"]
    assert payload["receipt_verified"] is True
    assert payload["provenance_class"] == "receipt_verified_v1"
    assert payload["receipt_session_id"] == CLI_RESULT["session_id"]
    assert payload["receipt_model_resolved"] == "claude-sonnet-4-5-20250929"
    assert "prompt" not in payload
    serialized = json.dumps(graph)
    assert PROMPT_TEXT.strip() not in serialized


def test_without_receipt_provenance_stays_operator_asserted(tmp_path: Path):
    _, output_dir = _generic_run_with_receipt(tmp_path, None)

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    graph = export_action_graph(conn, run_group="receipt-probe")
    agent_node = next(node for node in graph["nodes"] if node["kind"] == "agent")
    payload = agent_node["payload"]
    assert payload["receipt_verified"] is False
    assert payload["provenance_class"] == "operator_asserted_v1"
    assert payload["model"] == "operator-typed-model"


def test_stub_receipt_downgrades_agent_leg_to_simulated(tmp_path: Path):
    receipt_path = _write_receipt(tmp_path, cli_name="spark-stub-claude.sh")
    payload, output_dir = _generic_run_with_receipt(tmp_path, receipt_path)

    artifact_root = Path(payload["artifact_root"])
    provenance = json.loads((artifact_root / "agent-provenance.json").read_text())
    assert provenance["source_kind"] == "simulated_v1"
    assert provenance["agent"]["provenance_class"] == "stub_receipt_v1"

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    graph = export_action_graph(conn, run_group="receipt-probe")
    agent_node = next(node for node in graph["nodes"] if node["kind"] == "agent")
    assert agent_node["source_kind"] == "simulated_v1"
    assert agent_node["payload"]["receipt_verified"] is False


def test_compare_projection_carries_receipt_flags(tmp_path: Path):
    receipt_path = _write_receipt(tmp_path, cli_name="claude")
    _, output_dir = _generic_run_with_receipt(tmp_path, receipt_path)

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    compare = export_compare_projection(conn, "receipt-probe", "receipt-probe")
    dimension = next(d for d in compare["dimensions"] if d["id"] == "agent_provenance")
    blocks = dimension["left"]["blocks"]
    assert blocks, "expected agent provenance blocks in compare projection"
    assert blocks[0]["receipt_verified"] is True
    assert blocks[0]["provenance_class"] == "receipt_verified_v1"
    assert blocks[0]["receipt_session_id"] == CLI_RESULT["session_id"]


def test_bazel_mode_run_records_receipt_without_toolchain(tmp_path: Path):
    """cache-only run wiring works even when bazel is absent (blocker status)."""

    receipt_path = _write_receipt(tmp_path, cli_name="claude")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "probe.txt").write_text("agent output\n", encoding="utf-8")
    sidecar = _write_sidecar(tmp_path)
    output_dir = tmp_path / "out-bazel"
    result = _run_nlfr(
        "run",
        "--mode",
        "cache-only",
        "--skip-nativelink",
        "--scenario",
        "receipt-bazel-probe",
        "--run-group",
        "receipt-bazel-probe",
        "--workspace",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--bazel-executable",
        "definitely-not-bazel",
        "--change-path",
        "probe.txt",
        "--provenance-sidecar",
        str(sidecar),
        "--agent-receipt",
        str(receipt_path),
        "--json",
        "//...",
    )
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "environment_blocker"
    artifact_root = Path(payload["artifact_root"])
    provenance = json.loads((artifact_root / "agent-provenance.json").read_text())
    assert provenance["agent"]["provenance_class"] == "receipt_verified_v1"
    assert provenance["mode"] == "cache-only"
    assert provenance["build"]["status"] == "environment_blocker"
    # Receipt artifact present and hashed in the manifest.
    manifest = json.loads((artifact_root / "artifact_manifest.json").read_text())
    keys = {entry["artifact_key"] for entry in manifest["artifacts"]}
    assert "agent-receipt.json" in keys

    conn = initialize(connect(output_dir / "nlfr.sqlite"))
    graph = export_action_graph(conn, run_group="receipt-bazel-probe")
    kinds = {node["kind"] for node in graph["nodes"]}
    assert "agent" in kinds
    assert "change" in kinds
    edge_kinds = {edge["kind"] for edge in graph["edges"]}
    assert "authored_change" in edge_kinds
    assert "validated_by" in edge_kinds
