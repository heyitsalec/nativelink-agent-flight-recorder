#!/usr/bin/env python3
"""Emit a research-only fleet claim matrix for honesty doc sync."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nlfr.projectors.remote_execution import UNSUPPORTED_REMOTE_EXECUTION_CLAIMS


def build_matrix() -> dict:
    claims = []
    for claim_id in UNSUPPORTED_REMOTE_EXECUTION_CLAIMS:
        row = {
            "claim_id": claim_id,
            "v1_policy": "out_of_scope" if claim_id != "worker_identity" else "conditional",
            "parser": None,
            "sqlite_proof_block": None,
            "canvas_lens": "remote_boundary",
            "one_pager": "explicitly_unproven",
        }
        if claim_id == "worker_identity":
            row.update(
                {
                    "parser": "nlfr.ingest.worker_admin_stdout.parse_worker_admin_stdout",
                    "sqlite_proof_block": "worker_admin_identity_v1",
                    "collectable_when": "nativelink.stdout.txt contains Worker <name> started lines",
                    "projection_behavior": "unsupported_claims_for_run drops worker_identity when direct evidence exists",
                }
            )
        elif claim_id == "queue_time":
            row["blocker"] = "no BEP/execution-log queue timestamp parser"
        elif claim_id == "scheduler_assignment":
            row["blocker"] = "no scheduler stdout / admin API assignment parser"
        elif claim_id == "action_placement":
            row["blocker"] = "no per-action worker correlation parser beyond identity lines"
        elif claim_id == "load_distribution":
            row["blocker"] = "two-worker config proves endpoints only, not work distribution"
        claims.append(row)

    return {
        "status": "research_only",
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_kind": "derived_v1",
        "confidence": "high",
        "redaction_state": "safe",
        "evidence_refs": [
            "script:fleet-claims-audit.sh",
            "docs/dags/future-fleet-claims.md",
            "src/nlfr/projectors/remote_execution.py",
            "docs/ONE_PAGER.md",
        ],
        "broker_rule": "no implement workers for fleet/scheduler UI without new direct evidence parsers",
        "supported_collectable_ceiling": [
            "remote_executor configured (Bazel --remote_executor)",
            "worker_endpoints_ready (configured workers + live endpoints)",
            "worker_identity when admin stdout captured",
        ],
        "claims": claims,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build_matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
