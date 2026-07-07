"""Verifiable agent receipts for headless AI-agent CLI invocations.

A receipt is collected evidence that a live LLM call produced an agent change:
it carries the server-resolved model id, session id, token usage, the SHA-256
of the response text, and the SHA-256 of the prompt. The raw prompt is NEVER
stored or exported (AGENTS.md privacy rule) — hash only. The response text is
code and may be stored as a separate artifact.

Each supported CLI has a *normalizer* in ``CLI_PARSERS`` that maps that CLI's
raw ``--output-format json`` shape onto one internal receipt shape. Claude Code
was the first integration; Gemini CLI is the second (its shape is doc-derived
and fixture-tested — see contracts and tests). Adding a CLI is a normalizer
plus a ``LIVE_CLI_NAMES`` entry; the receipt/validation/privacy machinery is
shared, so every CLI clears the exact same verified-receipt bar.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA_VERSION = "nlfr.agent_receipt.v1"

#: Keys that must never appear anywhere inside a receipt payload.
FORBIDDEN_PROMPT_KEYS = frozenset({"prompt", "raw_prompt", "prompt_text", "system_prompt"})

#: CLI basenames accepted as live agent invocations (one parser family each).
LIVE_CLI_NAMES = frozenset({"claude", "gemini"})


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` encoded as UTF-8."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_claude(result: dict[str, Any]) -> dict[str, Any]:
    """Map a parsed ``claude -p --output-format json`` object to the internal shape.

    This reproduces exactly the fields ``build_receipt`` historically read from
    the raw Claude result, so a *complete* successful Claude output yields a
    byte-identical receipt. The one deliberate behavior change (see
    ``build_receipt``) is that a claude "success" whose JSON lacks a verification
    field now degrades to an honest ``invalid_output`` receipt instead of raising.
    """

    response_text = result.get("result") if isinstance(result.get("result"), str) else None
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    model_usage = result.get("modelUsage") if isinstance(result.get("modelUsage"), dict) else {}
    return {
        "response_text": response_text,
        # modelUsage is a dict-of-one-key on success; sorted keys → resolved model.
        "resolved_models": sorted(model_usage),
        "session_id": result.get("session_id"),
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        },
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "duration_api_ms": result.get("duration_api_ms"),
        "total_cost_usd": result.get("total_cost_usd"),
        "result_subtype": result.get("subtype"),
        "api_error_status": result.get("api_error_status"),
    }


def _normalize_gemini(result: dict[str, Any]) -> dict[str, Any]:
    """Map a parsed ``gemini -p --output-format json`` object to the internal shape.

    Doc-derived from the official Gemini CLI ``--output-format json`` contract
    (merged google-gemini/gemini-cli#14504, Dec 2025): a single JSON object with
    ``response`` (text), ``stats.models`` (dict keyed by model name, each with a
    ``tokens`` block: ``prompt``/``candidates``/``total``/``cached``),
    ``session_id`` (shipped Dec 2025), and an optional ``error`` object.

    ``stats.models`` is structurally analogous to Claude's ``modelUsage`` — a
    dict whose sole key on a clean run is the resolved model. Multiple keys (or
    none) leave ``model.resolved`` absent, degrading below the verified tier.
    Token counts are mapped only where semantics MATCH Claude's: ``input_tokens``
    is the NET prompt (``max(0, prompt - cached)``) because Gemini's
    ``tokens.prompt`` is GROSS — inclusive of ``tokens.cached`` — while Claude's
    ``input_tokens`` exclude cache reads (see ``_sum_gemini_input_tokens``).
    Fields Gemini does not report (e.g. cache-creation tokens) are left absent
    rather than invented.
    """

    response_text = result.get("response") if isinstance(result.get("response"), str) else None
    stats = result.get("stats") if isinstance(result.get("stats"), dict) else {}
    models = stats.get("models") if isinstance(stats.get("models"), dict) else {}
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    error_code = error.get("code")
    # Gemini's error.code is string|number upstream (packages/core/src/output/
    # types.ts). api_error_status carries only a numeric HTTP-style code; a
    # symbolic string code (e.g. "PERMISSION_DENIED") is preserved verbatim in
    # api_error_code — real gemini-cli errors always carry a ``type`` too, so
    # result_subtype alone would drop the string code (review finding). Both
    # still label the attempt api_error through _error_signal.
    api_error_status = (
        error_code if isinstance(error_code, int) and not isinstance(error_code, bool) else None
    )
    api_error_code = error_code if isinstance(error_code, str) else None
    error_subtype = error.get("type") or api_error_code
    return {
        "response_text": response_text,
        "resolved_models": sorted(models),
        "session_id": result.get("session_id"),
        "usage": {
            # NET of cache reads (Gemini's prompt is gross-of-cache); see
            # _sum_gemini_input_tokens. Prevents double-counting cached tokens.
            "input_tokens": _sum_gemini_input_tokens(models),
            "output_tokens": _sum_gemini_tokens(models, "candidates"),
            # Gemini reports cached (read) tokens but NOT cache-creation tokens.
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": _sum_gemini_tokens(models, "cached"),
        },
        # Gemini's JSON does not carry these; omit rather than invent values.
        "num_turns": None,
        "duration_ms": None,
        "duration_api_ms": None,
        "total_cost_usd": None,
        "result_subtype": error_subtype if error else None,
        "api_error_status": api_error_status,
        "api_error_code": api_error_code if error else None,
    }


def _sum_gemini_tokens(models: dict[str, Any], field: str) -> int | None:
    """Sum ``tokens.<field>`` across every model in ``stats.models``.

    Returns ``None`` (absent, not zero) when no model reports the field, so a
    missing count is never fabricated as a real zero.
    """

    total = 0
    found = False
    for entry in models.values():
        if not isinstance(entry, dict):
            continue
        tokens = entry.get("tokens")
        if not isinstance(tokens, dict):
            continue
        value = tokens.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            total += value
            found = True
    return total if found else None


def _sum_gemini_input_tokens(models: dict[str, Any]) -> int | None:
    """Sum NET input (prompt-minus-cache) tokens across ``stats.models``.

    Gemini's ``tokens.prompt`` is GROSS: it INCLUDES ``tokens.cached`` (the
    cache-read tokens). This receipt maps every CLI onto Claude's usage shape,
    where ``input_tokens`` EXCLUDE cache reads (those are reported separately as
    ``cache_read_input_tokens``). Recording the gross ``prompt`` as
    ``input_tokens`` would therefore double-count the cached tokens — once as
    input and again as cache-read. We record the NET figure instead, matching
    upstream's own ``tokens.input = max(0, prompt - cached)``
    (packages/core/src/telemetry/uiTelemetry.ts). The documented
    ``--output-format json`` payload carries ``prompt``/``candidates``/``total``/
    ``cached`` and no literal ``input``, so we honor a literal ``input`` if a
    future build emits one and otherwise derive ``max(0, prompt - cached)`` per
    model (clamped at zero so a cached > prompt anomaly never goes negative).

    Returns ``None`` (absent, not zero) when no model reports usable counts, so a
    missing figure is never fabricated as a real zero.
    """

    total = 0
    found = False
    for entry in models.values():
        if not isinstance(entry, dict):
            continue
        tokens = entry.get("tokens")
        if not isinstance(tokens, dict):
            continue
        literal = tokens.get("input")
        if isinstance(literal, int) and not isinstance(literal, bool):
            total += max(0, literal)
            found = True
            continue
        prompt = tokens.get("prompt")
        if isinstance(prompt, int) and not isinstance(prompt, bool):
            cached = tokens.get("cached")
            cached_val = cached if isinstance(cached, int) and not isinstance(cached, bool) else 0
            total += max(0, prompt - cached_val)
            found = True
    return total if found else None


#: Per-CLI normalizers: raw CLI ``--output-format json`` object → internal shape.
CLI_PARSERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "claude": _normalize_claude,
    "gemini": _normalize_gemini,
}


def cli_family_for(cli_name: str) -> str:
    """Infer the parser family from a CLI basename.

    Explicit families are passed through unchanged by ``build_receipt``; this
    heuristic only covers callers that pass a bare name (including test stubs
    such as ``spark-stub-claude.sh``). Anything not recognizably Gemini falls
    back to the Claude family, preserving historical behavior.
    """

    lowered = (cli_name or "").lower()
    if "gemini" in lowered:
        return "gemini"
    return "claude"


def build_receipt(
    *,
    cli_result: dict[str, Any] | None,
    prompt_sha256: str,
    cli_name: str,
    cli_version: str | None,
    requested_model: str | None,
    sanitized_command: list[str],
    status: str,
    detail: str | None = None,
    captured_at: str | None = None,
    cli_family: str | None = None,
) -> dict[str, Any]:
    """Build a receipt payload from a parsed agent-CLI ``--output-format json`` result.

    ``cli_family`` selects the per-CLI normalizer (``claude`` or ``gemini``);
    when omitted it is inferred from ``cli_name`` so existing callers that pass
    only a name keep working. ``status`` is ``success`` for a completed live
    call, otherwise an honest failure label (``api_error``, ``cli_error``,
    ``environment_blocker``, ``invalid_output``, ``timeout``). The raw prompt
    never enters the payload; callers pass only its SHA-256.

    Honest degradation: a caller may request ``success``, but a receipt only
    earns that (verified-eligible) status when the evidence bar is met — a
    response, exactly one resolved model, and a session id. If the CLI's JSON
    lacked any of those (e.g. Gemini emitted multi-model stats, or no
    ``session_id``), the attempt is recorded as ``invalid_output`` rather than
    raising, so the receipt is preserved below the verified tier.
    """

    result = cli_result or {}
    family = cli_family or cli_family_for(cli_name)
    normalizer = CLI_PARSERS.get(family, _normalize_claude)
    parsed = normalizer(result)

    response_text = parsed["response_text"]
    response_sha = sha256_text(response_text) if response_text is not None else None
    resolved_models = parsed["resolved_models"]
    resolved_model = resolved_models[0] if len(resolved_models) == 1 else None
    session_id = parsed["session_id"]

    if status == "success" and not (response_sha and resolved_model and session_id):
        missing = [
            name
            for name, present in (
                ("response", response_sha),
                ("model.resolved", resolved_model),
                ("session_id", session_id),
            )
            if not present
        ]
        status = "invalid_output"
        detail = detail or f"CLI output missing verification fields: {', '.join(missing)}"

    live = cli_name in LIVE_CLI_NAMES and status == "success"

    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "captured_at": captured_at or _timestamp(),
        "status": status,
        "cli": {
            "name": cli_name,
            "version": cli_version,
            "command": sanitized_command,
        },
        "prompt_sha256": prompt_sha256,
        "response_sha256": response_sha,
        "response_chars": len(response_text) if response_text is not None else None,
        "model": {
            "requested": requested_model,
            "resolved": resolved_model,
            "resolved_all": resolved_models,
        },
        "session_id": session_id,
        "usage": {
            "input_tokens": parsed["usage"].get("input_tokens"),
            "output_tokens": parsed["usage"].get("output_tokens"),
            "cache_creation_input_tokens": parsed["usage"].get("cache_creation_input_tokens"),
            "cache_read_input_tokens": parsed["usage"].get("cache_read_input_tokens"),
        },
        "num_turns": parsed["num_turns"],
        "duration_ms": parsed["duration_ms"],
        "duration_api_ms": parsed["duration_api_ms"],
        "total_cost_usd": parsed["total_cost_usd"],
        "result_subtype": parsed["result_subtype"],
        "api_error_status": parsed["api_error_status"],
        "api_error_code": parsed.get("api_error_code"),
        "source_kind": "collectable_v1" if live else "simulated_v1",
        "confidence": "high" if live else "medium",
        "evidence_refs": [
            f"prompt:sha256:{prompt_sha256}",
            f"cli:{cli_name}",
        ],
        "redaction_state": "redacted",
    }
    if detail:
        receipt["detail"] = detail
    if status != "success":
        # Honest failure receipts are still collected evidence of the attempt.
        receipt["source_kind"] = "collectable_v1"
        receipt["confidence"] = "high"
    if receipt["response_sha256"]:
        receipt["evidence_refs"].append(f"response:sha256:{receipt['response_sha256']}")
    if receipt["session_id"]:
        receipt["evidence_refs"].append(f"session:{receipt['session_id']}")
    validate_receipt(receipt)
    return receipt


def validate_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate receipt shape and privacy posture; raise ``ValueError`` on violation."""

    if not isinstance(payload, dict):
        raise ValueError("agent receipt must be a JSON object")
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ValueError(
            f"agent receipt schema_version must be {RECEIPT_SCHEMA_VERSION}, "
            f"got {payload.get('schema_version')!r}"
        )
    _reject_forbidden_keys(payload, path="receipt")
    for field in ("captured_at", "status", "prompt_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"agent receipt missing required string field: {field}")
    if not _is_sha256(payload["prompt_sha256"]):
        raise ValueError("agent receipt prompt_sha256 must be a 64-char hex digest")
    cli = payload.get("cli")
    if not isinstance(cli, dict) or not cli.get("name"):
        raise ValueError("agent receipt missing cli.name")
    if payload["status"] == "success":
        if not _is_sha256(payload.get("response_sha256")):
            raise ValueError("successful agent receipt requires response_sha256")
        if not payload.get("session_id"):
            raise ValueError("successful agent receipt requires session_id")
        model = payload.get("model")
        if not isinstance(model, dict) or not model.get("resolved"):
            raise ValueError("successful agent receipt requires model.resolved")
    return payload


def load_receipt(path: str | Path) -> dict[str, Any]:
    """Read and validate a receipt JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_receipt(payload)


def receipt_sha256(payload: dict[str, Any]) -> str:
    """Stable content hash of a receipt (sorted-key JSON serialization)."""

    return sha256_text(json.dumps(payload, ensure_ascii=True, sort_keys=True))


def is_live_receipt(payload: dict[str, Any]) -> bool:
    """True when the receipt records a successful call from the real Claude CLI."""

    cli = payload.get("cli") if isinstance(payload.get("cli"), dict) else {}
    return payload.get("status") == "success" and cli.get("name") in LIVE_CLI_NAMES


def receipt_provenance_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact receipt summary safe to embed in agent provenance payloads."""

    model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    cli = payload.get("cli") if isinstance(payload.get("cli"), dict) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "captured_at": payload.get("captured_at"),
        "session_id": payload.get("session_id"),
        "model_resolved": model.get("resolved"),
        "model_requested": model.get("requested"),
        "prompt_sha256": payload.get("prompt_sha256"),
        "response_sha256": payload.get("response_sha256"),
        "receipt_sha256": receipt_sha256(payload),
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        },
        "num_turns": payload.get("num_turns"),
        "cli_name": cli.get("name"),
        "cli_version": cli.get("version"),
        "live": is_live_receipt(payload),
    }


def _reject_forbidden_keys(obj: Any, *, path: str) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_PROMPT_KEYS:
                raise ValueError(f"agent receipt must not contain raw prompt field: {path}.{key}")
            _reject_forbidden_keys(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _reject_forbidden_keys(item, path=f"{path}[{index}]")


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
