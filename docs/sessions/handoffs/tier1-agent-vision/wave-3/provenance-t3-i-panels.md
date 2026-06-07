# T3-I Panels — Provenance

**Worker:** `t3-i-panels`  
**Coordinator:** `coord-t3-implement`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Extracted the `App.tsx` monolith into view-spec panel modules wired through `ViewProvider` + `GridShell` + `useViewRoute`. All 15 v1 `component_kind` implementations live in `panels/ChartPanel.tsx`, `panels/TablePanel.tsx`, and `panels/OperatorPanel.tsx`. `App.tsx` is a ~32 LOC shell. Projection loads remain single-path via `bindings/resolver.ts` (no per-panel fetch). Truth-guard selectors preserved.

---

## Inputs read

| Artifact | Path |
|----------|------|
| KOS startup routing | `docs/sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md` |
| Shell provenance | `docs/sessions/handoffs/tier1-agent-vision/wave-3/provenance-t3-i-shell.md` |
| Views provenance | `docs/sessions/handoffs/tier1-agent-vision/wave-3/provenance-t3-i-views.md` |
| ViewContext / GridShell / resolver | `apps/canvas/src/view/*`, `layout/GridShell.tsx`, `bindings/resolver.ts` |
| Page model helpers | `apps/canvas/src/pageModel.ts` |
| Default view spec | `apps/canvas/public/views/nlfr-default-v0.json` |
| Monolith source | `apps/canvas/src/App.tsx` (pre-refactor) |

---

## Deliverables written

| File | Role |
|------|------|
| `apps/canvas/src/panels/ChartPanel.tsx` | Graph/header kinds: notice, topbar, mode rail, zoom, graph canvas, legend, proof constellation, validation runway |
| `apps/canvas/src/panels/TablePanel.tsx` | Rail kinds: inspector, proof drawer/block, remote lens, compare lens/dimension |
| `apps/canvas/src/panels/OperatorPanel.tsx` | Operator command bar + keyword router |
| `apps/canvas/src/panels/index.ts` | `renderPanel()` registry over all 15 kinds |
| `apps/canvas/src/panels/shared/IconButton.tsx` | Shared mode/zoom button |
| `apps/canvas/src/panels/shared/props.ts` | View-spec prop parsing (comma lists, booleans) |
| `apps/canvas/src/panels/shared/ZoomContext.tsx` | D3 zoom bridge for graph + zoom_controls + operator reset |
| `apps/canvas/src/App.tsx` | Thin shell: `ViewProvider` → `ZoomProvider` → `GridShell` + `renderPanel` |
| `apps/canvas/src/styles.css` | Grid-shell region layout overrides (panel grid only) |
| This file | Worker provenance |

---

## Design decisions

### Panel grouping

| Module | `component_kind` values |
|--------|-------------------------|
| `ChartPanel.tsx` | `projection_notice`, `topbar_summary`, `mode_rail`, `zoom_controls`, `action_graph_canvas`, `truth_legend`, `proof_constellation`, `validation_runway` |
| `TablePanel.tsx` | `evidence_inspector`, `proof_drawer`, `proof_block_card`, `remote_boundary_lens`, `compare_lens`, `compare_dimension_card` |
| `OperatorPanel.tsx` | `operator_command_bar` |

### Single fetch path

Panels consume `useViewContext()` / `useViewComponent()` only. No `fetch('/projections/...')` in panel code.

### Truth-guard selectors preserved

Selectors are emitted once per instance on `GridShell` `grid-slot` wrappers (`instance.data_testid`); panel inner DOM avoids duplicate `data-testid` values that break Playwright strict mode.

| Selector | Location |
|----------|----------|
| `data-testid="nlfr-canvas-app"` | `GridShell` root |
| `projection-notice` | `grid-slot` wrapper for notice instance |
| `canvas-mode-rail` | `grid-slot` wrapper for modes instance |
| `action-graph-svg` | `grid-slot` wrapper for graph-main |
| `validation-runway` | `grid-slot` wrapper for runway-overlay |
| `proof-drawer` | `grid-slot` wrapper for proof-drawer |
| `remote-execution-lens` | `grid-slot` wrapper for remote-lens |
| `compare-lens` | `grid-slot` wrapper for compare-lens |
| `evidence-inspector` | `grid-slot` wrapper for inspector instance |
| `truth-legend` | `grid-slot` wrapper for legend instance |
| `operator-chat` | `grid-slot` wrapper for operator instance |
| `data-graph-node-id` | `GraphNode` in chart panel |
| `aria-label` on mode buttons | `IconButton` via mode spec labels (e.g. Compare Runs) |

### Zoom coordination

`ZoomProvider` registers D3 zoom API from `action_graph_canvas`; `zoom_controls` and operator reset call into the same controller. `ViewProvider.onZoomReset` wired for run-group changes.

---

## no_touch honored

- `apps/canvas/src/view/**`
- `apps/canvas/src/layout/**`
- `apps/canvas/src/routing/**`
- `apps/canvas/src/bindings/**`
- `apps/canvas/public/views/**`
- `apps/canvas/scripts/truth-guard.mjs`

---

## Proof

```bash
npm --prefix apps/canvas run build
# exit 0 — tsc -b && vite build

npm --prefix apps/canvas run test:truth
# ok: true — 40/40 graph nodes, compare lens visible
```

---

## Return

```json
{
  "worker_id": "t3-i-panels",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/tier1-agent-vision/wave-3/",
  "artifacts": {
    "provenance": "provenance-t3-i-panels.md",
    "panels": [
      "apps/canvas/src/panels/ChartPanel.tsx",
      "apps/canvas/src/panels/TablePanel.tsx",
      "apps/canvas/src/panels/OperatorPanel.tsx",
      "apps/canvas/src/panels/index.ts"
    ],
    "app": "apps/canvas/src/App.tsx"
  },
  "claims_touched": [],
  "blockers": []
}
```
