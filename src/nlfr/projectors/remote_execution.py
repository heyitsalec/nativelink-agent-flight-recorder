"""Remote execution projection helpers."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit

REMOTE_ENDPOINT_FLAGS = ("--remote_cache", "--remote_executor")

UNSUPPORTED_REMOTE_EXECUTION_CLAIMS = (
    "worker_identity",
    "action_placement",
    "queue_time",
    "scheduler_assignment",
    "load_distribution",
)


def remote_execution_invocations(invocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return invocations where Bazel was configured with a remote executor."""

    items: list[dict[str, Any]] = []
    for invocation in invocations:
        endpoints = _remote_executor_endpoints(invocation.get("command"))
        if not endpoints:
            continue
        endpoint = endpoints[-1]
        endpoint_label, endpoint_redacted = _endpoint_label(endpoint)
        items.append(
            {
                "invocation": invocation,
                "endpoint": endpoint,
                "endpoint_label": endpoint_label,
                "endpoint_fingerprint": _fingerprint(endpoint),
                "endpoint_redacted": endpoint_redacted,
                "remote_executor_arg_count": len(endpoints),
                "evidence_refs": invocation.get("evidence_refs") or [],
            }
        )
    return items


def worker_identity_events_for_run(
    run_id: str,
    proof_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return direct worker identity rows stored for a run."""

    events: list[dict[str, Any]] = []
    for block in proof_blocks:
        if block.get("block_kind") != "worker_admin_identity_v1":
            continue
        if block.get("run_id") != run_id:
            continue
        payload = block.get("payload") if isinstance(block.get("payload"), dict) else {}
        for row in payload.get("events") or []:
            if isinstance(row, dict) and row.get("worker_name"):
                events.append(row)
    return events


def unsupported_claims_for_run(
    run_id: str,
    proof_blocks: list[dict[str, Any]],
) -> list[str]:
    """Return remote-execution claims that remain unsupported for one run."""

    claims = list(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS)
    if worker_identity_events_for_run(run_id, proof_blocks):
        claims = [claim for claim in claims if claim != "worker_identity"]
    return claims


def remote_execution_metrics(
    invocations: list[dict[str, Any]],
    proof_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize observed remote-execution configuration and identity evidence."""

    remote_items = remote_execution_invocations(invocations)
    endpoints = sorted({item["endpoint"] for item in remote_items})
    worker_identity_observed = False
    if proof_blocks:
        for invocation in invocations:
            if worker_identity_events_for_run(str(invocation.get("run_id") or ""), proof_blocks):
                worker_identity_observed = True
                break
    return {
        "remote_executor_invocations": len(remote_items),
        "remote_executor_endpoints": len(endpoints),
        "remote_executor_overrides": sum(
            max(0, item["remote_executor_arg_count"] - 1) for item in remote_items
        ),
        "worker_identity_observed": worker_identity_observed,
        "queue_time_observed": False,
        "scheduler_assignment_observed": False,
    }


def unsupported_claims_for_group(
    invocations: list[dict[str, Any]],
    proof_blocks: list[dict[str, Any]],
) -> list[str]:
    """Return remote-execution claims unsupported across a run group."""

    claims = list(UNSUPPORTED_REMOTE_EXECUTION_CLAIMS)
    for invocation in invocations:
        if worker_identity_events_for_run(str(invocation.get("run_id") or ""), proof_blocks):
            claims = [claim for claim in claims if claim != "worker_identity"]
            break
    return claims


def remote_execution_endpoint_summaries(
    invocations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return privacy-safe endpoint summaries for projection payloads."""

    summaries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in remote_execution_invocations(invocations):
        fingerprint = item["endpoint_fingerprint"]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        summaries.append(
            {
                "label": item["endpoint_label"],
                "fingerprint": fingerprint,
                "redacted": item["endpoint_redacted"],
            }
        )
    return summaries


def sanitize_remote_endpoint_args(command: object) -> object:
    """Redact non-local remote endpoint flag values from a command list."""

    if not isinstance(command, list):
        return command
    sanitized: list[object] = []
    index = 0
    while index < len(command):
        part = command[index]
        if not isinstance(part, str):
            sanitized.append(part)
            index += 1
            continue
        flag, endpoint = _split_remote_endpoint_flag(part)
        if flag is not None and endpoint is not None:
            label, _ = _endpoint_label(endpoint)
            sanitized.append(f"{flag}={label}")
            index += 1
            continue
        if part in REMOTE_ENDPOINT_FLAGS and index + 1 < len(command):
            next_value = command[index + 1]
            sanitized.append(part)
            if isinstance(next_value, str):
                label, _ = _endpoint_label(next_value)
                sanitized.append(label)
            else:
                sanitized.append(next_value)
            index += 2
            continue
        sanitized.append(part)
        index += 1
    return sanitized


def _remote_executor_endpoints(command: object) -> list[str]:
    if not isinstance(command, list):
        return []
    endpoints: list[str] = []
    index = 0
    while index < len(command):
        part = command[index]
        if not isinstance(part, str):
            index += 1
            continue
        flag, endpoint = _split_remote_endpoint_flag(part)
        if flag == "--remote_executor" and endpoint is not None:
            endpoints.append(endpoint)
            index += 1
            continue
        if part == "--remote_executor" and index + 1 < len(command):
            endpoint = command[index + 1]
            if isinstance(endpoint, str):
                endpoints.append(endpoint)
            index += 2
            continue
        index += 1
    return endpoints


def _split_remote_endpoint_flag(part: str) -> tuple[str | None, str | None]:
    for flag in REMOTE_ENDPOINT_FLAGS:
        prefix = f"{flag}="
        if part.startswith(prefix):
            return flag, part.split("=", 1)[1]
    return None, None


def _endpoint_label(endpoint: str) -> tuple[str, bool]:
    parsed = urlsplit(endpoint)
    hostname = parsed.hostname or ""
    safe_loopback = hostname in {"127.0.0.1", "localhost", "::1"}
    has_credentials = parsed.username is not None or parsed.password is not None
    if safe_loopback and not has_credentials:
        return endpoint, False
    scheme = f"{parsed.scheme}://" if parsed.scheme else ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{scheme}<redacted>{port}#{_fingerprint(endpoint)}", True


def _fingerprint(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]
