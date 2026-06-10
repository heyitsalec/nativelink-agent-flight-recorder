# NLFR KOS cutover — wave 1 broker ARM (`tier1-canvas-polish`)

**Date:** 2026-06-06  
**Branch:** `feat/docs-wiki-wave2` → spawn `feat/nlfr-kos-cutover` after merge  
**Worker:** `wave1-arm-handoffs`  
**Status:** ARMED

## Operator intent

ARM **wave 1** of the NLFR flagship KOS cutover: human-design pass on the tier1 canvas
(compare lens, run-group selector, Proof Drawer / Remote Boundary density, screenshot baselines).
Authority is **local KOS primary** (`kos serve`, `dag:nlfr-flagship`, `linear_authority: false`).

## Prerequisite (wave-0)

| Artifact | Status |
|----------|--------|
| [`docs/dags/nlfr-kos-roadmap.md`](../../../dags/nlfr-kos-roadmap.md) | PLANNED |
| [`wave-0/four-wave-plan.md`](../wave-0/four-wave-plan.md) | PLANNED |
| `feat/docs-wiki-wave2` merge | pending — Diátaxis wiki, broker diagram, proof-samples hub |

Confirm `kos serve http://127.0.0.1:7423` healthy and `dag:nlfr-flagship` in `/v1/dags` before
coordinator spawn (see [`KOS-startup-routing.md`](KOS-startup-routing.md)).

## Parent actions (ARM only)

- Created DAG mirror: [`docs/dags/tier1-canvas-polish.md`](../../../dags/tier1-canvas-polish.md)
- Created KOS routing: [`KOS-startup-routing.md`](KOS-startup-routing.md)
- Initialized spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Re-armed broker mode — **no implementer spawn in this ARM worker**

## Wave-1 dispatch (next)

Parent spawns coordinators on `feat/nlfr-kos-cutover` with disjoint `write_scope`:

| # | coordinator_id | Sub-DAG | Notes |
|---|----------------|---------|-------|
| 1 | `coord-canvas-ux-polish` | Compare + worker + lens styling | Must not touch `RunSelector*` |
| 2 | `coord-run-group-selector` | Run-group selector UX | Owns `RunSelector*` tree only |
| 3 | `coord-canvas-readme` | Canvas operator docs | Parallel with 1–2 |
| 4 | `coord-canvas-screenshots` | Baseline capture + truth tests | **After** UX + selector land |

KOS nodes: `W1-CANVAS-UX` · `W1-RUN-SELECTOR` · `W1-SCREENSHOTS` · `W1-INTEGRATE`

Seed script (operator-owned, Knowledge OS repo):

```bash
# tools/orchestrator/scripts/seed_nlfr_flagship_wave1.py
```

## Proof gates (parent at wave close)

```bash
npm --prefix apps/canvas run test:truth
npm --prefix apps/canvas run build
./scripts/record-canvas-build.sh
uv run pytest -q   # if canvas test helpers touched
```

GHA offline: local gates substitute per
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).

## Ceiling / stop conditions

| Claim | Label | Gate |
|-------|-------|------|
| Run selector shows indexed run groups | `derived_v1` / `medium` | Fixture or CLI-exported compare index only |
| Compare lens visual polish | `simulated_v1` → layout | No unsupported compare dimensions |
| Live backend / fleet state in UI | **blocked** | Stop if selector invents SQLite rows not in projection |

**Stop wave** if run-selector requires new backend API beyond projection JSON export.

## Inherited design brief

Human-design items 1–4 from
[`human-design-handoff.md`](../../m5-m9-umbrella/wave-4/human-design-handoff.md):
compare lens polish, run selector UX, Proof Drawer / Remote Boundary density, screenshot baselines.
