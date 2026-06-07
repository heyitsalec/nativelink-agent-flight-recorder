import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cache-only-ci-gate.sh"


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


def validate_doctor_payload(payload: dict) -> None:
    assert payload["mode"] == "cache-only"
    assert isinstance(payload["ok"], bool)
    checks = payload["checks"]
    assert isinstance(checks, list) and checks

    names: set[str] = set()
    for check in checks:
        assert isinstance(check["ok"], bool)
        assert check["name"]
        assert check["detail"]
        names.add(check["name"])

    assert {"python", "bazel", "nativelink"} <= names
    assert checks[0]["name"] == "python"
    assert checks[0]["ok"] is True


def test_doctor_cache_only_json_contract() -> None:
    result = run_nlfr("doctor", "--mode", "cache-only", "--json")

    payload = json.loads(result.stdout)
    assert result.returncode == (0 if payload["ok"] else 1)
    validate_doctor_payload(payload)


def test_cache_only_ci_gate_script(tmp_path: Path) -> None:
    out = tmp_path / "cache-only-ci-gate"
    env = os.environ.copy()
    env["NLFR_CACHE_GATE_OUTPUT"] = str(out)

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    doctor = json.loads((out / "doctor.json").read_text(encoding="utf-8"))
    validate_doctor_payload(doctor)

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "passed"
    assert summary["proof_script"] == "cache-only-ci-gate.sh"
    assert summary["mode"] == "cache-only"
    assert summary["doctor_ok"] == doctor["ok"]
    assert summary["source_kind"] == "collectable_v1"
    assert summary["confidence"] == "high"
    assert summary["redaction_state"] == "safe"
    assert "script:cache-only-ci-gate.sh" in summary["evidence_refs"]
    assert "doctor_ok=false" in summary["claim_boundary"]
