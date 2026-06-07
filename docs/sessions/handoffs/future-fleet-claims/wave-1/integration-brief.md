# Wave 1 Integration Brief — Future fleet claims (research only)

**Date:** 2026-06-06  
**Coordinator:** `coord-future-fleet-claims`  
**Status:** DONE  
**Ceiling:** `research_only` (`derived_v1`, `high`)

---

## Landed

| Layer | Artifact | Claim |
|-------|----------|-------|
| Script | `scripts/fleet_claims_audit.py` | Emits claim matrix from `UNSUPPORTED_REMOTE_EXECUTION_CLAIMS` |
| Wrapper | `scripts/fleet-claims-audit.sh` | Proof command → `data/fleet-claims-audit/claim-matrix.json` |
| Tests | `tests/test_fleet_claims_audit.py` | 4 fixture-free contract tests |
| Docs | `docs/ONE_PAGER.md` | Explicitly-unproven footnote + matrix link |
| Sample | `docs/proof-samples/fleet-claims-matrix-sample.json` | Schema mirror for evaluators |
| DAG | `docs/dags/future-fleet-claims.md` | ONE_PAGER ↔ matrix mapping + broker rule |

---

## Proof

```bash
./scripts/fleet-claims-audit.sh
uv run pytest tests/test_fleet_claims_audit.py -q
# 4 passed
```

---

## Honesty / claim boundary

**Supported collectable ceiling today:**

- Remote executor configured (`Bazel --remote_executor`)
- `worker_endpoints_ready` (configured workers + live endpoints)
- `worker_identity` when admin stdout is captured (conditional parser path)

**Explicitly unproven (matrix rows):**

| ONE_PAGER | Matrix `claim_id` | v1 policy |
|-----------|-------------------|-----------|
| Worker identity | `worker_identity` | conditional |
| Scheduler assignment | `scheduler_assignment` | out_of_scope |
| Queue time | `queue_time` | out_of_scope |
| Action placement | `action_placement` | out_of_scope |
| Load distribution / multi-machine fleet | `load_distribution` | out_of_scope |

Org-scale history is narrative-only in ONE_PAGER; not a separate matrix row.

---

## Broker rule (unchanged)

| Action | Allowed |
|--------|---------|
| Run `fleet-claims-audit.sh` | Yes |
| Update ONE_PAGER / Remote Boundary copy from matrix | Yes |
| Spawn canvas fleet dashboard workers | **No** |
| Claim queue time / placement without new parser | **No** |

A future `fleet-evidence-v1` implement DAG requires parser + SQLite proof block + projection + canvas Remote Boundary lens change per `docs/dags/future-fleet-claims.md`.

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-ffc-w1-*.md`
- DAG mirror: `docs/dags/future-fleet-claims.md`
