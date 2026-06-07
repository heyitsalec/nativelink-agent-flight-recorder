# NLFR Component Catalog — `nlfr.view-spec.v1`

**Schema:** [`view-spec.v1.schema.json`](./view-spec.v1.schema.json)  
**Routing:** [`routing.md`](./routing.md)  
**Status:** normative design (T3-D wave 2)  
**Date:** 2026-06-06

This catalog enumerates the **15 v1 `component_kind` values** for `nlfr.view-spec.v1`. Each kind maps 1:1 to an implementation extracted from `apps/canvas/src/App.tsx` during T3-I*. Components render **projection-bound data only**; they never invent nodes, edges, or audit events.

---

## Grid shell placement

```
┌────────────────────────────────────────────────────────────┐
│ projection_notice                                           │
├────────────────────────────────────────────────────────────┤
│ topbar_summary │ mode_rail [+ zoom_controls]                │
├──────────────────────────────┬─────────────────────────────┤
│ action_graph_canvas          │ rail (mode-dependent)       │
│ + truth_legend               │ inspector / lens overlays   │
├──────────────────────────────┴─────────────────────────────┤
│ operator_command_bar                                        │
└────────────────────────────────────────────────────────────┘
```

| Region | `grid_area` | Typical kinds |
|--------|-------------|---------------|
| `notice` | banner | `projection_notice` |
| `header` | topbar | `topbar_summary`, `mode_rail`, `zoom_controls` |
| `primary` | canvas | `action_graph_canvas`, `truth_legend`, `proof_constellation` |
| `rail` | inspector (440px desktop) | `evidence_inspector`, `validation_runway`, `proof_drawer`, `remote_boundary_lens`, `compare_lens` |
| `operator` | command bar | `operator_command_bar` |

Rail collapses to bottom sheet when viewport width &lt; 720px (`layout.responsive.breakpoint_px`).

---

## Shell root (not a `component_kind`)

The canvas application root is **not** a catalog entry but carries a stable Playwright selector:

| Element | React source | `data-testid` |
|---------|--------------|---------------|
| App shell | `<main className="app-shell">` in `App` | `nlfr-canvas-app` |

---

## v1 component catalog (15 kinds)

| # | `component_kind` | React source (`App.tsx`) | Region | `projection_binding` | `data-testid` |
|---|------------------|--------------------------|--------|----------------------|---------------|
| 1 | `projection_notice` | `projectionNotice` memo → conditional `<p>` | `notice` | `binding.action_graph` (+ resolver `usingFixtureFallback` flag) | `projection-notice` |
| 2 | `topbar_summary` | header `.run-strip` | `header` | `binding.action_graph` → `$.summary` | *(none today; T3-I: `topbar-summary`)* |
| 3 | `mode_rail` | `.mode-rail` + mode `IconButton`s | `header` | none (UI chrome) | `canvas-mode-rail` |
| 4 | `zoom_controls` | zoom `IconButton`s in mode rail | `header` | none (D3 zoom API) | *(none today; T3-I: `zoom-controls`)* |
| 5 | `action_graph_canvas` | `<svg className="graph-canvas">` + `GraphNode` | `primary` | `binding.action_graph` | `action-graph-svg` |
| 6 | `truth_legend` | `TruthLegend` | `primary` | none (static source-kind key) | `truth-legend` |
| 7 | `proof_constellation` | `ProofConstellation` (SVG `foreignObject`) | `primary` | `binding.proof_packet` | *(none today; T3-I: `proof-constellation`)* |
| 8 | `evidence_inspector` | `Inspector` | `rail` | selector on graph: `$.nodes[?(@.id=='{selected}')]` | `evidence-inspector` |
| 9 | `validation_runway` | `RunwayOverlay` | `rail` | `binding.action_graph` (sorted nodes) or optional `binding.runway` | `validation-runway` |
| 10 | `proof_drawer` | `ProofDrawer` + `ProofBlockView` children | `rail` | `binding.proof_packet` | `proof-drawer` |
| 11 | `proof_block_card` | `ProofBlockView` | `rail` *(child)* | slice: `$.blocks[?(@.id=='{block_id}')]` | *(none today; T3-I: `proof-block-{id}`)* |
| 12 | `remote_boundary_lens` | `RemoteLens` | `rail` | `join_v1` → `remote_lens_model` | `remote-execution-lens` |
| 13 | `compare_lens` | `CompareLens` + `CompareDimensionView` children | `rail` | `binding.compare` (`required: false`) | `compare-lens` |
| 14 | `compare_dimension_card` | `CompareDimensionView` | `rail` *(child)* | slice: `$.dimensions[?(@.id=='{dimension_id}')]` | *(none today; T3-I: `compare-dimension-{id}`)* |
| 15 | `operator_command_bar` | `.operator` section | `operator` | none (local draft only) | `operator-chat` |

### Graph nodes (not `component_kind`)

Action graph nodes are rendered inside `action_graph_canvas`. They use **`data-graph-node-id`** (not `data-testid`) for parity checks in `truth-guard.mjs`:

```html
<g data-graph-node-id="run:abc123" … />
```

Truth-guard builds expected ids from `public/projections/action-graph.json` and asserts rendered parity.

---

## Per-kind reference

### 1. `projection_notice`

| Field | Value |
|-------|-------|
| **Purpose** | Banner when fixture fallback is active or projection mix is simulated/collectable/mixed |
| **Binding** | `binding.action_graph` — reads `run_group`, node `source_kind` distribution, resolver fallback state |
| **Props** | `{ "tones": ["fallback","collectable","simulated","mixed"] }` — optional allow-list |
| **Visible when** | Always when notice text is non-null; hidden when `projectionNotice` resolves to null |
| **Truth** | Display strings are `derived_v1`; must not claim live NativeLink proof when `simulated_v1` dominates |

### 2. `topbar_summary`

| Field | Value |
|-------|-------|
| **Purpose** | Run strip: run count, node count, cache events, failures, remote mode label |
| **Binding** | `binding.action_graph` — fields `summary.*`, plus derived `remoteLens.modeLabel` from join in T3-I |
| **Props** | `{ "show_remote_label": true }` |
| **Visible when** | `{ "mode": ["graph","runway","proof","remote","compare"] }` (all modes) |

### 3. `mode_rail`

| Field | Value |
|-------|-------|
| **Purpose** | Five canvas modes + visual active state |
| **Binding** | none |
| **Props** | `{ "modes": ["graph","runway","proof","remote","compare"] }` — must match `modes[]` in view spec |
| **Visible when** | Always |
| **T3-I testids** | Per-mode buttons: `data-testid="mode-{mode_id}"` (e.g. `mode-compare`) |

### 4. `zoom_controls`

| Field | Value |
|-------|-------|
| **Purpose** | D3 zoom in / out / reset |
| **Binding** | none — controls `action_graph_canvas` zoom behavior via shared context |
| **Props** | `{ "target_instance_id": "graph-main", "scale_extent": [0.55, 2.35] }` |
| **Visible when** | `{ "mode": ["graph","runway","proof"] }` or when `props.always_visible: true` |

### 5. `action_graph_canvas`

| Field | Value |
|-------|-------|
| **Purpose** | SVG graph: edges, nodes, optional in-canvas proof constellation sibling |
| **Binding** | `binding.action_graph` — full projection; layout via `layoutProjection()` |
| **Props** | `{ "show_truth_legend": false, "zoom_controls": true, "highlight_focus": "{focus}" }` |
| **Visible when** | `{ "mode": ["graph","runway","proof","remote","compare"] }` — graph stays mounted under lenses |

### 6. `truth_legend`

| Field | Value |
|-------|-------|
| **Purpose** | Static key for `collectable_v1`, `derived_v1`, `simulated_v1`, `future` |
| **Binding** | none |
| **Props** | `{ "items": ["collectable_v1","derived_v1","simulated_v1","future"] }` |
| **Visible when** | When parent `action_graph_canvas.props.show_truth_legend` is true, or as standalone instance |

List items expose `data-source-kind` on each `<li>` (existing DOM contract).

### 7. `proof_constellation`

| Field | Value |
|-------|-------|
| **Purpose** | In-graph mini proof summary (block counts by source kind) |
| **Binding** | `binding.proof_packet` |
| **Props** | `{ "scope_block_id": "scope" }` |
| **Visible when** | `{ "mode": ["proof"] }` |

### 8. `evidence_inspector`

| Field | Value |
|-------|-------|
| **Purpose** | Selected node dossier: truth grid, evidence refs, payload |
| **Binding** | Graph selector with `{selected}` placeholder from view state |
| **Props** | `{ "close_on_mode_change": true }` |
| **Visible when** | `{ "mode": ["graph","runway"], "has_selection": true }` |

### 9. `validation_runway`

| Field | Value |
|-------|-------|
| **Purpose** | Timeline of validation events sorted by `laneIndex(kind)` |
| **Binding** | Prefer `binding.action_graph` nodes; optional `binding.runway` when promoted (T3-I2) |
| **Props** | `{ "lane_order": ["run","invocation","target","action","remote_execution_config","worker_readiness","cache_event","failure","artifact"] }` |
| **Visible when** | `{ "mode": ["runway"] }` |

### 10. `proof_drawer`

| Field | Value |
|-------|-------|
| **Purpose** | Full proof packet: summary metrics + block list |
| **Binding** | `binding.proof_packet` |
| **Props** | `{ "render_blocks_as": "proof_block_card" }` |
| **Visible when** | `{ "mode": ["proof"] }` |

### 11. `proof_block_card`

| Field | Value |
|-------|-------|
| **Purpose** | Reusable proof block card (metrics, claims, unsupported claims, evidence refs) |
| **Binding** | Block selector on proof packet |
| **Props** | `{ "block_id": "scope" }` — required when used as standalone instance |
| **Visible when** | Parent `proof_drawer` or explicit instance in custom layouts |

### 12. `remote_boundary_lens`

| Field | Value |
|-------|-------|
| **Purpose** | Remote execution boundary + worker readiness; gated unsupported claims |
| **Binding** | `join_v1` with `join_fn: "remote_lens_model"`, sources `binding.action_graph` + `binding.proof_packet` |
| **Props** | `{ "remote_block_id": "remote_execution", "worker_block_title": "Worker Readiness Boundary" }` |
| **Visible when** | `{ "mode": ["remote"] }` |

### 13. `compare_lens`

| Field | Value |
|-------|-------|
| **Purpose** | Multi-run compare panel or honest empty state |
| **Binding** | `binding.compare` with `required: false` |
| **Props** | `{ "empty_state_path_hint": "/projections/compare-projection.json" }` |
| **Visible when** | `{ "mode": ["compare"] }` |

When binding resolves to null, show empty state — **never synthesize** compare dimensions.

### 14. `compare_dimension_card`

| Field | Value |
|-------|-------|
| **Purpose** | Per-dimension truth grid, delta metrics, claims, evidence refs |
| **Binding** | Dimension selector on compare projection |
| **Props** | `{ "dimension_id": "agent_provenance" }` |
| **Visible when** | Parent `compare_lens` when dimension exists |

### 15. `operator_command_bar`

| Field | Value |
|-------|-------|
| **Purpose** | Local keyword router (`cache`, `fail`, `proof`, `agent`, `compare`, `runway`, reset) |
| **Binding** | none — `source_kind: derived_v1` local-only chrome |
| **Props** | `{ "placeholder": "focus cache misses", "commands": ["cache","fail","proof","remote","agent","compare","runway","reset"] }` |
| **Visible when** | Always (default tier1 layout) |

Operator input is **never persisted** as evidence or exported in proof packets.

---

## Props schema conventions

All `props` objects in view specs are JSON objects. Common patterns:

| Prop type | Examples | Notes |
|-----------|----------|-------|
| Boolean flags | `show_truth_legend`, `zoom_controls`, `show_remote_label`, `close_on_mode_change` | Default per kind table above |
| Binding key ref | `target_instance_id` | References another `instance_id` in same spec |
| Selector placeholders | `{selected}`, `{block_id}`, `{dimension_id}` | Resolved by binding resolver at runtime |
| String arrays | `modes`, `tones`, `lane_order`, `commands` | Must match schema enums where applicable |
| Numeric tuples | `scale_extent: [0.55, 2.35]` | D3 zoom limits |

Props must **not** contain secrets, environment variables, raw prompts, or credentials. Agent views may only reference `model` and `prompt_sha256` prefix per M8 contract.

---

## Truth-guard selector contract

Selectors preserved from current canvas (`apps/canvas/scripts/truth-guard.mjs`, capture scripts):

| `data-testid` | Asserted today | Component kind |
|---------------|----------------|----------------|
| `nlfr-canvas-app` | capture scripts | shell root |
| `projection-notice` | design target (T3-I) | `projection_notice` |
| `canvas-mode-rail` | — | `mode_rail` |
| `action-graph-svg` | yes (wait + node parity) | `action_graph_canvas` |
| `validation-runway` | capture-demo-tour | `validation_runway` |
| `proof-drawer` | capture-demo-tour | `proof_drawer` |
| `remote-execution-lens` | — | `remote_boundary_lens` |
| `compare-lens` | yes (when compare present) | `compare_lens` |
| `evidence-inspector` | — | `evidence_inspector` |
| `truth-legend` | — | `truth_legend` |
| `operator-chat` | capture-demo-tour | `operator_command_bar` |

**Graph parity:** `[data-graph-node-id]` on each rendered node vs `action-graph.json` node ids.

---

## Future kinds (wave 4+ — not in v1 enum)

| `component_kind` | Notes |
|------------------|-------|
| `run_group_selector` | Requires `run_group_index` projection binding |
| `agent_provenance_card` | Binds proof block `kind: agent_provenance` |
| `audit_ledger_timeline` | Harmony port; needs event projection |
| `worker_lane_board` | Requires role-labeled runs in projection |

Do not reference these kinds in v1 view specs; schema enum is closed at 15.

---

## Anti-patterns

1. **Per-component fetch** — No `useEffect` fetch inside individual components. All projection loads go through the binding resolver once per view mount (eliminates triple fetch in current `App.tsx`).

2. **View spec as data source** — The view spec describes layout and bindings only. Nodes, edges, proof blocks, and compare dimensions must come from projection JSON.

3. **Silent join inference** — Cross-projection joins require explicit `join_v1` with a registered `join_fn` in `pageModel.ts`. No ad hoc correlation of workers, queues, or agents.

4. **Persisting operator commands** — Command bar state is ephemeral local draft; it must not appear in exports or proof claims.

5. **Synthesizing missing compare/runway data** — Optional bindings show empty states (compare lens pattern), not fabricated dimensions or timeline events.

6. **Secrets in props** — Reject specs that embed API keys, env vars, or raw prompt text in any `props` field.

---

## Source map

| Artifact | Path |
|----------|------|
| Monolith (extraction source) | `apps/canvas/src/App.tsx` |
| Types | `apps/canvas/src/types.ts` |
| Layout | `apps/canvas/src/layout.ts` |
| Truth guard | `apps/canvas/scripts/truth-guard.mjs` |
| View systems handoff | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-view-systems.md` |
| Canvas audit | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-canvas-audit.md` |
