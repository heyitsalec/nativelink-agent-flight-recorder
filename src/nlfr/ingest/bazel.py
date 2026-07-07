"""Parsers for compact Bazel evidence artifacts."""

from __future__ import annotations

import gzip
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nlfr.ingest.models import (
    ActionEvidence,
    ArtifactReferenceEvidence,
    CacheEventEvidence,
    EvidenceBundle,
    FailureEvidence,
    TargetEvidence,
)
from nlfr.ingest.verification import (
    CasProbe,
    DigestFunctionInfo,
    build_reference,
    detect_digest_function,
    iter_bep_file_references,
)

# The Bazel versions whose BEP + execution-log + profile shapes NLFR pins with
# proto-derived, populator-verified matrix fixtures (7.x LTS line and current 9.x
# line). This is the SINGLE source of truth for the tested anchors: the matrix
# fixture directories (tests/fixtures/bazel/matrix/<version>/) mirror it, asserted
# by tests/test_ingest_bazel_matrix.py::test_matrix_anchor_constant_matches_fixtures.
# It is a bounded honesty claim ("tested against these"), NOT "supports only these":
# versions between/around the anchors are EXPECTED to parse, and the out-of-range
# warning is a non-blocking "untested version" signal, never a hard failure.
TESTED_BAZEL_VERSIONS: tuple[str, ...] = ("7.4.1", "9.0.0")
TESTED_BAZEL_MAJORS: tuple[int, ...] = (7, 9)

_BAZEL_RELEASE_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
# `bazel version` prints a line like "Build label: 7.4.1"; a pre-release build may
# print "Build label: 8.0.0-pre.20240101.1" or an empty label for a dev build. The
# whitespace after the colon is [ \t] (NOT \s) so an empty label does not greedily
# consume the newline and match the next line's first token.
_BUILD_LABEL_RE = re.compile(r"^[ \t]*Build label:[ \t]*(\S+)", re.MULTILINE)


def bazel_major(version: str | None) -> int | None:
    """Return the major version int from a Bazel release string, or ``None``.

    Accepts ``"7.4.1"``, ``"9.0.0"``, a ``"8.0.0-pre.20240101.1"`` pre-release, or
    a leading-``v`` form; returns ``None`` for an empty/unparseable string (a dev
    build with no release label, or a non-version string). ``None`` in means
    ``None`` out — the version is *unknown*, which is never treated as out-of-range.
    """

    if not version:
        return None
    match = _BAZEL_RELEASE_RE.search(version)
    if match is None:
        return None
    return int(match.group(1))


def is_tested_bazel_major(version: str | None) -> bool:
    """True when ``version``'s major is one NLFR pins matrix fixtures for.

    An unknown/unparseable version is ``False`` here (it is not a tested major),
    but callers distinguish "unknown" from "out-of-range" via
    :func:`out_of_range_bazel_warning`, which stays silent on unknown.
    """

    major = bazel_major(version)
    return major is not None and major in TESTED_BAZEL_MAJORS


def out_of_range_bazel_warning(version: str | None) -> str | None:
    """A non-blocking "untested Bazel version" warning, or ``None`` to stay silent.

    Returns ``None`` — no warning — when the version is unknown/unparseable (never
    fabricate an out-of-range claim from a version NLFR could not read) OR when the
    major is one of the tested anchors. Returns an honest one-line warning naming
    the observed version and the tested anchors when the major is outside them.
    This is advisory only; no caller changes an exit code or fabricates evidence
    because of it.
    """

    major = bazel_major(version)
    if major is None or major in TESTED_BAZEL_MAJORS:
        return None
    anchors = ", ".join(TESTED_BAZEL_VERSIONS)
    return (
        f"Bazel {version} (major {major}) is outside NLFR's tested version anchors "
        f"({anchors}); evidence still ingests, but parser behavior at this version "
        "is not pinned by the matrix. See docs/wiki/reference/bazel-version-matrix.md."
    )


def bazel_release_from_version_output(text: str | None) -> str | None:
    """Extract the release string from ``bazel version`` stdout, or ``None``.

    Parses the ``Build label: <release>`` line real Bazel prints. Returns ``None``
    when there is no non-empty label (a source/dev build prints an empty label) so
    the caller records the version as *unknown* rather than guessing one.
    """

    if not text:
        return None
    match = _BUILD_LABEL_RE.search(text)
    if match is None:
        return None
    label = match.group(1).strip()
    return label or None


def parse_bazel_bep(
    path: str | Path,
    *,
    source_kind: str = "collectable_v1",
    confidence: str = "high",
    evidence_ref: str | None = None,
    verify_artifacts: bool = True,
    artifact_base: str | Path | None = None,
    cas_probe: CasProbe | None = None,
) -> EvidenceBundle:
    """Parse Bazel Build Event Protocol JSON lines or JSON objects.

    When ``verify_artifacts`` is set (the default), every file the BEP references
    is independently checked: local bytes have their SHA-256 recomputed and
    compared against the BEP-declared digest, while remote-only URIs are labeled
    ``unverified_remote_reference``. ``artifact_base`` resolves relative and
    ``file://`` paths; it defaults to the directory containing the BEP file.

    ``cas_probe`` is an OPTIONAL injectable CAS probe (issue #81 part A). With no
    probe (the default) remote references keep the historical
    ``unverified_remote_reference`` downgrade — unchanged behavior. When supplied,
    each remote reference is checked against the CAS and earns an honest
    ``remote_verified`` / ``remote_present`` / ``remote_mismatch`` /
    ``remote_missing`` label. NLFR ships no probe backend in part A.
    """

    evidence_path = Path(path)
    evidence_refs = [_evidence_ref(evidence_path, evidence_ref)]
    resolved_base = (
        Path(artifact_base) if artifact_base is not None else evidence_path.parent
    )
    targets: dict[str, TargetEvidence] = {}
    actions: dict[str, ActionEvidence] = {}
    failures: dict[str, FailureEvidence] = {}
    artifact_references: dict[str, ArtifactReferenceEvidence] = {}

    events = _load_json_events(evidence_path)
    # Resolve the build's digest function once up front (from the started event's
    # optionsDescription / optionsParsed command line) so per-file verification can
    # skip comparison when the declared digest is not a recomputable SHA-256.
    digest_function = detect_digest_function(events)

    for index, event in enumerate(events, start=1):
        event_id = event.get("id", {})
        label = _bep_label(event_id, event)

        if verify_artifacts:
            _collect_artifact_references(
                artifact_references,
                event=event,
                label=label,
                index=index,
                source_kind=source_kind,
                evidence_refs=evidence_refs,
                artifact_base=resolved_base,
                digest_function=digest_function,
                cas_probe=cas_probe,
            )

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
        artifact_references=list(artifact_references.values()),
    )


def extract_bep_started_at(path: str | Path) -> str | None:
    """Return the build's REAL start time from the BEP ``started`` event, or ``None``.

    The Bazel Build Event Protocol's ``started`` event records the moment the build
    actually began — as ``startTime`` (an ISO-8601 timestamp, newer Bazel) and/or
    ``startTimeMillis`` (Unix epoch milliseconds, older Bazel). This reads that
    evidence-recorded instant and renders it as an ISO-8601 UTC string (``...Z``).

    It returns ``None`` when the BEP has no ``started`` event or no usable start
    field — so ingest can carry a start time it can *observe in the evidence*, but
    NEVER fabricates one from wall-clock ingest time. A run with no observable
    start stays age-unknown, which `db gc` refuses to auto-delete.
    """

    for event in _load_json_events(Path(path)):
        started = event.get("started")
        if not isinstance(started, dict):
            continue
        # Prefer the explicit ISO timestamp when present (newer Bazel).
        iso = started.get("startTime")
        if isinstance(iso, str) and iso.strip():
            normalized = _normalize_iso_utc(iso)
            if normalized is not None:
                return normalized
        # Fall back to epoch milliseconds (older Bazel; also our fixtures).
        millis = started.get("startTimeMillis")
        if isinstance(millis, bool):
            continue
        if isinstance(millis, int):
            return _millis_to_iso_utc(millis)
        if isinstance(millis, float):
            return _millis_to_iso_utc(int(millis))
        if isinstance(millis, str) and millis.strip().lstrip("-").isdigit():
            return _millis_to_iso_utc(int(millis))
    return None


def _millis_to_iso_utc(millis: int) -> str:
    """Render Unix epoch milliseconds as an ISO-8601 UTC timestamp (``...Z``)."""

    seconds, millis_part = divmod(millis, 1000)
    moment = datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=millis_part * 1000)
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _normalize_iso_utc(value: str) -> str | None:
    """Normalize an ISO-8601 timestamp string to UTC ``...Z`` form, or ``None``."""

    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (
        moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _collect_artifact_references(
    references: dict[str, ArtifactReferenceEvidence],
    *,
    event: dict[str, Any],
    label: str | None,
    index: int,
    source_kind: str,
    evidence_refs: list[str],
    artifact_base: Path,
    digest_function: DigestFunctionInfo,
    cas_probe: CasProbe | None = None,
) -> None:
    for offset, file_payload in enumerate(iter_bep_file_references(event)):
        reference = build_reference(
            file_payload,
            label=label,
            index=index * 1000 + offset,
            source_kind=source_kind,
            evidence_refs=evidence_refs,
            artifact_base=artifact_base,
            digest_function=digest_function,
            cas_probe=cas_probe,
        )
        if reference is None:
            continue
        # First observation of a stable reference wins; later duplicates (e.g. the
        # same file echoed in importantOutput) are ignored to keep counts honest.
        references.setdefault(reference.reference_key, reference)


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


def extract_bep_tool_version(path: str | Path) -> str | None:
    """Return the Bazel version that produced this BEP, or ``None``.

    The Build Event Protocol's ``started`` event (``BuildStarted``) carries
    ``buildToolVersion`` — the exact build tool release string, e.g. ``"7.4.1"``
    or ``"9.0.0"`` (proto field ``build_tool_version`` = 3, present across the
    7.x LTS line and the 9.x line alike; see ``tests/fixtures/bazel/matrix``).
    NLFR reads it verbatim from the evidence so an exported proof packet can state
    which build tool produced the evidence.

    It returns ``None`` when no ``started`` event carries a non-empty
    ``buildToolVersion`` — older evidence, a hand-authored fixture that omits it,
    or a non-Bazel BEP. NLFR then records the build tool version as *unknown*
    rather than fabricating one. Extra 9.x-only started fields (``host``, ``user``)
    are simply ignored; a version is read whenever the field is present.
    """

    for event in _load_json_events(Path(path)):
        started = event.get("started")
        if not isinstance(started, dict):
            continue
        version = started.get("buildToolVersion")
        if isinstance(version, str) and version.strip():
            return version.strip()
    return None


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
