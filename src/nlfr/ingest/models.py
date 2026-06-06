"""Typed records emitted by evidence parsers before SQLite ingest."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TruthLabels:
    source_kind: str
    confidence: str
    evidence_refs: list[str]
    redaction_state: str = "safe"


@dataclass
class TargetEvidence(TruthLabels):
    label: str = ""
    target_kind: str | None = None
    status: str | None = None


@dataclass
class ActionEvidence(TruthLabels):
    action_key: str = ""
    target_label: str | None = None
    mnemonic: str | None = None
    status: str | None = None


@dataclass
class CacheEventEvidence(TruthLabels):
    event_key: str = ""
    event_kind: str | None = None
    hit: bool | None = None
    digest: str | None = None
    target_label: str | None = None
    action_key: str | None = None


@dataclass
class FailureEvidence(TruthLabels):
    failure_key: str = ""
    failure_kind: str | None = None
    message: str = ""
    span: dict[str, object] | None = None


@dataclass
class EvidenceBundle:
    targets: list[TargetEvidence] = field(default_factory=list)
    actions: list[ActionEvidence] = field(default_factory=list)
    cache_events: list[CacheEventEvidence] = field(default_factory=list)
    failures: list[FailureEvidence] = field(default_factory=list)

    def extend(self, other: "EvidenceBundle") -> None:
        self.targets.extend(other.targets)
        self.actions.extend(other.actions)
        self.cache_events.extend(other.cache_events)
        self.failures.extend(other.failures)

    def counts(self) -> dict[str, int]:
        return {
            "targets": len(self.targets),
            "actions": len(self.actions),
            "cache_events": len(self.cache_events),
            "failures": len(self.failures),
        }
