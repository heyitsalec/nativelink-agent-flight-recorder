"""Codex CLI receipts — the third receipt integration (after Claude, Gemini).

Unlike the doc-derived Gemini shape, the Codex shape here is **empirical**: it
was captured from a real ``codex exec --json`` invocation of codex-cli 0.144.1
(the installed build) and sanitized into the committed fixtures (ids replaced
with synthetic values; the exact event structure preserved; the only real prompt
was the trivial "Reply with exactly: ok"). See ``tests/fixtures/codex/*.json``.

Ground truth (codex-cli 0.144.1): ``codex exec --json`` emits **JSON Lines** —
one event object per line — NOT a single ``--output-format json`` document. A
success stream is four events: ``thread.started`` (``thread_id`` → session id),
``turn.started``, ``item.completed`` (``item.type == "agent_message"`` → response
text), and ``turn.completed`` (``usage``: ``input_tokens`` gross-of-cache,
``cached_input_tokens``, ``output_tokens``, ``reasoning_output_tokens``).

HONEST TIER CAVEAT: that stream carries **no resolved model id** — the model
lives only in the on-disk session rollout, which also stores the raw prompt and
is therefore privacy-forbidden as a receipt source. So a REAL Codex success
honestly degrades to ``invalid_output`` below the verified tier
(``happy.json``). Fixtures whose name carries ``_with_model`` (and the
multi/no-usage variants) add a ``model`` field in the forward-compatible
location the parser scans; they are NOT current 0.144.1 output and exist only to
prove the verified-tier wiring fires the instant a Codex build attests its model.
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
    CLI_PARSERS,
    build_receipt,
    cli_family_for,
    is_live_receipt,
    load_receipt,
    sha256_text,
    validate_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "codex"
CONTRACT = ROOT / "contracts" / "agent_receipt.v1.json"

PROMPT_TEXT = "CODEX-SECRET-PROMPT never stored anywhere\n"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _codex_receipt(fixture: str, *, status: str = "success", **overrides):
    kwargs = dict(
        cli_result=_fixture(fixture),
        prompt_sha256=sha256_text(PROMPT_TEXT),
        cli_name="codex",
        cli_version="codex-cli 0.144.1",
        requested_model=None,
        sanitized_command=["codex", "exec", "--json", "--skip-git-repo-check", "<prompt:sha256>"],
        status=status,
        cli_family="codex",
    )
    kwargs.update(overrides)
    return build_receipt(**kwargs)


# --------------------------------------------------------------------------- #
# Family registration
# --------------------------------------------------------------------------- #


def test_codex_is_registered_as_a_parser_family_and_choice():
    # Adding codex to CLI_PARSERS enrolls it in `agent-invoke --agent-cli` choices.
    assert "codex" in CLI_PARSERS
    assert cli_family_for("codex") == "codex"
    assert cli_family_for("/opt/homebrew/bin/codex") == "codex"
    # Non-codex names are unaffected (claude fallback preserved).
    assert cli_family_for("claude") == "claude"
    assert cli_family_for("gemini") == "gemini"


# --------------------------------------------------------------------------- #
# HONEST DEGRADATION — the REAL 0.144.1 success stream has NO model
# --------------------------------------------------------------------------- #


def test_codex_empty_stdout_stream_is_unparseable_and_degrades():
    # A dead/quiet codex process must yield an honest below-verified receipt,
    # never a crash: no events -> unparseable (None) -> invalid_output.
    from nlfr.commands.agent_invoke_cmd import _parse_cli_stdout

    assert _parse_cli_stdout("codex", "") is None
    assert _parse_cli_stdout("codex", "\n\n   \n") is None
    receipt = _codex_receipt("happy.json", cli_result=None)
    assert receipt["status"] == "invalid_output"
    assert not is_live_receipt(receipt)


def test_codex_interleaved_garbage_lines_are_skipped_and_last_message_wins():
    # Hostile stdout: banners and broken JSON interleaved with real events, and
    # TWO agent messages — parsing must survive and the LAST message must win,
    # pinned by the response hash.
    from nlfr.commands.agent_invoke_cmd import _parse_cli_stdout

    stdout = "\n".join(
        [
            "codex-cli booting...",
            '{"type": "thread.started", "thread_id": "019f-test"}',
            "{not json at all",
            '{"type": "item.completed", "item": {"type": "agent_message", "text": "first draft"}}',
            "42",
            '{"type": "item.completed", "item": {"type": "agent_message", "text": "final answer"}}',
            '{"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 2}}',
        ]
    )
    cli_result = _parse_cli_stdout("codex", stdout)
    assert cli_result is not None
    receipt = _codex_receipt("happy.json", cli_result=cli_result)
    assert receipt["response_sha256"] == sha256_text("final answer")
    assert receipt["usage"]["input_tokens"] == 6  # net of cache, gemini precedent
    assert receipt["usage"]["cache_read_input_tokens"] == 4


def test_codex_real_success_degrades_because_no_model_id_is_attested():
    """The empirically-captured success stream degrades below the verified tier.

    codex 0.144.1 emits response + session (thread_id) + usage but NO model, so a
    "success" request is recorded HONESTLY as ``invalid_output`` — never faked to
    verified. This is the primary honesty fixture (sanitized-from-real).
    """

    receipt = _codex_receipt("happy.json")
    assert receipt["status"] == "invalid_output"
    # Everything the stream DOES attest is captured faithfully:
    assert receipt["session_id"] == "019f0000-0000-7000-8000-000000000000"
    assert receipt["response_sha256"] == sha256_text("ok")
    # ...but no model is attested, so the verified bar is not met.
    assert receipt["model"]["resolved"] is None
    assert receipt["model"]["resolved_all"] == []
    assert "model.resolved" in receipt["detail"]
    # input_tokens is NET of cache reads: codex's input_tokens (13660) is GROSS
    # (inclusive of cached_input_tokens=9984), and Claude's input_tokens EXCLUDE
    # cache reads, so mapping the gross figure would double-count cached tokens.
    gross, cached, output = 13660, 9984, 5
    assert receipt["usage"]["input_tokens"] == gross - cached  # 3676, not 13660
    assert receipt["usage"]["cache_read_input_tokens"] == cached
    assert receipt["usage"]["output_tokens"] == output
    # codex reports cached (read) tokens but NOT cache-creation tokens.
    assert receipt["usage"]["cache_creation_input_tokens"] is None
    assert receipt["num_turns"] == 1
    # Honest evidence of the attempt (collectable), but NOT the verified tier.
    assert receipt["source_kind"] == "collectable_v1"
    assert not is_live_receipt(receipt)
    validate_receipt(receipt)  # invalid_output carries no success invariants


# --------------------------------------------------------------------------- #
# FORWARD-COMPAT — the verified tier is reachable the instant codex attests a model
# --------------------------------------------------------------------------- #


def test_codex_with_model_reaches_the_verified_tier():
    """Same real stream + a resolved model on thread.started → verified tier.

    This is NOT current 0.144.1 output; it proves the parser + LIVE_CLI_NAMES
    wiring lifts Codex to ``receipt_verified_v1`` the moment a build surfaces the
    model, clearing the exact same bar as claude/gemini.
    """

    receipt = _codex_receipt("happy_with_model.json")
    assert receipt["status"] == "success"
    assert receipt["model"]["resolved"] == "gpt-5.6-sol"
    assert receipt["model"]["resolved_all"] == ["gpt-5.6-sol"]
    assert receipt["session_id"] == "019f0000-0000-7000-8000-000000000000"
    assert receipt["response_sha256"] == sha256_text("ok")
    assert receipt["usage"]["input_tokens"] == 13660 - 9984
    assert receipt["source_kind"] == "collectable_v1"
    assert receipt["confidence"] == "high"
    assert receipt["redaction_state"] == "redacted"
    assert is_live_receipt(receipt)
    validate_receipt(receipt)


def test_codex_verified_when_usage_absent_but_model_present():
    """Usage is optional for the verified bar: model + session + response suffice.

    A ``turn.completed`` with no ``usage`` block leaves the token counts absent
    (None, never a fabricated zero) yet still clears the verified tier.
    """

    receipt = _codex_receipt("no_usage.json")
    assert receipt["status"] == "success"
    assert receipt["model"]["resolved"] == "gpt-5.6-sol"
    assert receipt["usage"]["input_tokens"] is None
    assert receipt["usage"]["output_tokens"] is None
    assert receipt["usage"]["cache_read_input_tokens"] is None
    assert is_live_receipt(receipt)
    validate_receipt(receipt)


def test_codex_multi_model_stream_degrades_and_sums_usage_honestly():
    receipt = _codex_receipt("multi_model.json")
    # Two distinct models across turns → no single resolved model → below the bar.
    assert receipt["model"]["resolved"] is None
    assert receipt["model"]["resolved_all"] == ["gpt-5.6-mini", "gpt-5.6-sol"]
    assert receipt["status"] == "invalid_output"
    assert not is_live_receipt(receipt)
    # Usage is still aggregated honestly across BOTH turns, NET of cache per turn:
    # turn1 (input 300, cached 0) → 300; turn2 (900, 50) → 850.
    assert receipt["usage"]["input_tokens"] == (300 - 0) + (900 - 50)  # 1150
    assert receipt["usage"]["output_tokens"] == 40 + 120  # 160
    assert receipt["usage"]["cache_read_input_tokens"] == 0 + 50  # 50
    assert receipt["num_turns"] == 2
    validate_receipt(receipt)


# --------------------------------------------------------------------------- #
# Error stream — the REAL failed-turn shape (nested JSON-string status)
# --------------------------------------------------------------------------- #


def test_codex_error_stream_maps_nested_status_and_type():
    # The command maps codex's turn.failed to a failure status before build; the
    # normalizer surfaces the nested HTTP status and error type from the message.
    receipt = _codex_receipt("error.json", status="api_error", detail="400")
    assert receipt["status"] == "api_error"
    assert receipt["api_error_status"] == 400
    assert receipt["result_subtype"] == "invalid_request_error"
    # Honest failure receipts are collected evidence of the attempt, not "live".
    assert receipt["source_kind"] == "collectable_v1"
    assert receipt["confidence"] == "high"
    assert not is_live_receipt(receipt)
    validate_receipt(receipt)


# --------------------------------------------------------------------------- #
# End-to-end: a verified Codex receipt drives an agent leg to receipt_verified_v1
# --------------------------------------------------------------------------- #


def test_codex_verified_receipt_reaches_receipt_verified_v1_through_run(tmp_path: Path):
    """Same machinery Claude/Gemini use (nlfr run --agent-receipt): the tier is
    computed identically for Codex once its receipt is live/verified."""

    receipt = _codex_receipt("happy_with_model.json")
    receipt_path = tmp_path / "codex-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "probe.txt").write_text("agent output\n", encoding="utf-8")
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "nlfr.agent_provenance.sidecar.v1",
                "adapter": "codex-cli",
                "change_class": "bounded_agent_v1",
                "agent": {
                    "kind": "codex_cli_adapter_v1",
                    "name": "codex-receipt-agent",
                    "model": "operator-typed-codex",
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
            "--scenario", "codex-probe", "--run-group", "codex-probe",
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
    # Model comes from Codex's SERVER-resolved id, not the operator label.
    assert agent["model"] == "gpt-5.6-sol"
    assert agent["model_label_operator"] == "operator-typed-codex"
    assert agent["receipt"]["session_id"] == "019f0000-0000-7000-8000-000000000000"
    assert agent["receipt"]["live"] is True
    # Privacy holds across the whole run: the prompt bytes never appear.
    assert PROMPT_TEXT.strip() not in (artifact_root / "agent-provenance.json").read_text()
    assert PROMPT_TEXT.strip() not in (artifact_root / "agent-receipt.json").read_text()


# --------------------------------------------------------------------------- #
# Privacy — identical guarantees to Claude/Gemini receipts
# --------------------------------------------------------------------------- #


def test_codex_receipt_never_contains_prompt_text():
    receipt = _codex_receipt("happy_with_model.json")
    serialized = json.dumps(receipt)
    assert "CODEX-SECRET-PROMPT" not in serialized
    for key in FORBIDDEN_PROMPT_KEYS:
        assert f'"{key}"' not in serialized


def test_codex_receipt_rejects_injected_prompt_key():
    receipt = _codex_receipt("happy_with_model.json")
    receipt["prompt"] = "the raw prompt leaked into a codex receipt"
    with pytest.raises(ValueError, match="raw prompt"):
        validate_receipt(receipt)
    # Also rejected when nested under cli (the whole tree is scanned).
    receipt.pop("prompt")
    receipt["cli"]["raw_prompt"] = "leaked"
    with pytest.raises(ValueError, match="raw prompt"):
        validate_receipt(receipt)


def test_codex_receipt_validates_against_contract():
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    # Verified, degraded, and failure receipts all satisfy agent_receipt.v1.json
    # with NO schema change — cli.name is a free string, not an enum.
    validator.validate(_codex_receipt("happy_with_model.json"))
    validator.validate(_codex_receipt("happy.json"))  # degraded (no model)
    validator.validate(_codex_receipt("error.json", status="api_error"))
    validator.validate(_codex_receipt("multi_model.json"))
    # Negative control: the contract's `not` clause still catches a leaked prompt.
    leaked = _codex_receipt("happy_with_model.json")
    leaked["prompt"] = "leaked"
    assert not validator.is_valid(leaked)


# --------------------------------------------------------------------------- #
# Command path — nlfr agent-invoke --agent-cli codex against a fake CLI
# --------------------------------------------------------------------------- #


def _write_codex_stub(tmp_path: Path, *, fixture: str, exit_code: int = 0) -> Path:
    """A tiny fake ``codex`` CLI that emits a fixture's events as RAW JSONL.

    Proves the round trip: fixture events → JSONL stdout → the command path's
    aggregation → normalization → receipt.
    """

    stub = tmp_path / "codex"
    events = _fixture(fixture)["events"]
    jsonl = "".join(json.dumps(event) + "\n" for event in events)
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('codex-cli 0.144.1 (stub)')\n"
        "    raise SystemExit(0)\n"
        f"sys.stdout.write({jsonl!r})\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _run_codex_invoke(tmp_path: Path, stub: Path, prompt_text: str):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(prompt_text, encoding="utf-8")
    receipt_out = tmp_path / "out" / "receipt.json"
    response_out = tmp_path / "out" / "response.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "agent-invoke",
            "--agent-cli", "codex",
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


def test_agent_invoke_codex_with_model_writes_verified_receipt(tmp_path: Path):
    stub = _write_codex_stub(tmp_path, fixture="happy_with_model.json")
    proc, receipt_out, response_out = _run_codex_invoke(tmp_path, stub, PROMPT_TEXT)

    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["status"] == "success"
    assert summary["model_resolved"] == "gpt-5.6-sol"
    assert summary["prompt_sha256"] == sha256_text(PROMPT_TEXT)

    receipt = load_receipt(receipt_out)
    assert receipt["cli"]["name"] == "codex"
    assert receipt["cli"]["version"] == "codex-cli 0.144.1 (stub)"
    assert is_live_receipt(receipt)
    assert response_out.read_text(encoding="utf-8") == "ok"

    # Privacy: the prompt never appears in stdout or the receipt; command sanitized.
    assert "CODEX-SECRET-PROMPT" not in proc.stdout
    assert "CODEX-SECRET-PROMPT" not in receipt_out.read_text(encoding="utf-8")
    assert "<prompt:sha256>" in receipt["cli"]["command"]
    # The sanitized command records the real codex form, not `-p ... --output-format`.
    assert receipt["cli"]["command"][:4] == [str(stub), "exec", "--json", "--skip-git-repo-check"]


def test_agent_invoke_codex_real_stream_degrades_no_response(tmp_path: Path):
    # The REAL 0.144.1 stream (no model) → honest invalid_output, no response file.
    stub = _write_codex_stub(tmp_path, fixture="happy.json")
    proc, receipt_out, response_out = _run_codex_invoke(tmp_path, stub, PROMPT_TEXT)

    assert proc.returncode == 3, proc.stdout + proc.stderr
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "invalid_output"
    assert receipt["session_id"] == "019f0000-0000-7000-8000-000000000000"
    assert not is_live_receipt(receipt)
    assert not response_out.exists()


def test_agent_invoke_codex_error_stream_is_api_error(tmp_path: Path):
    stub = _write_codex_stub(tmp_path, fixture="error.json", exit_code=1)
    proc, receipt_out, response_out = _run_codex_invoke(tmp_path, stub, "p\n")

    assert proc.returncode == 3, proc.stdout + proc.stderr
    receipt = json.loads(receipt_out.read_text(encoding="utf-8"))
    assert receipt["status"] == "api_error"
    assert receipt["api_error_status"] == 400
    assert receipt["result_subtype"] == "invalid_request_error"
    assert not is_live_receipt(receipt)
    assert not response_out.exists()


def test_agent_invoke_codex_rejects_claude_arg(tmp_path: Path):
    # --claude-arg is claude-only; it must NOT leak into the codex argv.
    stub = _write_codex_stub(tmp_path, fixture="happy_with_model.json")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(PROMPT_TEXT, encoding="utf-8")
    receipt_out = tmp_path / "out" / "receipt.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "agent-invoke",
            "--agent-cli", "codex", "--agent-bin", str(stub),
            "--prompt-file", str(prompt),
            "--receipt-output", str(receipt_out),
            "--response-output", str(tmp_path / "out" / "response.md"),
            "--cwd", str(tmp_path / "scratch"),
            "--claude-arg=--dangerously-bypass-approvals-and-sandbox",
        ],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "--claude-arg applies only to --agent-cli claude" in proc.stderr
    assert not receipt_out.exists()


# --------------------------------------------------------------------------- #
# Env-gated live proof — mirrors the gemini/claude live-proof skipif pattern
# --------------------------------------------------------------------------- #


def _codex_on_path() -> bool:
    from shutil import which

    return which("codex") is not None


@pytest.mark.skipif(
    os.environ.get("NLFR_RUN_AGENT_LIVE_CODEX") != "1" or not _codex_on_path(),
    reason="set NLFR_RUN_AGENT_LIVE_CODEX=1 with the codex CLI on PATH for live proof",
)
def test_codex_live_chain_env_gated(tmp_path: Path):
    """Live proof against a REAL codex CLI. Skips unless explicitly opted in.

    codex-cli 0.144.1 attests no model on its stream, so the HONEST live outcome
    is an ``invalid_output`` receipt (below the verified tier), NOT a faked
    success — and the raw prompt must never leak. If a future codex build surfaces
    the resolved model, the success branch here begins to fire.
    """

    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Reply with exactly: ok\n", encoding="utf-8")
    receipt_out = tmp_path / "receipt.json"
    response_out = tmp_path / "response.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable, "-m", "nlfr", "agent-invoke",
            "--agent-cli", "codex",
            "--prompt-file", str(prompt),
            "--receipt-output", str(receipt_out),
            "--response-output", str(response_out),
            "--json",
        ],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert receipt_out.is_file(), proc.stderr
    receipt = load_receipt(receipt_out)
    assert "Reply with exactly" not in receipt_out.read_text(encoding="utf-8")
    if receipt["status"] == "success":
        assert receipt["model"]["resolved"]
        assert receipt["session_id"]
        assert receipt["response_sha256"]
        assert is_live_receipt(receipt)
    else:
        # Honest sub-verified receipt (0.144.1: no model attested). Session and
        # response are still captured; the attempt is recorded, never faked.
        assert not is_live_receipt(receipt)
        assert receipt["session_id"]
