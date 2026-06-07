# Unlock wave — ship packet

**Date:** 2026-06-06  
**Branch:** `feat/lre-fleet-unlocks`  
**Git HEAD:** `e00d057bf41cf480a608ebfcff2dd1d658c410d4`  
**Broker:** parent Composer (KOS-armed)  
**Status:** wave-1 ship-ready

---

## DAGs closed

| DAG | Wave | Ceiling | Handoffs |
|-----|------|---------|----------|
| `lre-proof` | wave-2 | `lre_substrate_ready` (`collectable_v1`, `medium`) | [`lre-proof/wave-2/`](../../lre-proof/wave-2/) |
| `future-fleet-claims` | wave-1 | research-only `derived_v1` | [`future-fleet-claims/wave-1/`](../../future-fleet-claims/wave-1/) |

**Integration close:** [`unlock-wave/wave-1/integration-brief.md`](../wave-1/integration-brief.md)

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
```

Nix (when available):

```bash
nix develop --command ./scripts/lre-proof.sh
# → data/lre-proof/summary.json with status: lre_substrate_ready
```

---

## Honesty boundaries

### LRE

- **Supported:** Substrate config (`lre.json5`), dedicated ports, remote_executor smoke, endpoint probes
- **Not supported:** Hermetic Nix `--config=lre`, `lre.bazelrc` via flake + MODULE.bazel

### Fleet

- **Supported:** Claim matrix audit, ONE_PAGER footnote, `worker_endpoints_ready` / conditional `worker_identity`
- **Not supported:** Scheduler assignment, queue time, action placement, load distribution, fleet canvas UI

---

## PR ship checklist

- [x] LRE proof script + tests + CI probe landed
- [x] Fleet claims audit script + tests + ONE_PAGER footnote landed
- [x] Dual integration brief consolidated (`unlock-wave/wave-1/integration-brief.md`)
- [x] Parent pytest green (92 passed, 1 skipped)
- [ ] Parent opens PR on `feat/lre-fleet-unlocks` (broker action)
- [ ] CI `lre-proof-probe` green on PR (when Nix toolchain available)

---

## Wave-1 frontier (follow-up PRs, not blocking ship)

| Coordinator | Goal |
|-------------|------|
| `coord-lre-nix-phase3` | Nix LRE toolchain research → implement or honest blocker |
| `coord-ladder-docs-sync` | `future-execution-ladder.md` + `docs/dags/README.md` truth sync |

---

## Broker rules (unchanged)

- Do not spawn fleet/scheduler canvas workers from this ship gate
- Do not claim queue time / placement without new collectable parser
- Fleet implement DAG (`fleet-evidence-v1`) requires SQLite proof block + projection change
