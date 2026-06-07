# Wave 5 Integration Brief — live-proof-residual

**Date:** 2026-06-06  
**Worker:** `waves-5-8-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 4 `W4-INTEGRATE` done

---

## Wave-5 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-m8-live-residual` | `m8-live-residual` | `W5-M8-LIVE` | SHIPPED | `scripts/agent-live-proof.sh` — live path + honest Cursor CLI blocker refresh |
| `coord-lre-linux-residual` | `lre-linux-residual` | `W5-LRE-LINUX` | SHIPPED | `lre-cold-warm-proof-linux-manual-sample.json` blocker refresh; `tests/test_lre_proof.py` |
| `coord-live-proof-docs` | `live-proof-docs` | `W5-LIVE-DOCS` | SHIPPED | `adapters/cursor/README.md`, `docs/LRE_LINUX_PROOF.md`, `docs/proof-samples/README.md` M8/LRE sections |
| `w5-integrate` | `waves-5-8-integrate-close` | `W5-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| M8 live path | `scripts/agent-live-proof.sh`, `scripts/record-agent-change.sh` |
| LRE residual | `docs/proof-samples/lre-cold-warm-proof-linux-manual-sample.json` |
| Operator runbooks | `adapters/cursor/README.md`, `docs/LRE_LINUX_PROOF.md` |
| Tests | `tests/test_agent_live_proof.py`, `tests/test_lre_proof.py` |
| Hub | `docs/proof-samples/README.md` (M8/LRE milestone rows) |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W5-1 | **Cursor CLI unavailable** on integrate host — `chain_complete=true` from live session not observed | P1 |
| C-W5-2 | Integrate host is **aarch64-darwin** — no x86_64-linux LRE green; blocker sample is honest outcome | P1 |
| C-W5-3 | GHA offline — CI promotion deferred to wave 4 residual | inherited |

Wave 5 closes per policy: honest blockers are `collectable_v1` / `high`; waves 6–8 proceed.

---

## Proof (local — GHA offline)

```bash
./scripts/record-agent-change.sh --dry-run
./scripts/agent-live-proof.sh
./scripts/lre-cold-warm-proof.sh --help
uv run pytest tests/test_agent_live_proof.py tests/test_lre_proof.py -q
bash -n scripts/agent-live-proof.sh scripts/lre-cold-warm-proof.sh
```

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Four-wave plan: [`four-wave-plan-5-8.md`](four-wave-plan-5-8.md)
