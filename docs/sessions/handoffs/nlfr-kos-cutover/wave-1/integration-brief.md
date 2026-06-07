# Wave 1 Integration Brief — tier1-canvas-polish

**Date:** 2026-06-06  
**Worker:** `waves-1-4-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**DAG:** [`tier1-canvas-polish.md`](../../../../dags/tier1-canvas-polish.md) · KOS `dag:nlfr-flagship`

---

## Wave-1 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-canvas-ux-polish` | `canvas-ux-polish` | `W1-CANVAS-UX` | SHIPPED | Compare lens, worker nodes, Proof Drawer density — `ChartPanel`, `OperatorPanel`, `TablePanel`, `styles.css` |
| `coord-run-group-selector` | `run-group-selector` | `W1-RUN-SELECTOR` | SHIPPED | `RunGroupSelector.tsx` + `compare-index.json` fixture; reads projection JSON only (`derived_v1`) |
| `coord-canvas-readme` | `canvas-readme` | — | SHIPPED | `apps/canvas/README.md` — tier1 demo, run-group selector operator path |
| `coord-canvas-screenshots` | `canvas-screenshots` | `W1-SCREENSHOTS` | SHIPPED (partial) | Hero GIF refresh (`docs/media/nlfr-canvas-tour.gif`); `test:truth` green; full `record-canvas-build.sh` baseline not re-run at integrate close |
| `w1-integrate` | `waves-1-4-integrate-close` | `W1-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Canvas UX | `apps/canvas/src/panels/ChartPanel.tsx`, `OperatorPanel.tsx`, `TablePanel.tsx`, `styles.css` |
| Run selector | `apps/canvas/src/panels/RunGroupSelector.tsx`, `ComposerDrawer.tsx`, `apps/canvas/public/projections/compare-index.json` |
| Operator docs | `apps/canvas/README.md` |
| Media | `docs/media/nlfr-canvas-tour.gif` (refreshed) |
| DAG | `docs/dags/tier1-canvas-polish.md` → **SHIPPED** |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W1-1 | `record-canvas-build.sh` not re-run at integrate close — committed projections may lag selector fixture | P2 |
| C-W1-2 | GHA offline — canvas truth verified locally only | inherited |

---

## Proof (local — GHA offline)

```bash
npm --prefix apps/canvas run test:truth   # PASS at integrate close
npm --prefix apps/canvas run build
uv run pytest -q
```

---

## KOS close

All `W1-*` nodes marked **done** on `dag:nlfr-flagship` via ControlPlaneClient.
Provenance: this brief.

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Wave-0 plan: [`../wave-0/four-wave-plan.md`](../wave-0/four-wave-plan.md)
