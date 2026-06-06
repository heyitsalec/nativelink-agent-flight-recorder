"""Parsers for compact Bazel evidence artifacts."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from nlfr.ingest.models import (
    ActionEvidence,
    CacheEventEvidence,
    EvidenceBundle,
    FailureEvidence,
    TargetEvidence,
)


def parse_bazel_bep(
    path: str | Path,
    *,
    source_kind: str = "collectable_v1",
    confidence: str = "high",
    evidence_ref: str | None = None,
) -> EvidenceBundle:
    """Parse Bazel Build Event Protocol JSON lines or JSON objects."""

    evidence_path = Path(path)
    evidence_refs = [_evidence_ref(evidence_path, evidence_ref)]
    targets: dict[str, TargetEvidence] = {}
    actions: dict[str, ActionEvidence] = {}
    failures: dict[str, FailureEvidence] = {}

    for index, event in enumerate(_load_json_events(evidence_path), start=1):
        event_id = event.get("id", {})
        label = _bep_label(event_id, event)

        if label and "configured" in event:
            configured = event["configured"]
            target = _target_for(
                targets,
                label=label,
                source_kind=source_kind,
                confidence=confidence,
                evidence_refs=evidence_refs,
            )
            target.target_kind = _string_or_none(configured.get("targetKind"))
            target.status = target.status or "CONFIGURED"

        if label and "action" in event:
            action_id = _nested_get(event_id, "actionCompleted", "id")
            primary_output = _nested_get(event_id, "actionCompleted", "primaryOutput")
            action_key = f"{label}:action:{action_id or primary_output or index}"
            action = event["action"]
            actions[action_key] = ActionEvidence(
                action_key=action_key,
                target_label=label,
                mnemonic=_string_or_none(action.get("type") or action.get("mnemonic")),
                status=_success_status(action.get("success")),
                source_kind=source_kind,
                confidence=confidence,
                evidence_refs=list(evidence_refs),
            )

        if label and "testResult" in event:
            result = event["testResult"]
            status = _string_or_none(result.get("status")) or "UNKNOWN"
            target = _target_for(
                targets,
                label=label,
                source_kind=source_kind,
                confidence=confidence,
                evidence_refs=evidence_refs,
            )
            target.status = status
            action_key = _test_action_key(event_id, label)
            actions[action_key] = ActionEvidence(
                action_key=action_key,
                target_label=label,
                mnemonic="BazelTest",
                status=status,
                source_kind=source_kind,
                confidence=confidence,
                evidence_refs=list(evidence_refs),
            )

        if label and "completed" in event:
            completed = event["completed"]
            target = _target_for(
                targets,
                label=label,
                source_kind=source_kind,
                confidence=confidence,
                evidence_refs=evidence_refs,
            )
            if completed.get("targetKind"):
                target.target_kind = _string_or_none(completed.get("targetKind"))
            if completed.get("success") is False:
                target.status = "FAILED"
                detail = completed.get("failureDetail")
                message = _failure_message(detail) or f"{label} completed unsuccessfully"
                failure_key = f"{label}:target_completed:{index}"
                failures[failure_key] = FailureEvidence(
                    failure_key=failure_key,
                    failure_kind="target_completed",
                    message=message,
                    span={"event_index": index, "id": event_id},
                    source_kind=source_kind,
                    confidence=confidence,
                    evidence_refs=list(evidence_refs),
                )
            elif completed.get("success") is True and target.status in (None, "CONFIGURED"):
                target.status = "PASSED"

        if "finished" in event:
            exit_code = event["finished"].get("exitCode") or {}
            exit_name = _string_or_none(exit_code.get("name")) or "UNKNOWN"
            exit_value = exit_code.get("code")
            if exit_name != "SUCCESS" or exit_value not in (0, None):
                failure_key = f"build_finished:{index}:{exit_name}"
                failures[failure_key] = FailureEvidence(
                    failure_key=failure_key,
                    failure_kind="build_finished",
                    message=f"Bazel finished with {exit_name} (exit code {exit_value})",
                    span={"event_index": index, "id": event_id},
                    source_kind=source_kind,
                    confidence=confidence,
                    evidence_refs=list(evidence_refs),
                )

    return EvidenceBundle(
        targets=list(targets.values()),
        actions=list(actions.values()),
        failures=list(failures.values()),
    )


def parse_bazel_execution_log(
    path: str | Path,
    *,
    source_kind: str = "collectable_v1",
    evidence_ref: str | None = None,
) -> EvidenceBundle:
    """Parse Bazel execution-log-like JSON into cache evidence."""

    evidence_path = Path(path)
    evidence_refs = [_evidence_ref(evidence_path, evidence_ref)]
    events: list[CacheEventEvidence] = []

    for index, event in enumerate(_load_json_events(evidence_path), start=1):
        spawn = _spawn_exec(event)
        if spawn is None:
            continue

        target_label = _string_or_none(
            spawn.get("targetLabel") or spawn.get("target_label") or spawn.get("label")
        )
        mnemonic = _string_or_none(spawn.get("mnemonic")) or "Spawn"
        digest = _digest_from(spawn)
        hit = _cache_hit_from(spawn)
        event_source_kind = source_kind
        confidence = "high"
        if hit is None:
            event_source_kind = "derived_v1"
            confidence = "low"

        event_kind = _cache_event_kind(hit)
        event_key = _cache_event_key(target_label, mnemonic, digest, index)
        events.append(
            CacheEventEvidence(
                event_key=event_key,
                event_kind=event_kind,
                hit=hit,
                digest=digest,
                target_label=target_label,
                source_kind=event_source_kind,
                confidence=confidence,
                evidence_refs=list(evidence_refs),
            )
        )

    return EvidenceBundle(cache_events=events)


def parse_bazel_profile(
    path: str | Path,
    *,
    evidence_ref: str | None = None,
) -> EvidenceBundle:
    """Parse Bazel profile/Chrome-trace-like JSON into derived cache evidence."""

    evidence_path = Path(path)
    evidence_refs = [_evidence_ref(evidence_path, evidence_ref)]
    payload = _load_json_document(evidence_path)
    trace_events = payload.get("traceEvents", []) if isinstance(payload, dict) else []
    events: list[CacheEventEvidence] = []

    for index, event in enumerate(trace_events, start=1):
        if not isinstance(event, dict):
            continue
        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        target_label = _string_or_none(
            args.get("label") or args.get("target") or args.get("targetLabel")
        )
        if target_label is None:
            continue

        name = str(event.get("name") or "").lower()
        mnemonic = _string_or_none(args.get("mnemonic")) or "Action"
        digest = _digest_from(args)
        timestamp = _string_or_none(event.get("ts")) or str(index)
        hit = True if "cache hit" in name else None
        event_kind = "remote_cache_hit" if hit is True else "action_cache_observed"
        confidence = "medium" if hit is True else "low"
        event_key = f"profile:{target_label}:{mnemonic}:{digest or timestamp}"

        events.append(
            CacheEventEvidence(
                event_key=event_key,
                event_kind=event_kind,
                hit=hit,
                digest=digest,
                target_label=target_label,
                source_kind="derived_v1",
                confidence=confidence,
                evidence_refs=list(evidence_refs),
            )
        )

    return EvidenceBundle(cache_events=events)


def _load_json_events(path: Path) -> list[dict[str, Any]]:
    text = _read_text(path).strip()
    if not text:
        return []

    try:
        return _normalize_json_payload(json.loads(text))
    except json.JSONDecodeError:
        try:
            return _load_concatenated_json_events(text)
        except json.JSONDecodeError:
            return [
                event
                for event in (json.loads(line) for line in text.splitlines() if line.strip())
                if isinstance(event, dict)
            ]


def _load_concatenated_json_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        payload, index = decoder.raw_decode(text, index)
        events.extend(_normalize_json_payload(payload))
    return events


def _normalize_json_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [event for event in payload if isinstance(event, dict)]
    if isinstance(payload, dict):
        for key in ("events", "buildEvents"):
            value = payload.get(key)
            if isinstance(value, list):
                return [event for event in value if isinstance(event, dict)]
        return [payload]
    return []


def _load_json_document(path: Path) -> Any:
    return json.loads(_read_text(path))


def _read_text(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8")


def _evidence_ref(path: Path, evidence_ref: str | None) -> str:
    return evidence_ref or f"artifact:{path.name}"


def _bep_label(event_id: dict[str, Any], event: dict[str, Any]) -> str | None:
    for key in ("targetConfigured", "targetCompleted", "testResult", "actionCompleted"):
        label = _nested_get(event_id, key, "label")
        if label:
            return str(label)
    for payload_key in ("configured", "completed", "testResult", "action"):
        payload = event.get(payload_key)
        if isinstance(payload, dict) and payload.get("label"):
            return str(payload["label"])
    return None


def _nested_get(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _target_for(
    targets: dict[str, TargetEvidence],
    *,
    label: str,
    source_kind: str,
    confidence: str,
    evidence_refs: list[str],
) -> TargetEvidence:
    if label not in targets:
        targets[label] = TargetEvidence(
            label=label,
            source_kind=source_kind,
            confidence=confidence,
            evidence_refs=list(evidence_refs),
        )
    return targets[label]


def _success_status(value: Any) -> str | None:
    if value is True:
        return "SUCCESS"
    if value is False:
        return "FAILED"
    return None


def _test_action_key(event_id: dict[str, Any], label: str) -> str:
    result_id = event_id.get("testResult") if isinstance(event_id, dict) else {}
    if not isinstance(result_id, dict):
        result_id = {}
    run = result_id.get("run", 1)
    shard = result_id.get("shard", 1)
    attempt = result_id.get("attempt", 1)
    return f"{label}:test:run={run}:shard={shard}:attempt={attempt}"


def _failure_message(detail: Any) -> str | None:
    if isinstance(detail, dict):
        message = detail.get("message")
        if message:
            return str(message)
    if isinstance(detail, str):
        return detail
    return None


def _spawn_exec(event: dict[str, Any]) -> dict[str, Any] | None:
    if "spawnExec" in event and isinstance(event["spawnExec"], dict):
        return event["spawnExec"]
    if "spawn" in event and isinstance(event["spawn"], dict):
        return event["spawn"]
    if any(key in event for key in ("mnemonic", "targetLabel", "cacheHit", "runner")):
        return event
    return None


def _digest_from(payload: dict[str, Any]) -> str | None:
    digest = payload.get("digest") or payload.get("actionDigest")
    if isinstance(digest, str):
        return digest
    if isinstance(digest, dict):
        hash_value = digest.get("hash") or digest.get("sha256")
        size = digest.get("sizeBytes") or digest.get("size_bytes")
        if hash_value and size:
            return f"{hash_value}/{size}"
        if hash_value:
            return str(hash_value)
    listed_outputs = payload.get("listedOutputs") or payload.get("actualOutputs")
    if isinstance(listed_outputs, list) and listed_outputs:
        return str(listed_outputs[0])
    return None


def _cache_hit_from(payload: dict[str, Any]) -> bool | None:
    for key in ("cacheHit", "remoteCacheHit", "remote_cache_hit"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    runner = str(payload.get("runner") or "").lower()
    if "cache hit" in runner:
        return True
    if runner in {"local", "sandboxed", "worker"} or "cache miss" in runner:
        return False
    return None


def _cache_event_kind(hit: bool | None) -> str:
    if hit is True:
        return "remote_cache_hit"
    if hit is False:
        return "cache_miss"
    return "action_cache_observed"


def _cache_event_key(
    target_label: str | None,
    mnemonic: str,
    digest: str | None,
    index: int,
) -> str:
    target = target_label or "unknown-target"
    return f"{target}:{mnemonic}:{digest or index}"


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
