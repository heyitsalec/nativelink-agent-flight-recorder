import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "demo" / "nativelink" / "local-execution.json5"
SCRIPT = ROOT / "scripts" / "worker-readiness.py"


def run_readiness(tmp_path, *args):
    output = tmp_path / "worker-readiness.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(CONFIG),
            "--output",
            str(output),
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(output.read_text()) if output.exists() else None
    return result, payload


def test_worker_readiness_preflight_records_one_worker_config(tmp_path):
    result, payload = run_readiness(tmp_path, "--phase", "preflight")

    assert result.returncode == 0
    assert payload["status"] == "configuration_ready"
    assert payload["expected_workers"] == 1
    assert payload["configured_workers"] == 2
    assert len(payload["config_sha256"]) == 64
    assert payload["worker_api_endpoints"][0]["label"] == "grpc://127.0.0.1:50061"
    assert payload["worker_api_endpoints"][0]["redacted"] is False
    assert {"execution", "worker_api", "capabilities", "cas", "ac"} <= set(
        payload["services"]
    )
    assert "worker_identity" in payload["unsupported_claims"]
    assert "does not prove worker registration" in " ".join(payload["claims"]).lower()


def test_worker_readiness_blocks_when_expected_workers_exceed_config(tmp_path):
    result, payload = run_readiness(
        tmp_path,
        "--phase",
        "preflight",
        "--expected-workers",
        "3",
    )

    assert result.returncode == 2
    assert payload["status"] == "configuration_blocker"
    assert payload["expected_workers"] == 3
    assert payload["configured_workers"] == 2
    assert "below expected 3" in " ".join(payload["reasons"])


def test_worker_readiness_preflight_passes_for_two_expected_workers(tmp_path):
    result, payload = run_readiness(
        tmp_path,
        "--phase",
        "preflight",
        "--expected-workers",
        "2",
    )

    assert result.returncode == 0
    assert payload["status"] == "configuration_ready"
    assert payload["expected_workers"] == 2
    assert payload["configured_workers"] == 2


def test_worker_readiness_ports_record_endpoint_readiness_only(tmp_path):
    result, payload = run_readiness(
        tmp_path,
        "--phase",
        "ports",
        "--public-port-open",
        "--worker-api-port-open",
        "--evidence-ref",
        "nativelink.stdout.txt",
        "--evidence-ref",
        "nativelink.stderr.txt",
    )

    assert result.returncode == 0
    assert payload["status"] == "worker_endpoints_ready"
    assert payload["port_checks"]["public_endpoint_open"] is True
    assert payload["port_checks"]["worker_api_endpoint_open"] is True
    assert "action_placement" in payload["unsupported_claims"]
    assert "not worker identity or action placement" in " ".join(payload["claims"])


def test_local_exec_script_expected_two_workers_passes_config_gate(tmp_path):
    output = tmp_path / "local-exec"
    env = os.environ.copy()
    env["NLFR_LOCAL_EXEC_OUTPUT"] = str(output)
    env["NLFR_EXPECTED_WORKERS"] = "2"

    result = subprocess.run(
        ["bash", "scripts/local-exec-proof.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    readiness = json.loads((output / "worker-readiness.json").read_text())
    assert readiness["status"] in {"configuration_ready", "worker_endpoints_ready"}
    assert readiness["expected_workers"] == 2
    assert readiness["configured_workers"] == 2
    assert readiness["status"] != "configuration_blocker"
    if result.returncode != 0:
        assert (output / "environment-blocker.json").exists()
