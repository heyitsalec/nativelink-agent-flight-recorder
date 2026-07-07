"""SQLite ingest for parsed evidence bundles."""

from __future__ import annotations

import sqlite3

from nlfr.db.ingest import (
    upsert_action,
    upsert_artifact_reference,
    upsert_cache_event,
    upsert_failure,
    upsert_target,
)
from nlfr.ingest.models import EvidenceBundle


def ingest_evidence_bundle(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    run_stable_key: str,
    bundle: EvidenceBundle,
) -> dict[str, int]:
    """Ingest parsed evidence into the NLFR data spine."""

    target_ids: dict[str, str] = {}
    action_ids: dict[str, str] = {}

    for target in bundle.targets:
        target_ids[target.label] = upsert_target(
            conn,
            stable_key=f"{run_stable_key}:target:{target.label}",
            run_id=run_id,
            label=target.label,
            target_kind=target.target_kind,
            status=target.status,
            source_kind=target.source_kind,
            confidence=target.confidence,
            evidence_refs=target.evidence_refs,
            redaction_state=target.redaction_state,
        )

    for action in bundle.actions:
        target_id = _target_id(conn, target_ids, run_id, action.target_label)
        action_ids[action.action_key] = upsert_action(
            conn,
            stable_key=f"{run_stable_key}:action:{action.action_key}",
            run_id=run_id,
            target_id=target_id,
            action_key=action.action_key,
            mnemonic=action.mnemonic,
            status=action.status,
            source_kind=action.source_kind,
            confidence=action.confidence,
            evidence_refs=action.evidence_refs,
            redaction_state=action.redaction_state,
        )

    for event in bundle.cache_events:
        target_id = _target_id(conn, target_ids, run_id, event.target_label)
        action_id = action_ids.get(event.action_key or "")
        upsert_cache_event(
            conn,
            stable_key=f"{run_stable_key}:cache_event:{event.event_key}",
            run_id=run_id,
            target_id=target_id,
            action_id=action_id,
            event_key=event.event_key,
            event_kind=event.event_kind,
            hit=event.hit,
            digest=event.digest,
            source_kind=event.source_kind,
            confidence=event.confidence,
            evidence_refs=event.evidence_refs,
            redaction_state=event.redaction_state,
        )

    for failure in bundle.failures:
        upsert_failure(
            conn,
            stable_key=f"{run_stable_key}:failure:{failure.failure_key}",
            run_id=run_id,
            failure_kind=failure.failure_kind,
            message=failure.message,
            span=failure.span,
            source_kind=failure.source_kind,
            confidence=failure.confidence,
            evidence_refs=failure.evidence_refs,
            redaction_state=failure.redaction_state,
        )

    for reference in bundle.artifact_references:
        target_id = _target_id(conn, target_ids, run_id, reference.target_label)
        upsert_artifact_reference(
            conn,
            stable_key=f"{run_stable_key}:artifact_reference:{reference.reference_key}",
            run_id=run_id,
            target_id=target_id,
            reference_key=reference.reference_key,
            name=reference.name,
            uri=reference.uri,
            local_path=reference.local_path,
            declared_digest=reference.declared_digest,
            declared_size_bytes=reference.declared_size_bytes,
            computed_digest=reference.computed_digest,
            digest_verified=reference.digest_verified,
            presence=reference.presence,
            verification_note=reference.verification_note,
            source_kind=reference.source_kind,
            confidence=reference.confidence,
            evidence_refs=reference.evidence_refs,
            redaction_state=reference.redaction_state,
        )

    return bundle.counts()


def _target_id(
    conn: sqlite3.Connection,
    target_ids: dict[str, str],
    run_id: str,
    label: str | None,
) -> str | None:
    if label is None:
        return None
    if label in target_ids:
        return target_ids[label]
    row = conn.execute(
        "SELECT id FROM targets WHERE run_id = ? AND label = ?",
        (run_id, label),
    ).fetchone()
    if row is None:
        return None
    target_ids[label] = row["id"]
    return row["id"]
