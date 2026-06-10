"""Verifiable agent receipts for headless Claude Code CLI invocations.

A receipt is collected evidence that a live LLM call produced an agent change:
it carries the server-resolved model id, session id, token usage, the SHA-256
of the response text, and the SHA-256 of the prompt. The raw prompt is NEVER
stored or exported (AGENTS.md privacy rule) — hash only. The response text is
code and may be stored as a separate artifact.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA_VERSION = "nlfr.agent_receipt.v1"

#: Keys that must never appear anywhere inside a receipt payload.
FORBIDDEN_PROMPT_KEYS = frozenset({"prompt", "raw_prompt", "prompt_text", "system_prompt"})

#: CLI basenames accepted as live Claude Code invocations.
LIVE_CLI_NAMES = frozenset({"claude"})


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` encoded as UTF-8."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
) -> dict[str, Any]:
    """Build a receipt payload from a parsed ``claude -p --output-format json`` result.

    ``status`` is ``success`` for a completed live call, otherwise an honest
    failure label (``api_error``, ``environment_blocker``, ``invalid_output``,
    ``timeout``). The raw prompt never enters the payload; callers pass only
    its SHA-256.
    """

    result = cli_result or {}
    response_text = result.get("result") if isinstance(result.get("result"), str) else None
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    model_usage = result.get("modelUsage") if isinstance(result.get("modelUsage"), dict) else {}
    resolved_models = sorted(model_usage)
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
        "response_sha256": sha256_text(response_text) if response_text is not None else None,
        "response_chars": len(response_text) if response_text is not None else None,
        "model": {
            "requested": requested_model,
            "resolved": resolved_models[0] if len(resolved_models) == 1 else None,
            "resolved_all": resolved_models,
        },
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
