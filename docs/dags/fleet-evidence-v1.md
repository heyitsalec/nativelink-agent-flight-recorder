# Fleet evidence v1 — broker DAG (stdout ingest breadth)

**Status:** wave-1 handoffs done (`DONE_WITH_CONCERNS` — `fel-w1-agent-coldwarm-attach` pending)  
**Parent:** [future-fleet-claims.md](future-fleet-claims.md) · PER-1058  
**Handoffs:** `docs/sessions/handoffs/fleet-evidence-v1/wave-1/` · wave-0: `wave-0/`

## Objective

Broaden **collectable** fleet evidence by attaching `nativelink.stdout.txt` (and
stderr for provenance) into `artifact_root` **before** `nlfr ingest` on remote-exec
proof scripts, so the M7 `worker_admin_stdout` parser can promote
`worker_identity` when admin lines match.

Reject fleet dashboard cosplay, scheduler claims, and queue/placement correlation
without new proof block kinds.

## Wave-1 deliverables

| Item | Path | Status |
|------|------|--------|
| Local-exec attach | `scripts/local-exec-proof.sh` | **landed** (wave-0) |
| Worker-evidence live path | `scripts/worker-evidence-proof.sh` | **landed** (wave-0) |
| Agent-loop attach | `scripts/agent-loop-proof.sh` | **pending** (`fel-w1-agent-coldwarm-attach`) |
| Cold-warm attach | `scripts/cold-warm-cache-proof.sh` | **pending** (`fel-w1-agent-coldwarm-attach`) |
| Research | `docs/sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md` | wave-0 |
| Parser (pre-existing) | `src/nlfr/ingest/worker_admin_stdout.py` | unchanged |
| Handoffs | `docs/sessions/handoffs/fleet-evidence-v1/wave-1/` | wave-1 closed |

## Claim ceiling (wave-1 target)

| Claim | Status |
|-------|--------|
| `worker_endpoints_ready` | `collectable_v1` (unchanged — readiness probe) |
| `worker_identity` | Conditional — when stdout attached **and** M7 regex matches |
| stdout pre-ingest on four proof scripts | **Target:** local-exec + worker-evidence + agent-loop + cold-warm |
| stdout pre-ingest on committed branch | **Today:** local-exec + worker-evidence only until attach worker lands |
| `scheduler_assignment` | out_of_scope |
| `queue_time` | out_of_scope |
| `action_placement` | out_of_scope |
| `load_distribution` | out_of_scope |

Ceiling label: `stdout_ingest_breadth` (`collectable_v1`, `high`).

## Proof commands (local — GHA offline)

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh \
  scripts/agent-loop-proof.sh scripts/cold-warm-cache-proof.sh
./scripts/worker-evidence-proof.sh   # fixture replay when nativelink/bazel absent
```

Parent proof gates substitute for CI while GHA is offline:
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Remaining breadth gaps (post wave-1)

| Priority | Gap |
|----------|-----|
| P1 | Land `fel-w1-agent-coldwarm-attach` — commit agent-loop + cold-warm attach |
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
