"""Honest v1 retention semantics for M9 multi-run history."""

from __future__ import annotations

from typing import Any

# Policy mode identifiers (v1 ceiling).
INDEX_ONLY = "index_only"
NO_AUTO_PURGE = "no_auto_purge"
OPERATOR_MANAGED = "operator_managed"


def retention_policy_summary() -> dict[str, Any]:
    """Return the canonical v1 retention policy descriptor."""

    return {
        "version": 1,
        "discovery": INDEX_ONLY,
        "purge": NO_AUTO_PURGE,
        "lifecycle": OPERATOR_MANAGED,
    }


def proof_retention_block() -> dict[str, Any]:
    """Minimal retention notes for proof packet export."""

    return {
        **retention_policy_summary(),
        "claims": [
            "Run-group discovery is index-only via nlfr compare index.",
            "NLFR v1 does not auto-purge SQLite rows or artifact files.",
            "Artifact and database growth is operator-managed.",
        ],
        "source_kind": "derived_v1",
        "confidence": "high",
        "evidence_refs": [],
        "redaction_state": "safe",
    }
