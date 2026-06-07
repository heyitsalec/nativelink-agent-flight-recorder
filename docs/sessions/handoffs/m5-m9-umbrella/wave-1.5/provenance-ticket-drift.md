# Provenance / ticket drift — M5–M9 umbrella (Wave 1.5)

**Audit date:** 2026-06-06  
**Scope:** PER-1065–PER-1069 as documented in repo DAG mirrors (Linear not queried)

## Matrix

| Milestone | Linear | Claimed | Actual | Gap |
|-----------|--------|---------|--------|-----|
| M5 | PER-1065 | Linux CI + adoption docs + proof samples | Workflow + docs exist; proof-samples from Nix not CI | medium |
| M6 | PER-1066 | Real default projection + banner | Delivered (`canvas-dev` collectable_v1) | low |
| M7 | PER-1067 | Worker stdout parser + one promoted claim | Not started | Wave 2 scope |
| M8 | PER-1068 | Real agent adapter | Not started | Wave 2 scope |
| M9 | PER-1069 | compare + retention + canvas lens | CLI shell only | Wave 3 scope |

## M5 gaps (non-blocking for Wave 2)

- `m5-ci-proof.md` handoff checklist unchecked
- Status docs still "planned/pending" (fixing in Wave 1.5 closeout)
- CI artifact promotion to `proof-samples/` waits on first green GHA run

## Wave 2 unblock

1. This file + sibling provenance artifacts
2. `integration-brief.md` with M7 claim pick + M8 adapter contract
3. `worker-results.json` aggregate
