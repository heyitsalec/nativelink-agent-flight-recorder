# Fleet evidence v1 — broker DAG (stdout ingest breadth)

**Status:** wave-0 done (local-exec + worker-evidence attach path)  
**Parent:** [future-fleet-claims.md](future-fleet-claims.md) · PER-1058  
**Handoffs:** `docs/sessions/handoffs/fleet-evidence-v1/wave-0/`

## Objective

Broaden **collectable** fleet evidence by attaching `nativelink.stdout.txt` (and
stderr for provenance) into `artifact_root` **before** `nlfr ingest` on remote-exec
proof scripts, so the M7 `worker_admin_stdout` parser can promote
`worker_identity` when admin lines match.

Reject fleet dashboard cosplay, scheduler claims, and queue/placement correlation
without new proof block kinds.

## Wave-0 deliverables

| Item | Path |
|------|------|
| Local-exec attach | `scripts/local-exec-proof.sh` — `write_artifact` for stdout/stderr |
| Worker-evidence live path | `scripts/worker-evidence-proof.sh` — no post-run stdout `cp` |
| Research | `docs/sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md` |
| Parser (pre-existing) | `src/nlfr/ingest/worker_admin_stdout.py` |
| Proof wrapper | `scripts/worker-evidence-proof.sh` → `data/worker-evidence-proof/summary.json` |

## Claim ceiling (wave-0)

| Claim | Status after wave-0 |
|-------|---------------------|
| `worker_endpoints_ready` | `collectable_v1` (unchanged — readiness probe) |
| `worker_identity` | Conditional — when stdout attached **and** M7 regex matches |
| `scheduler_assignment` | out_of_scope |
| `queue_time` | out_of_scope |
| `action_placement` | out_of_scope |
| `load_distribution` | out_of_scope |

## Proof commands

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh
./scripts/worker-evidence-proof.sh   # fixture replay when nativelink/bazel absent
```

## Remaining breadth gaps (next waves)

| Priority | Script | Gap |
|----------|--------|-----|
| P1 | `scripts/agent-loop-proof.sh` | stdout listed in summary only; not in artifact_root pre-ingest |
| P1 | `scripts/cold-warm-cache-proof.sh` | same |
| P2 | Real NativeLink stdout sample | validate M7 regex against production wording |
| P3 | stderr triage playbook | provenance-only; no claim promotion |

## Broker rule

| Action | Allowed |
|--------|---------|
| Attach stdout/stderr pre-ingest on proof scripts | Yes |
| Extend M7 parser with fixture-backed regex | Yes (new wave) |
| Spawn canvas fleet ops dashboard workers | **No** |
| Claim scheduler / queue / placement without new proof block | **No** |

## Exit criteria for projection / canvas wave

A later wave may touch projection + Remote Boundary lens only when:

1. SQLite has `worker_admin_identity_v1` rows from live or fixture ingest
2. Proof export includes the block with truth labels
3. Canvas copy reflects matrix from `scripts/fleet_claims_audit.py`
