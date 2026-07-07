"""Honest v1 retention semantics for M9 multi-run history.

NLFR v1 never auto-purges: discovery is index-only and lifecycle is
operator-managed (see the constants below). The *managed* mechanism is the
explicit, operator-consented ``nlfr db gc`` command (see
:func:`nlfr.commands.db_cmd.db_gc`), which deletes whole run groups' evidence —
rows and on-disk artifact trees — only under ``--apply`` and never orphans
referenced evidence. This module still asserts "no auto-purge": ``db gc`` is a
consented act an operator invokes, not an automatic sweep, so the policy claims
below remain true.
"""

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
