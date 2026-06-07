# Wave 4 Integration Brief — ci-restore-verify

**Date:** 2026-06-06  
**Worker:** `waves-1-4-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 3 `W3-INTEGRATE` done

---

## Wave-4 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-gha-restore` | `gha-restore` | `W4-GHA-RESTORE` | SHIPPED (docs-only) | `docs/GHA_RESTORE_RUNBOOK.md` — seven-job restore procedure; **GHA still offline** |
| `coord-ci-proof-promote` | `ci-proof-promote` | `W4-PROOF-PROMOTE` | SHIPPED (docs-only) | `docs/proof-samples/CI_PROMOTION_MATRIX.md` — promotion matrix pending first green run |
| `coord-ci-docs-sync` | `ci-docs-sync` | `W4-CI-DOCS` | SHIPPED | `docs/CI_RECIPE.md`, `docs/GITHUB_RELEASE.md`, `docs/dags/README.md` gha-offline notes |
| `w4-integrate` | `waves-1-4-integrate-close` | `W4-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| GHA restore runbook | `docs/GHA_RESTORE_RUNBOOK.md` |
| CI promotion matrix | `docs/proof-samples/CI_PROMOTION_MATRIX.md` |
| CI docs sync | `docs/CI_RECIPE.md`, `docs/GITHUB_RELEASE.md`, `docs/dags/README.md` |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W4-1 | **GHA offline** — `nlfr-proof.yml` not exercised; no sustained green run | P0 |
| C-W4-2 | No CI artifacts promoted to `docs/proof-samples/` — matrix is documentation-only | P1 |
| C-W4-3 | Workflow repair not validated in Actions | P1 |

Wave 4 closes as **docs + runbook ship** per gha-offline-proof-shift policy. Re-open when operator declares GHA restored.

---

## Proof (local — GHA offline)

```bash
uv run pytest -q
bash -n scripts/*.sh
# When GHA returns:
# gh run list --workflow=nlfr-proof.yml --limit 5
# See docs/GHA_RESTORE_RUNBOOK.md
```

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Restore runbook: [`../../../../GHA_RESTORE_RUNBOOK.md`](../../../../GHA_RESTORE_RUNBOOK.md)
