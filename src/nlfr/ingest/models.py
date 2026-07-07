"""Typed records emitted by evidence parsers before SQLite ingest."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TruthLabels:
    """Truth-label fields required on projected evidence records."""

    source_kind: str
    confidence: str
    evidence_refs: list[str]
    redaction_state: str = "safe"


@dataclass
class TargetEvidence(TruthLabels):
    """Parsed Bazel target status evidence."""

    label: str = ""
    target_kind: str | None = None
    status: str | None = None


@dataclass
class ActionEvidence(TruthLabels):
    """Parsed Bazel action completion evidence."""

    action_key: str = ""
    target_label: str | None = None
    mnemonic: str | None = None
    status: str | None = None


@dataclass
class CacheEventEvidence(TruthLabels):
    """Parsed cache hit, miss, or observation evidence."""

    event_key: str = ""
    event_kind: str | None = None
    hit: bool | None = None
    digest: str | None = None
    target_label: str | None = None
    action_key: str | None = None


@dataclass
class FailureEvidence(TruthLabels):
    """Parsed build or target failure evidence."""

    failure_key: str = ""
    failure_kind: str | None = None
    message: str = ""
    span: dict[str, object] | None = None


@dataclass
class ArtifactReferenceEvidence(TruthLabels):
    """A file referenced by ingested BEP, with independent verification state.

    NLFR does not trust the build tool's self-reports: for every artifact BEP
    references it recomputes the local SHA-256 (when the bytes are on disk) and
    compares it against the BEP-declared digest. Remote-only references
    (``bytestream://`` and other CAS URIs) cannot be verified locally: with no CAS
    probe they are labeled ``unverified_remote_reference`` per bazelbuild/bazel#23250.
    When an optional CAS probe is injected (issue #81 part A), a remote reference
    instead earns an honest ``remote_verified`` / ``remote_present`` /
    ``remote_mismatch`` / ``remote_missing`` label from the probe's verdict.
    """

    reference_key: str = ""
    name: str | None = None
    uri: str | None = None
    local_path: str | None = None
    declared_digest: str | None = None
    declared_size_bytes: int | None = None
    computed_digest: str | None = None
    # True when recomputed SHA-256 matched the BEP-declared digest, False on
    # mismatch, None when no local comparison was possible (missing/remote, no
    # declared digest, or a declared digest NLFR cannot prove is SHA-256).
    digest_verified: bool | None = None
    # One of local_verified | local_present | local_mismatch | missing |
    # unverified_remote_reference | remote_verified | remote_present |
    # remote_mismatch | remote_missing. ``local_present`` means the bytes are on
    # disk but the declared digest was not cross-checked because it is not a
    # recomputable SHA-256 (a non-default --digest_function or a non-64-hex digest).
    # The remote_* values are only produced when an optional CAS probe is injected
    # (issue #81 part A); with no probe a remote reference stays
    # unverified_remote_reference.
    presence: str = "missing"
    verification_note: str | None = None
    target_label: str | None = None


@dataclass
class EvidenceBundle:
    """Parsed Bazel evidence grouped by SQLite ingest table."""

    targets: list[TargetEvidence] = field(default_factory=list)
    actions: list[ActionEvidence] = field(default_factory=list)
    cache_events: list[CacheEventEvidence] = field(default_factory=list)
    failures: list[FailureEvidence] = field(default_factory=list)
    artifact_references: list[ArtifactReferenceEvidence] = field(default_factory=list)

    def extend(self, other: "EvidenceBundle") -> None:
        """Append all records from another bundle."""

        self.targets.extend(other.targets)
        self.actions.extend(other.actions)
        self.cache_events.extend(other.cache_events)
        self.failures.extend(other.failures)
        self.artifact_references.extend(other.artifact_references)

    def counts(self) -> dict[str, int]:
        """Return per-table record counts for ingest summaries."""

        return {
            "targets": len(self.targets),
            "actions": len(self.actions),
            "cache_events": len(self.cache_events),
            "failures": len(self.failures),
            "artifact_references": len(self.artifact_references),
        }
