import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.agent_receipt import (
    FORBIDDEN_PROMPT_KEYS,
    build_receipt,
    is_live_receipt,
    load_receipt,
    receipt_provenance_summary,
    receipt_sha256,
    sha256_text,
    validate_receipt,
)

ROOT = Path(__file__).resolve().parents[1]

CLI_RESULT = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 4200,
    "duration_api_ms": 3100,
    "num_turns": 1,
    "result": "Done.\n\n```python\nVALUE = 1\n```\n",
    "session_id": "11111111-2222-3333-4444-555555555555",
    "total_cost_usd": 0.01,
    "usage": {
        "input_tokens": 321,
        "output_tokens": 45,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 100,
    },
    "modelUsage": {"claude-sonnet-4-5-20250929": {"output_tokens": 45}},
}


def _receipt(**overrides):
    kwargs = dict(
        cli_result=CLI_RESULT,
        prompt_sha256=sha256_text("never stored"),
        cli_name="claude",
        cli_version="2.1.162 (Claude Code)",
        requested_model=None,
        sanitized_command=["claude", "-p", "<prompt:sha256>", "--output-format", "json"],
        status="success",
    )
    kwargs.update(overrides)
    return build_receipt(**kwargs)


def test_build_receipt_captures_server_resolved_fields():
    receipt = _receipt()
    assert receipt["schema_version"] == "nlfr.agent_receipt.v1"
    assert receipt["model"]["resolved"] == "claude-sonnet-4-5-20250929"
    assert receipt["session_id"] == CLI_RESULT["session_id"]
    assert receipt["usage"]["input_tokens"] == 321
    assert receipt["usage"]["output_tokens"] == 45
    assert receipt["response_sha256"] == sha256_text(CLI_RESULT["result"])
    assert receipt["cli"]["version"] == "2.1.162 (Claude Code)"
    assert receipt["captured_at"].endswith("Z")
    assert receipt["source_kind"] == "collectable_v1"
    assert receipt["confidence"] == "high"
    assert receipt["redaction_state"] == "redacted"
    assert is_live_receipt(receipt)


def test_receipt_never_contains_prompt_text():
    receipt = _receipt()
    serialized = json.dumps(receipt)
    assert "never stored" not in serialized
    for key in FORBIDDEN_PROMPT_KEYS:
        assert f'"{key}"' not in serialized


def test_stub_cli_receipt_is_simulated_not_live():
    receipt = _receipt(cli_name="spark-stub-claude.sh")
    assert receipt["source_kind"] == "simulated_v1"
    assert receipt["confidence"] == "medium"
    assert not is_live_receipt(receipt)


def test_failure_receipt_is_honest_collectable_evidence():
    error_result = {
        "is_error": True,
        "api_error_status": 401,
        "result": "Failed to authenticate. API Error: 401",
        "session_id": "errsession",
        "usage": {},
    }
    receipt = _receipt(cli_result=error_result, status="api_error", detail="401")
    assert receipt["status"] == "api_error"
    assert receipt["source_kind"] == "collectable_v1"
    assert not is_live_receipt(receipt)


def test_validate_receipt_rejects_raw_prompt_fields():
    receipt = _receipt()
    receipt["prompt"] = "leaked"
    with pytest.raises(ValueError, match="raw prompt"):
        validate_receipt(receipt)
    receipt.pop("prompt")
    receipt["cli"]["prompt_text"] = "leaked"
    with pytest.raises(ValueError, match="raw prompt"):
        validate_receipt(receipt)


def test_validate_receipt_requires_success_fields():
    receipt = _receipt()
    receipt["session_id"] = None
    with pytest.raises(ValueError, match="session_id"):
        validate_receipt(receipt)


def test_load_receipt_roundtrip(tmp_path: Path):
    receipt = _receipt()
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    loaded = load_receipt(path)
    assert receipt_sha256(loaded) == receipt_sha256(receipt)


def test_receipt_provenance_summary_is_hash_level_only():
    receipt = _receipt()
    summary = receipt_provenance_summary(receipt)
    assert summary["live"] is True
    assert summary["model_resolved"] == "claude-sonnet-4-5-20250929"
    assert summary["receipt_sha256"] == receipt_sha256(receipt)
    serialized = json.dumps(summary)
    assert "never stored" not in serialized
    assert "```python" not in serialized


def _write_stub_cli(tmp_path: Path, *, payload: dict | None = None, exit_code: int = 0) -> Path:
    """Write a tiny fake claude CLI that emits a fixed JSON result."""

    stub = tmp_path / "claude"
    body = json.dumps(payload if payload is not None else CLI_RESULT)
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('stub-cli 0.0.1')\n"
        "    raise SystemExit(0)\n"
        f"print({body!r})\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _run_agent_invoke(tmp_path: Path, stub: Path, prompt_text: str) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(prompt_text, encoding="utf-8")
    receipt_out = tmp_path / "out" / "receipt.json"
    response_out = tmp_path / "out" / "response.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nlfr",
            "agent-invoke",
            "--prompt-file",
            str(prompt),
            "--receipt-output",
            str(receipt_out),
            "--response-output",
            str(response_out),
            "--claude-bin",
            str(stub),
            "--cwd",
            str(tmp_path / "scratch"),
            "--json",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc, receipt_out, response_out


def test_agent_invoke_writes_receipt_and_response(tmp_path: Path):
    stub = _write_stub_cli(tmp_path)
    prompt_text = "SECRET-SPARK-PROMPT do the task\n"
    proc, receipt_out, response_out = _run_agent_invoke(tmp_path, stub, prompt_text)

    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["status"] == "success"
    assert summary["prompt_sha256"] == sha256_text(prompt_text)

    receipt = load_receipt(receipt_out)
    assert receipt["status"] == "success"
    assert receipt["model"]["resolved"] == "claude-sonnet-4-5-20250929"
    assert receipt["cli"]["version"] == "stub-cli 0.0.1"
    assert response_out.read_text(encoding="utf-8") == CLI_RESULT["result"]

    # Privacy: prompt text never appears in stdout, receipt, or response files.
    assert "SECRET-SPARK-PROMPT" not in proc.stdout
    assert "SECRET-SPARK-PROMPT" not in receipt_out.read_text(encoding="utf-8")
    # Receipt command is sanitized.
    assert "<prompt:sha256>" in receipt["cli"]["command"]


def test_agent_invoke_records_honest_error_receipt(tmp_path: Path):
    error_payload = {
        "is_error": True,
        "api_error_status": 401,
        "result": "Failed to authenticate. API Error: 401 Invalid authentication credentials",
        "session_id": "errsession",
        "usage": {},
    }
    stub = _write_stub_cli(tmp_path, payload=error_payload, exit_code=0)
    proc, receipt_out, response_out = _run_agent_invoke(tmp_path, stub, "p\n")

    assert proc.returncode == 3, proc.stdout + proc.stderr
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "api_error"
    assert receipt["api_error_status"] == 401
    assert not response_out.exists()


def test_agent_invoke_missing_cli_is_environment_blocker(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    proc, receipt_out, _ = _run_agent_invoke(tmp_path, missing, "p\n")
    assert proc.returncode == 3
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "environment_blocker"


# --------------------------------------------------------------------------- #
# Claude honest-degradation path (F1)
#
# The per-CLI parser registry added a success-downgrade block to build_receipt
# that applies to EVERY family, including claude. This is a DELIBERATE behavior
# change, now owned and tested: a claude "success" whose --output-format json
# lacks a verification field (multi-key modelUsage, or a missing session_id)
# previously raised ValueError from validate_receipt — traceback, exit 1, NO
# receipt file written. It now records an honest ``invalid_output`` receipt
# (exit 3, receipt written), mirroring the Gemini degraded tests. These are
# strictly better outcomes, not byte-identical ones.
# --------------------------------------------------------------------------- #

_MULTI_MODEL_USAGE = {
    "claude-sonnet-4-5-20250929": {"output_tokens": 45},
    "claude-opus-4-1-20250805": {"output_tokens": 12},
}


def test_claude_multi_model_usage_degrades_not_verified():
    receipt = _receipt(cli_result=dict(CLI_RESULT, modelUsage=_MULTI_MODEL_USAGE))
    # Two modelUsage keys → no single resolved model → below the verified tier.
    assert receipt["status"] == "invalid_output"
    assert receipt["model"]["resolved"] is None
    assert receipt["model"]["resolved_all"] == [
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-5-20250929",
    ]
    # Honest evidence of the attempt (collectable), but NOT live.
    assert receipt["source_kind"] == "collectable_v1"
    assert not is_live_receipt(receipt)
    assert "model.resolved" in receipt["detail"]
    validate_receipt(receipt)  # invalid_output carries no success invariants


def test_claude_missing_session_id_degrades_not_verified():
    no_session = {k: v for k, v in CLI_RESULT.items() if k != "session_id"}
    receipt = _receipt(cli_result=no_session)
    assert receipt["status"] == "invalid_output"
    assert receipt["session_id"] is None
    assert receipt["model"]["resolved"] == "claude-sonnet-4-5-20250929"  # model present
    assert not is_live_receipt(receipt)
    assert "session_id" in receipt["detail"]
    validate_receipt(receipt)


def test_agent_invoke_claude_multi_model_degrades_writes_receipt(tmp_path: Path):
    # Behavior change: this input used to raise (exit 1, no receipt). Now an
    # honest invalid_output receipt IS written and the exit code (3) is
    # consistent with the receipt status.
    stub = _write_stub_cli(tmp_path, payload=dict(CLI_RESULT, modelUsage=_MULTI_MODEL_USAGE))
    proc, receipt_out, response_out = _run_agent_invoke(tmp_path, stub, "p\n")

    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert receipt_out.is_file()  # the key change: a receipt IS written now
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "invalid_output"
    assert receipt["model"]["resolved"] is None
    assert not is_live_receipt(receipt)
    assert not response_out.exists()  # no response file below the verified tier


def test_agent_invoke_claude_missing_session_degrades_writes_receipt(tmp_path: Path):
    payload = {k: v for k, v in CLI_RESULT.items() if k != "session_id"}
    stub = _write_stub_cli(tmp_path, payload=payload)
    proc, receipt_out, response_out = _run_agent_invoke(tmp_path, stub, "p\n")

    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert receipt_out.is_file()
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "invalid_output"
    assert receipt["session_id"] is None
    assert not is_live_receipt(receipt)
    assert not response_out.exists()
