# NLFR View Routing — Modes, Visibility, Responsive Shell

**Schema:** [`view-spec.v1.schema.json`](./view-spec.v1.schema.json)  
**Status:** normative design (T3-D wave 2)  
**Replaces:** implicit `CanvasMode` routing in `apps/canvas/src/App.tsx` (T3-I1 implements)

---

## Purpose

This document specifies how `nlfr.view-spec.v1` drives canvas mode lenses, component visibility, selection-reset policy, and responsive rail collapse. The canvas renders **only** what the view spec and bound projections provide — no synthesized nodes, edges, or audit events.

---

## Modes registry

Five v1 modes map 1:1 from current `CanvasMode` (`apps/canvas/src/types.ts`):

| `mode_id` | `label` | `icon` | `primary_component` | `rail_component` | `default_focus` | `requires_binding` | `data_testid` |
|-----------|---------|--------|---------------------|------------------|-----------------|-------------------|---------------|
| `graph` | Action Graph | `git-branch` | `graph-main` | `inspector-selected-node` | `all` | — | `canvas-mode-graph` |
| `runway` | Validation Runway | `route` | `graph-main` | `inspector-selected-node` | `all` | — | `canvas-mode-runway` |
| `proof` | Proof Packet | `file-check-2` | `graph-main` | `proof-drawer` | `all` | `binding.proof_packet` | `canvas-mode-proof` |
| `remote` | Remote Boundary | `network` | `graph-main` | `remote-lens` | `remote` | `binding.proof_packet` (join) | `canvas-mode-remote` |
| `compare` | Compare Runs | `git-compare` | `graph-main` | `compare-lens` | `derived` | `binding.compare` (optional) | `canvas-mode-compare` |

### Mode rail contract

- Container preserves **`data-testid="canvas-mode-rail"`** (truth-guard + Playwright continuity).
- Each mode button carries **`data-testid="canvas-mode-{mode_id}"`** per the table above.
- Zoom controls are a separate `zoom_controls` component instance in the `header` region (not mode buttons).
- Mode switching is local UI state; it does not mutate projections.

### Enter-mode side effects

| `mode_id` | On enter |
|-----------|----------|
| `graph` | `default_focus: all` |
| `runway` | `default_focus: all` |
| `proof` | `default_focus: all` |
| `remote` | `default_focus: remote` |
| `compare` | `default_focus: derived` |

These replace hardcoded `setFocus(...)` calls in `App.tsx` mode `onClick` handlers.

---

## Component visibility (`visible_when`)

Grid shell regions (see schema `layout.regions`):

```
┌────────────────────────────────────────────────────────────┐
│ notice: projection_notice                                   │
├────────────────────────────────────────────────────────────┤
│ header: topbar_summary │ mode_rail │ zoom_controls?        │
├──────────────────────────────┬─────────────────────────────┤
│ primary: action_graph_canvas │ rail: mode-dependent lens   │
│          truth_legend?       │                             │
├──────────────────────────────┴─────────────────────────────┤
│ operator: operator_command_bar                              │
└────────────────────────────────────────────────────────────┘
```

### Always-on chrome

| `instance_id` | `component_kind` | Region | `visible_when` |
|---------------|------------------|--------|----------------|
| `notice` | `projection_notice` | `notice` | *(none — always)* |
| `topbar` | `topbar_summary` | `header` | *(none — always)* |
| `modes` | `mode_rail` | `header` | *(none — always)* |
| `graph-main` | `action_graph_canvas` | `primary` | *(none — all modes)* |
| `operator` | `operator_command_bar` | `operator` | *(none — always)* |

### Conditional chrome

| `instance_id` | `component_kind` | Region | `visible_when` |
|---------------|------------------|--------|----------------|
| `zoom` | `zoom_controls` | `header` | `{ "prop_truthy": "zoom_controls" }` |
| `legend` | `truth_legend` | `primary` | `{ "prop_truthy": "show_truth_legend" }` |

Default props for `graph-main`: `{ "show_truth_legend": true, "zoom_controls": true }`. When `zoom_controls` is true, the zoom component may still be a separate instance; the prop gates optional header placement.

### Mode-specific overlays and rails

| `instance_id` | `component_kind` | Region | `visible_when` |
|---------------|------------------|--------|----------------|
| `runway-overlay` | `validation_runway` | `primary` | `{ "mode": ["runway"] }` |
| `proof-constellation` | `proof_constellation` | `primary` | `{ "mode": ["proof"] }` |
| `proof-drawer` | `proof_drawer` | `rail` | `{ "mode": ["proof"] }` |
| `remote-lens` | `remote_boundary_lens` | `rail` | `{ "mode": ["remote"] }` |
| `compare-lens` | `compare_lens` | `rail` | `{ "mode": ["compare"], "binding_missing_ok": "binding.compare" }` |
| `inspector-selected-node` | `evidence_inspector` | `rail` | `{ "mode": ["graph", "runway"], "mode_not": ["proof", "remote", "compare"], "selected_node": true }` |

`proof_block_card` and `compare_dimension_card` are **child render targets** inside `proof_drawer` / `compare_lens`; they do not receive top-level `visible_when` in the default spec unless a custom view promotes them to standalone rail slots.

### Projection notice triggers

`projection_notice` content is derived from resolver state, not invented:

| Condition | Banner tone |
|-----------|-------------|
| `usingFixtureFallback === true` | fallback |
| `run_group` is `canvas-dev` with collectable-only nodes | collectable |
| `run_group` is `latest` or simulated dominates | simulated |
| Mixed collectable + simulated | mixed |

When `fixture_fallback: true` is added to `visible_when`, the notice may be shown only during fallback (optional stricter spec). Default v0 shows the notice whenever the derived tone is non-empty.

---

## Compare mode — missing binding tolerance

`binding.compare` is **`required: false`** in the default bindings map.

When compare projection fetch fails or file is absent:

1. `compare_lens` **still mounts** (`binding_missing_ok`).
2. Rail shows an **empty state** with honest copy (e.g. “No compare projection loaded”).
3. Resolver must **not** synthesize dimensions or run-group pairs.
4. Truth-guard: if `compare-projection.json` exists, assert `compare-lens` visible after mode click; if absent, assert empty state without fabricated claims.

This aligns with Track A gap: `compare-agent-runs.sh` may be missing while tier1 demo copies a pairwise JSON manually.

---

## Selection-reset policy

Adopted from Harmony patterns (`provenance-t3-harmony-patterns.md`):

### On `mode_id` change

1. Clear **operator draft** (`command` input → empty).
2. Clear **operator note** string.
3. Apply mode `default_focus`.
4. **Do not** clear `selectedId` when switching between `graph` and `runway` (inspector continuity).
5. **Clear** `selectedId` when entering `proof`, `remote`, or `compare` (inspector hidden; stale selection misleading).
6. **Restore** `selectedId` to `null` when returning to `graph` from lens modes if prior selection is not in current projection nodes.

### On `run_group` change

1. Clear `selectedId`.
2. Reset `focus` to `all`.
3. Clear operator draft and note.
4. Re-fetch all `bindings.*` per `refresh: on_run_group_change` where specified.
5. Reset D3 zoom transform to default (via `zoom_controls` reset or layout init).

### On binding resolver fallback

1. Set global `usingFixtureFallback`.
2. Show `projection_notice` with fallback tone.
3. Do not upgrade `source_kind` on bound projection slices.

Operator commands remain **local draft only** — never persisted as claims (M8 / AGENTS.md).

---

## Responsive routing

From `layout.responsive`:

| Viewport | Rail behavior |
|----------|---------------|
| `>= 720px` | Fixed **440px** inspector rail (`layout.regions.rail.width_px`) |
| `< 720px` | `collapse_rail: bottom_sheet` — lens components move to bottom sheet overlay |

`visible_when.viewport_min_px` / `viewport_max_px` gate desktop-only vs collapsed-only component instances when a view spec duplicates chrome for each breakpoint. Default v0 uses a single instance set; GridShell applies CSS grid area swap at `720px`.

Zoom controls stay in header at all breakpoints.

---

## Binding resolution (design reference for T3-I2)

Single resolver module — **no per-component fetch**:

1. Load view spec (bundled default or `?view=` / `localStorage`).
2. Fetch all `bindings.*.path` in parallel.
3. Apply `fallback` policy; set `usingFixtureFallback`.
4. Resolve `join_v1` bindings via `pageModel.ts` registry (`remote_lens_model`, etc.).
5. Expose `{ actionGraph, proofPacket, compareProjection, runway? }` to components.

### Runway binding (open question — recommended default)

**`runway.json` is an orphan** in `public/projections/` today.

| Option | Recommendation |
|--------|----------------|
| Promote `binding.runway` | Defer to T3-I2 |
| Delete orphan file | Defer to T3-I2 |
| **Graph-derived runway** | **Adopt for v1** — `validation_runway` binds `binding.action_graph` and derives lane order via `laneIndex(kind)` until T3-I2 promotes a dedicated runway projection |

Default spec should set `validation_runway.projection_binding` to `binding.action_graph` with a note in bindings that `binding.runway` is reserved.

---

## Operator command bar (open question — recommended default)

**Include in v1 view spec** as `operator_command_bar` in the `operator` region.

| Property | Value |
|----------|-------|
| `projection_binding` | none |
| Truth labels on spec | `source_kind: derived_v1`, `confidence: medium` |
| Persistence | none — local focus commands only |

Keyword router (`cache`, `fail`, `proof`, `agent`, `compare`, `runway`, `reset`) remains demo ergonomics until view-spec-driven filters replace it in a later wave.

---

## Run-group selector (open question — recommended default)

**Defer to wave 4.** For tier1 demo:

- Do **not** add `run_group_selector` to v1 `component_kind` enum.
- Document **disabled placeholder** pattern: a future `run_group_selector` instance with `props: { disabled: true, disabled_reason: "Retention index projection not available" }`.
- Current canvas has no run-group picker; `run_group` is read from loaded `action-graph.json`.

---

## Truth-guard extensions (T3-I target)

| Check | v1 design requirement |
|-------|----------------------|
| Graph node parity | keep `[data-graph-node-id]` vs projection |
| Compare schema | keep when file present |
| Proof block truth keys | validate committed `proof.json` |
| Projection notice on fallback | assert `[data-testid="projection-notice"]` |
| Mode rail per-mode | assert `[data-testid="canvas-mode-{mode_id}"]` on each button |

Shell root: `data-testid="nlfr-canvas-app"` (unchanged).

---

## Downstream

| Phase | Consumes this doc |
|-------|-------------------|
| T3-I1 | GridShell + resolver + `nlfr-default-v0.json` |
| T3-I2 | Extract graph, inspector, graph-derived runway |
| T3-I3 | Proof / remote / compare lenses + join bindings |
| T3-I4 | Composer validates against schema + routing rules |

Do not start T3-I1 until a default view spec instance validates against `view-spec.v1.schema.json` (wave 3 / I1 worker).
