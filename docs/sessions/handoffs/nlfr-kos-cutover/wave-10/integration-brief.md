# Wave 10 Integration Brief — gha-sustained-green

**Date:** 2026-06-07  
**Worker:** `gha-sustained-green` (W10)  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 9 `W9-INTEGRATE` — closed 2026-06-06

---

## Wave-10 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-gha-readiness` | `gha-sustained-green` | `W10-GHA-RESTORE` | SHIPPED (local only) | `verify-gha-readiness.sh` — YAML audit + substitute gates |
| `coord-gha-readiness` | `gha-sustained-green` | `W10-CI-PROMOTE` | BLOCKED | GHA offline — promotion deferred to first sustained green |
| `coord-gha-ci-docs` | `gha-sustained-green` | `W10-CI-DOCS` | SHIPPED | `GHA_RESTORE_RUNBOOK.md`, `CI_RECIPE.md` sustained-green + offline blocker |
| `w10-integrate` | `gha-sustained-green` | `W10-INTEGRATE` | DONE | This brief, worker-results, blocker sample |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Readiness script | `scripts/verify-gha-readiness.sh` |
| Runbook | `docs/GHA_RESTORE_RUNBOOK.md` — sustained-green criteria, offline blocker |
| CI recipe | `docs/CI_RECIPE.md` — sustained-green section |
| Blocker sample | `docs/proof-samples/ci-offline-blocker-sample.json` |
| Handoff | `docs/sessions/handoffs/nlfr-kos-cutover/wave-10/` |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W10-1 | **GHA offline** — no sustained green on `nlfr-proof.yml` (≥3 consecutive runs) | P0 |
| C-W10-2 | **CI promotion** — `proof-samples/` still author-Nix / fixture provenance | P1 |
| C-W10-3 | Inherited from W4/W7 — full seven-job Linux CI badge not observable | inherited |

Local readiness gate is the honest substitute per gha-offline-proof-shift policy.

---

## Proof (local — GHA offline)

```bash
chmod +x scripts/verify-gha-readiness.sh
./scripts/verify-gha-readiness.sh
# When GHA returns:
# gh workflow run nlfr-proof.yml
# gh workflow run nlfr-cache-only-gate.yml
```

---

## KOS close

Wave 10 local readiness gates substitute for sustained GHA green per gha-offline-proof-shift policy.
KOS nodes `W10-GHA-RESTORE`, `W10-CI-DOCS`, `W10-INTEGRATE` marked done; `W10-CI-PROMOTE` closed
with honest BLOCKED status. Proof gate: **140 passed, 3 skipped** (`uv run pytest -q`).

**Next broker action:** ARM wave 11 `adoption-init-path` per
[`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md).

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Roadmap: [`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md)
- Gap honesty (umbrella): [`../wave-9/gap-honesty-packet.md`](../wave-9/gap-honesty-packet.md)
