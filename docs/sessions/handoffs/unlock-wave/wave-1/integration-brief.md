# Wave 1 Integration Brief — Unlock wave (LRE + fleet claims)

**Date:** 2026-06-06  
**Coordinator:** `coord-unlock-ship`  
**Status:** DONE  
**Branch:** `feat/lre-fleet-unlocks`  
**Ceiling:** dual close — `lre_substrate_ready` + `research_only` fleet matrix

---

## Purpose

Consolidate wave-0 sub-DAG closes into a single ship gate for the unlock wave.
Parent broker may open one PR for LRE substrate proof + fleet claim honesty without
inventing fleet UI or Nix LRE toolchain claims.

---

## Sub-DAG synthesis

| Sub-DAG | Wave | Coordinator | Ceiling | Handoffs |
|---------|------|-------------|---------|----------|
| `lre-proof` | wave-2 | `coord-lre-proof` | `lre_substrate_ready` (`collectable_v1`, `medium`) | [`lre-proof/wave-2/`](../../lre-proof/wave-2/) |
| `future-fleet-claims` | wave-1 | `coord-future-fleet-claims` | `research_only` (`derived_v1`, `high`) | [`future-fleet-claims/wave-1/`](../../future-fleet-claims/wave-1/) |

---

## Landed (combined)

### LRE substrate (`lre-proof` wave-2)

| Layer | Artifact | Claim |
|-------|----------|-------|
| Config | `demo/nativelink/lre.json5` | LRE ports 50071/50081, one local worker |
| Docs | `demo/nativelink/README.md` | Phase-1 substrate + `claim_boundary` |
| Script | `scripts/lre-proof.sh` | Probe → blocker or delegate → `summary.json` |
| Samples | `docs/proof-samples/lre-proof-*-sample.json` | Schema mirrors script output |
| Tests | `tests/test_lre_proof.py` | 4 fixture-backed contract tests |
| CI | `.github/workflows/nlfr-proof.yml` | `lre-proof-probe` uploads `summary.json` or blocker |
| DAG | `docs/dags/lre-proof.md` | Ceiling synced to `lre_substrate_ready` |

### Fleet claims research (`future-fleet-claims` wave-1)

| Layer | Artifact | Claim |
|-------|----------|-------|
| Script | `scripts/fleet_claims_audit.py` | Emits claim matrix from `UNSUPPORTED_REMOTE_EXECUTION_CLAIMS` |
| Wrapper | `scripts/fleet-claims-audit.sh` | Proof command → `data/fleet-claims-audit/claim-matrix.json` |
| Tests | `tests/test_fleet_claims_audit.py` | 4 fixture-free contract tests |
| Docs | `docs/ONE_PAGER.md` | Explicitly-unproven footnote + matrix link |
| Sample | `docs/proof-samples/fleet-claims-matrix-sample.json` | Schema mirror for evaluators |
| DAG | `docs/dags/future-fleet-claims.md` | ONE_PAGER ↔ matrix mapping + broker rule |

---

## Parent proof gates (passed)

```bash
cd /Users/alecbot/Documents/nativelink-agent-flight-recorder
uv run pytest -q
# 92 passed, 1 skipped

uv run pytest tests/test_lre_proof.py -q
# 4 passed

uv run pytest tests/test_fleet_claims_audit.py -q
# 4 passed

bash -n scripts/lre-proof.sh
./scripts/fleet-claims-audit.sh
# → data/fleet-claims-audit/claim-matrix.json
```

Nix green path (CI or local when toolchain available):

```bash
nix develop --command ./scripts/lre-proof.sh
# → data/lre-proof/summary.json with status: lre_substrate_ready
```

---

## Honesty boundaries (unchanged)

### LRE — supported today

- LRE NativeLink server substrate configured (`lre.json5`)
- Cache-only and local-exec smoke on dedicated LRE ports
- Two-worker endpoint readiness probes

### LRE — unsupported until Nix LRE toolchain

- Hermetic `bazel --config=lre` cache parity
- `lre.bazelrc` wiring via `flake.nix` + `MODULE.bazel`
- Fleet dashboards, queue-time / action correlation

Phase 2 remains blocked on TraceMachina Nix LRE wiring per README **Future full-LRE** section.
Tracked by `coord-lre-nix-phase3` (wave-1 frontier, not this ship gate).

### Fleet — supported collectable ceiling today

- Remote executor configured (`Bazel --remote_executor`)
- `worker_endpoints_ready` (configured workers + live endpoints)
- `worker_identity` when admin stdout is captured (conditional parser path)

### Fleet — explicitly unproven (matrix rows)

| ONE_PAGER | Matrix `claim_id` | v1 policy |
|-----------|-------------------|-----------|
| Worker identity | `worker_identity` | conditional |
| Scheduler assignment | `scheduler_assignment` | out_of_scope |
| Queue time | `queue_time` | out_of_scope |
| Action placement | `action_placement` | out_of_scope |
| Load distribution / multi-machine fleet | `load_distribution` | out_of_scope |

Org-scale history is narrative-only in ONE_PAGER; not a separate matrix row.

---

## Broker rules (unchanged)

| Action | Allowed |
|--------|---------|
| Ship LRE substrate + fleet claim matrix on `feat/lre-fleet-unlocks` | Yes |
| Run `lre-proof.sh` / `fleet-claims-audit.sh` in CI | Yes |
| Update ONE_PAGER / Remote Boundary copy from matrix | Yes |
| Spawn canvas fleet dashboard workers | **No** |
| Claim queue time / placement without new parser | **No** |
| Claim hermetic Nix `--config=lre` without flake + MODULE.bazel | **No** |

A future `fleet-evidence-v1` implement DAG requires parser + SQLite proof block + projection + canvas Remote Boundary lens change per `docs/dags/future-fleet-claims.md`.

---

## Wave-1 frontier (not in this ship gate)

| Coordinator | Sub-DAG | Goal |
|-------------|---------|------|
| `coord-lre-nix-phase3` | `lre-proof` wave-3 | Nix LRE toolchain research → implement or honest blocker |
| `coord-ladder-docs-sync` | ladder-sync | Fix stale `future-execution-ladder.md` + `docs/dags/README.md` |

These may land follow-up PRs; they do not block the dual-close ship packet.

---

## Handoff index

- Ship packet: [`../wave-0/ship-packet.md`](../wave-0/ship-packet.md) (wave-1 ship-ready)
- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Broker ARM: [`broker-arm.md`](broker-arm.md)
- KOS routing: [`../KOS-startup-routing.md`](../KOS-startup-routing.md)
- LRE worker results: [`../../lre-proof/wave-2/worker-results.json`](../../lre-proof/wave-2/worker-results.json)
- Fleet worker results: [`../../future-fleet-claims/wave-1/worker-results.json`](../../future-fleet-claims/wave-1/worker-results.json)
