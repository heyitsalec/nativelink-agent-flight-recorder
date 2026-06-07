# Wave 7 Integration Brief — cache-only-ci-gate

**Date:** 2026-06-06  
**Worker:** `waves-5-8-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 6 `W6-INTEGRATE` done

---

## Wave-7 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-cache-gate-script` | `cache-gate-script` | `W7-CACHE-GATE-SCRIPT` | SHIPPED | `scripts/cache-only-ci-gate.sh` — doctor JSON contract + pytest smoke |
| `coord-cache-gate-workflow` | `cache-gate-workflow` | `W7-CACHE-GATE-WF` | SHIPPED (docs-only) | `.github/workflows/nlfr-cache-only-gate.yml` — **GHA still offline** |
| `coord-cache-gate-docs` | `cache-gate-docs` | `W7-CACHE-GATE-DOCS` | SHIPPED | `docs/CI_RECIPE.md`, `docs/ADOPTION_GUIDE.md`, `docs/GHA_RESTORE_RUNBOOK.md` gate section |
| `w7-integrate` | `waves-5-8-integrate-close` | `W7-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Gate script | `scripts/cache-only-ci-gate.sh` |
| Workflow | `.github/workflows/nlfr-cache-only-gate.yml` |
| Docs | `docs/CI_RECIPE.md`, `docs/ADOPTION_GUIDE.md`, `docs/GHA_RESTORE_RUNBOOK.md` |
| Tests | `tests/test_doctor_cache_only_gate.py` |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W7-1 | **GHA offline** — `nlfr-cache-only-gate.yml` not exercised in Actions | P1 |
| C-W7-2 | Full `nlfr-proof.yml` green still deferred to wave 4 residual | inherited |

Local gate is PR-safe substitute per gha-offline-proof-shift policy.

---

## Proof (local — GHA offline)

```bash
./scripts/cache-only-ci-gate.sh
uv run pytest tests/test_doctor_cache_only_gate.py -q
bash -n scripts/cache-only-ci-gate.sh
# When GHA returns:
# gh workflow run nlfr-cache-only-gate.yml
```

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Four-wave plan: [`../wave-5/four-wave-plan-5-8.md`](../wave-5/four-wave-plan-5-8.md)
