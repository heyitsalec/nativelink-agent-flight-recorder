# Future fleet claims — research-only DAG

**Status:** wave-1 done (research only; no UI implement workers)  
**Parent:** [future-execution-ladder.md](future-execution-ladder.md) · PER-1058  
**Handoffs:** `docs/sessions/handoffs/future-fleet-claims/wave-1/`

## Objective

Keep honesty docs synchronized with the **actual evidence ceiling** for fleet,
scheduler, and worker-correlation claims. Reject Harmony-style fake worker
personas or dashboard cosplay without SQLite proof blocks.

## Wave-1 deliverables

| Item | Path |
|------|------|
| Claim matrix script | `scripts/fleet_claims_audit.py` |
| Proof wrapper | `scripts/fleet-claims-audit.sh` |
| Honesty doc sync | `docs/ONE_PAGER.md` (explicitly unproven footnote) |
| Matrix output | `data/fleet-claims-audit/claim-matrix.json` |

## Claim matrix (ONE_PAGER ↔ audit)

| ONE_PAGER (unproven) | Matrix `claim_id` | v1 policy |
|----------------------|-------------------|-----------|
| Worker identity | `worker_identity` | conditional (M7 parser when stdout captured) |
| Scheduler assignment | `scheduler_assignment` | out_of_scope |
| Queue time | `queue_time` | out_of_scope |
| Action placement | `action_placement` | out_of_scope |
| Load distribution / multi-machine fleet | `load_distribution` | out_of_scope |

Org-scale history is narrative-only; not a separate matrix row.

## Proof command

```bash
./scripts/fleet-claims-audit.sh
uv run pytest tests/test_fleet_claims_audit.py -q
```

Writes `data/fleet-claims-audit/claim-matrix.json` with `source_kind: derived_v1`.

**Supported collectable ceiling today:** remote executor configured,
`worker_endpoints_ready`, and `worker_identity` when admin stdout is captured.

## Broker rule

| Action | Allowed |
|--------|---------|
| Run `fleet-claims-audit.sh` | Yes |
| Update ONE_PAGER / Remote Boundary copy from matrix | Yes |
| Spawn canvas fleet dashboard workers | **No** |
| Claim queue time / placement without new parser | **No** |

## Exit criteria for a future implement DAG

A new `fleet-evidence-v1` broker DAG may spawn implement workers only when
architecture track Phase 3 names a **new collectable claim** with:

1. Parser module + pytest on real fixtures
2. SQLite proof block kind + ingest path
3. Projection update with truth labels
4. Canvas Remote Boundary lens change (not a new fleet ops UI)
