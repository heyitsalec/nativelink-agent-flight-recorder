"""Gemini CLI receipts — the first non-Claude receipt_verified_v1 integration.

GitHub issue #28. Everything here is FIXTURE-BACKED against the documented
``gemini -p "<prompt>" --output-format json`` shape (official Gemini CLI docs +
merged google-gemini/gemini-cli#14504, Dec 2025): a single JSON object with
``response`` (text), ``stats.models`` (dict keyed by model name, each carrying a
``tokens`` block of ``prompt``/``candidates``/``total``/``cached``),
``session_id`` (shipped Dec 2025), and an optional ``error`` object.

No live Gemini CLI runs in this suite — the doc-derived integration is proven
with canned JSON fixtures and a fake CLI. A live end-to-end check exists but is
env-gated (``test_gemini_live_chain_env_gated``) and skips without a real CLI.
The Claude regression suite (tests/test_agent_receipt.py) is deliberately left
untouched; the parser registry keeps Claude's path byte-identical.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from nlfr.agent_receipt import (
    FORBIDDEN_PROMPT_KEYS,
    build_receipt,
    is_live_receipt,
    load_receipt,
    sha256_text,
    validate_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "gemini"
CONTRACT = ROOT / "contracts" / "agent_receipt.v1.json"

PROMPT_TEXT = "GEMINI-SECRET-PROMPT never stored anywhere\n"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _gemini_receipt(fixture: str, *, status: str = "success", **overrides):
    kwargs = dict(
        cli_result=_fixture(fixture),
        prompt_sha256=sha256_text(PROMPT_TEXT),
        cli_name="gemini",
        cli_version="gemini-cli 0.14.0",
        requested_model=None,
        sanitized_command=["gemini", "-p", "<prompt:sha256>", "--output-format", "json"],
        status=status,
        cli_family="gemini",
    )
    kwargs.update(overrides)
    return build_receipt(**kwargs)


# --------------------------------------------------------------------------- #
# Happy path — the verified-tier bar is cleared from Gemini's documented shape
# --------------------------------------------------------------------------- #


def test_gemini_happy_receipt_captures_server_resolved_fields():
    receipt = _gemini_receipt("happy.json")
    assert receipt["status"] == "success"
    # stats.models is a dict-of-one-key → resolved model (mirrors Claude modelUsage).
    assert receipt["model"]["resolved"] == "gemini-2.5-pro"
    assert receipt["model"]["resolved_all"] == ["gemini-2.5-pro"]
    assert receipt["session_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert receipt["response_sha256"] == sha256_text("Done.\n\n```python\nVALUE = 1\n```\n")
    # Token semantics that MATCH are mapped; ones Gemini does not report stay absent.
    assert receipt["usage"]["input_tokens"] == 1200
    assert receipt["usage"]["output_tokens"] == 340
    assert receipt["usage"]["cache_read_input_tokens"] == 200
    assert receipt["usage"]["cache_creation_input_tokens"] is None
    # cli.name == "gemini" is a live family → collectable_v1, high confidence.
    assert receipt["source_kind"] == "collectable_v1"
    assert receipt["confidence"] == "high"
    assert receipt["redaction_state"] == "redacted"
    assert is_live_receipt(receipt)
    # The success invariants hold — validate does not raise.
    validate_receipt(receipt)


def test_gemini_happy_reaches_receipt_verified_v1_through_run(tmp_path: Path):
    """End-to-end: a Gemini receipt drives the agent leg to receipt_verified_v1.

    This is the same machinery Claude receipts use (nlfr run --mode generic
    --agent-receipt), proving the tier is computed identically for Gemini.
    """

    receipt = _gemini_receipt("happy.json")
    receipt_path = tmp_path / "gemini-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "probe.txt").write_text("agent output\n", encoding="utf-8")
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "nlfr.agent_provenance.sidecar.v1",
                "adapter": "gemini-cli",
                "change_class": "bounded_agent_v1",
                "agent": {
                    "kind": "gemini_cli_adapter_v1",
                    "name": "gemini-receipt-agent",
                    "model": "operator-typed-gemini",
                    "prompt_sha256": sha256_text(PROMPT_TEXT),
                },
                "change_before_hashes": {"probe.txt": None},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "run", "--mode", "generic",
            "--scenario", "gemini-probe", "--run-group", "gemini-probe",
            "--workspace", str(workspace), "--output-dir", str(output_dir),
            "--change-path", "probe.txt", "--provenance-sidecar", str(sidecar),
            "--agent-receipt", str(receipt_path), "--command", "true", "--json",
        ],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    artifact_root = Path(payload["artifact_root"])
    provenance = json.loads((artifact_root / "agent-provenance.json").read_text())

    assert provenance["source_kind"] == "collectable_v1"
    agent = provenance["agent"]
    assert agent["provenance_class"] == "receipt_verified_v1"
    # Model comes from Gemini's SERVER-resolved id, not the operator label.
    assert agent["model"] == "gemini-2.5-pro"
    assert agent["model_label_operator"] == "operator-typed-gemini"
    assert agent["receipt"]["session_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert agent["receipt"]["live"] is True
    # Privacy holds across the whole run: the prompt bytes never appear.
    assert PROMPT_TEXT.strip() not in (artifact_root / "agent-provenance.json").read_text()
    assert PROMPT_TEXT.strip() not in (artifact_root / "agent-receipt.json").read_text()


# --------------------------------------------------------------------------- #
# Honest degradation — anything short of the bar drops BELOW the verified tier
# --------------------------------------------------------------------------- #


def test_gemini_missing_session_id_degrades_not_verified():
    receipt = _gemini_receipt("no_session.json")
    # A "success" request with no session_id is recorded honestly, not raised.
    assert receipt["status"] == "invalid_output"
    assert receipt["session_id"] is None
    assert receipt["model"]["resolved"] == "gemini-2.5-pro"  # model was present
    # Honest evidence of the attempt (collectable), but NOT the verified tier.
    assert receipt["source_kind"] == "collectable_v1"
    assert not is_live_receipt(receipt)
    assert "session_id" in receipt["detail"]
    validate_receipt(receipt)  # invalid_output has no success invariants


def test_gemini_multi_model_stats_degrades_not_verified():
    receipt = _gemini_receipt("multi_model.json")
    # Two model keys → no single resolved model → below the verified tier.
    assert receipt["model"]["resolved"] is None
    assert receipt["model"]["resolved_all"] == ["gemini-2.5-flash", "gemini-2.5-pro"]
    assert receipt["status"] == "invalid_output"
    assert not is_live_receipt(receipt)
    # Token usage is still aggregated honestly across both models.
    assert receipt["usage"]["input_tokens"] == 1200
    assert receipt["usage"]["output_tokens"] == 160
    validate_receipt(receipt)


def test_gemini_error_object_is_honest_failure():
    # The command maps a Gemini error object to a failure status before build.
    receipt = _gemini_receipt("error.json", status="api_error", detail="401")
    assert receipt["status"] == "api_error"
    assert receipt["api_error_status"] == 401
    assert receipt["result_subtype"] == "ApiError"
    # Honest failure receipts are collected evidence of the attempt, not "live".
    assert receipt["source_kind"] == "collectable_v1"
    assert receipt["confidence"] == "high"
    assert not is_live_receipt(receipt)
    validate_receipt(receipt)


# --------------------------------------------------------------------------- #
# Privacy — identical guarantees to Claude receipts
# --------------------------------------------------------------------------- #


def test_gemini_receipt_never_contains_prompt_text():
    receipt = _gemini_receipt("happy.json")
    serialized = json.dumps(receipt)
    assert "GEMINI-SECRET-PROMPT" not in serialized
    for key in FORBIDDEN_PROMPT_KEYS:
        assert f'"{key}"' not in serialized


def test_gemini_receipt_rejects_injected_prompt_key():
    receipt = _gemini_receipt("happy.json")
    receipt["prompt"] = "the raw prompt leaked into a gemini receipt"
    with pytest.raises(ValueError, match="raw prompt"):
        validate_receipt(receipt)
    # Also rejected when nested under the gemini stats we newly parse.
    receipt.pop("prompt")
    receipt["cli"]["raw_prompt"] = "leaked"
    with pytest.raises(ValueError, match="raw prompt"):
        validate_receipt(receipt)


def test_gemini_receipt_validates_against_contract():
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    # Happy (collectable) and failure receipts both satisfy agent_receipt.v1.json
    # with NO schema change — cli.name is a free string, not an enum.
    validator.validate(_gemini_receipt("happy.json"))
    validator.validate(_gemini_receipt("error.json", status="api_error"))
    validator.validate(_gemini_receipt("multi_model.json"))
    # Negative control: the contract's `not` clause still catches a leaked prompt.
    leaked = _gemini_receipt("happy.json")
    leaked["prompt"] = "leaked"
    assert not validator.is_valid(leaked)


# --------------------------------------------------------------------------- #
# Command path — nlfr agent-invoke --agent-cli gemini against a fake CLI
# --------------------------------------------------------------------------- #


def _write_gemini_stub(tmp_path: Path, *, fixture: str, exit_code: int = 0) -> Path:
    """A tiny fake ``gemini`` CLI that emits a fixed --output-format json body."""

    stub = tmp_path / "gemini"
    body = (FIXTURES / fixture).read_text(encoding="utf-8")
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('gemini-cli 0.14.0 (stub)')\n"
        "    raise SystemExit(0)\n"
        f"sys.stdout.write({body!r})\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _run_gemini_invoke(tmp_path: Path, stub: Path, prompt_text: str):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(prompt_text, encoding="utf-8")
    receipt_out = tmp_path / "out" / "receipt.json"
    response_out = tmp_path / "out" / "response.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "agent-invoke",
            "--agent-cli", "gemini",
            "--agent-bin", str(stub),
            "--prompt-file", str(prompt),
            "--receipt-output", str(receipt_out),
            "--response-output", str(response_out),
            "--cwd", str(tmp_path / "scratch"),
            "--json",
        ],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    return proc, receipt_out, response_out


def test_agent_invoke_gemini_writes_receipt_and_response(tmp_path: Path):
    stub = _write_gemini_stub(tmp_path, fixture="happy.json")
    proc, receipt_out, response_out = _run_gemini_invoke(tmp_path, stub, PROMPT_TEXT)

    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["status"] == "success"
    assert summary["model_resolved"] == "gemini-2.5-pro"
    assert summary["prompt_sha256"] == sha256_text(PROMPT_TEXT)

    receipt = load_receipt(receipt_out)
    assert receipt["cli"]["name"] == "gemini"
    assert receipt["cli"]["version"] == "gemini-cli 0.14.0 (stub)"
    assert is_live_receipt(receipt)
    assert response_out.read_text(encoding="utf-8") == "Done.\n\n```python\nVALUE = 1\n```\n"

    # Privacy: the prompt never appears in stdout or the receipt; command sanitized.
    assert "GEMINI-SECRET-PROMPT" not in proc.stdout
    assert "GEMINI-SECRET-PROMPT" not in receipt_out.read_text(encoding="utf-8")
    assert "<prompt:sha256>" in receipt["cli"]["command"]


def test_agent_invoke_gemini_records_error_receipt(tmp_path: Path):
    stub = _write_gemini_stub(tmp_path, fixture="error.json", exit_code=1)
    proc, receipt_out, response_out = _run_gemini_invoke(tmp_path, stub, "p\n")

    assert proc.returncode == 3, proc.stdout + proc.stderr
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "api_error"
    assert receipt["api_error_status"] == 401
    assert not response_out.exists()


def test_agent_invoke_gemini_missing_session_degrades(tmp_path: Path):
    stub = _write_gemini_stub(tmp_path, fixture="no_session.json")
    proc, receipt_out, response_out = _run_gemini_invoke(tmp_path, stub, "p\n")

    # No error object and exit 0, but the JSON lacks session_id → honest downgrade.
    assert proc.returncode == 3, proc.stdout + proc.stderr
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "invalid_output"
    assert not is_live_receipt(receipt)  # honest evidence, below the verified tier
    assert not response_out.exists()


# --------------------------------------------------------------------------- #
# Env-gated live proof — mirrors tests/test_agent_live_proof.py's skipif pattern
# --------------------------------------------------------------------------- #


def _gemini_on_path() -> bool:
    from shutil import which

    return which("gemini") is not None


@pytest.mark.skipif(
    os.environ.get("NLFR_RUN_AGENT_LIVE_GEMINI") != "1" or not _gemini_on_path(),
    reason="set NLFR_RUN_AGENT_LIVE_GEMINI=1 with the gemini CLI on PATH for live proof",
)
def test_gemini_live_chain_env_gated(tmp_path: Path):
    """Live proof against a REAL gemini CLI. Skips unless explicitly opted in.

    Pending a machine with the Gemini CLI installed; the fixture tests above
    cover the doc-derived shape. When run, this asserts a real invocation
    produces a receipt whose success path reaches the verified-tier fields and
    that the raw prompt never leaks — an honest failure receipt is acceptable
    (e.g. unauthenticated), but a fabricated success is not.
    """

    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Reply with the single word: ok\n", encoding="utf-8")
    receipt_out = tmp_path / "receipt.json"
    response_out = tmp_path / "response.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "agent-invoke",
            "--agent-cli", "gemini",
            "--prompt-file", str(prompt),
            "--receipt-output", str(receipt_out),
            "--response-output", str(response_out),
            "--json",
        ],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert receipt_out.is_file(), proc.stderr
    receipt = load_receipt(receipt_out)
    assert "Reply with the single word" not in receipt_out.read_text(encoding="utf-8")
    if receipt["status"] == "success":
        assert receipt["model"]["resolved"]
        assert receipt["session_id"]
        assert receipt["response_sha256"]
        assert is_live_receipt(receipt)
    else:
        # Honest failure receipt: recorded evidence of the attempt, never faked.
        assert not is_live_receipt(receipt)
