# Wave 3 Integration Brief — lre-linux-manual-proof

**Date:** 2026-06-06  
**Worker:** `waves-1-4-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 2 `W2-INTEGRATE` done

---

## Wave-3 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-lre-linux-runbook` | `lre-linux-runbook` | `W3-LINUX-RUNBOOK` | SHIPPED | `docs/LRE_LINUX_PROOF.md` — x86_64-linux Nix operator runbook; Darwin blocker honesty |
| `coord-lre-sample-promote` | `lre-sample-promote` | `W3-SAMPLE-PROMOTE` | SHIPPED | `lre-cold-warm-proof-linux-manual-sample.json` — honest blocker on Darwin host |
| `coord-lre-ladder-sync` | `lre-ladder-sync` | `W3-LADDER-SYNC` | SHIPPED | `docs/dags/lre-proof.md`, `docs/dags/future-execution-ladder.md`, `docs/DEV_ENVIRONMENT.md` LRE section |
| `w3-integrate` | `waves-1-4-integrate-close` | `W3-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Operator runbook | `docs/LRE_LINUX_PROOF.md` |
| Proof sample | `docs/proof-samples/lre-cold-warm-proof-linux-manual-sample.json` |
| Ladder sync | `docs/dags/lre-proof.md`, `docs/dags/future-execution-ladder.md`, `docs/DEV_ENVIRONMENT.md` |
| Hub | `docs/proof-samples/README.md` |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W3-1 | Integrate host is **aarch64-darwin** — no x86_64-linux green `summary.json`; blocker sample is honest outcome | P1 |
| C-W3-2 | `lre_cache_parity_observed` not observed on this host | P1 |
| C-W3-3 | GHA offline — CI LRE legs deferred to wave 4 | inherited |

---

## Proof (local — GHA offline)

```bash
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
# Operator-owned optional green on x86_64-linux:
# nix develop --command ./scripts/lre-cold-warm-proof.sh
```

---

## Honesty / claim boundary

**Supported now:**

- LRE substrate + Nix toolchain scripts (`lre-proof.sh`, `lre-nix-toolchain-proof.sh`)
- Darwin environment-blocker as `collectable_v1` / `high`
- Manual Linux runbook for operator promotion path

**Unsupported until x86_64-linux green run:**

- `lre_cache_parity_observed` cold/warm metrics from this host

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
