# T3-D Catalog + Composer — Provenance

**Worker:** `t3-d-catalog-composer`  
**Coordinator:** `coord-t3-design`  
**Date:** 2026-06-06  
**Repo:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

## Scope

Design-only deliverables for wave 2 (no `apps/` or `src/` edits):

| File | Action |
|------|--------|
| `docs/design/component-catalog.md` | created |
| `docs/design/view-composer-protocol.md` | created |
| `docs/sessions/handoffs/tier1-agent-vision/wave-2/provenance-t3-d-catalog-composer.md` | created |

## Inputs read

| Artifact | Use |
|----------|-----|
| `docs/sessions/handoffs/tier1-agent-vision/wave-2/task-packet-t3-design.md` | Acceptance criteria, 15-kind enum, testid table |
| `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-view-systems.md` | Catalog mapping, binding contract, composer sketch |
| `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-canvas-audit.md` | App.tsx structure, truth-guard gaps, testid inventory |
| `apps/canvas/src/App.tsx` | Component sources, props behavior, `data-testid` / `data-graph-node-id` |
| `apps/canvas/scripts/truth-guard.mjs` | Selectors asserted in E2E (`action-graph-svg`, `compare-lens`, node parity) |

## Deliverable summary

### `component-catalog.md`

- **15 rows** — full v1 `component_kind` enum aligned with task packet and view-systems provenance.
- Per-kind tables: React source, region, `projection_binding`, props, `visible_when`, truth notes.
- **Stable testids** preserved from current canvas for Playwright continuity (11 selectors + shell root).
- Graph nodes documented as `data-graph-node-id` (not testid).
- Future kinds (`run_group_selector`, `agent_provenance_card`, `audit_ledger_timeline`, `worker_lane_board`) listed as wave 4+ only.
- Anti-patterns: no per-component fetch, no view-spec-as-data-source, no operator persistence, no synthesized compare/runway.

### `view-composer-protocol.md`

- MVP purpose: operator-authored specs, export JSON only (T3-I4 implements).
- Message API: `list_catalog`, `list_templates`, `validate_spec`, `preview_spec`, **`apply_patch`**.
- **Patch ops:** `add_component`, `remove_component`, `update_component`, `move_component`, `set_binding`, `remove_binding`, `add_mode`, `update_mode`, `remove_mode`, `set_layout`, `set_envelope`, `replace_components`, `replace_bindings`.
- Validation gates (12) with error codes; references [`view-spec.v1.schema.json`](../../design/view-spec.v1.schema.json).
- Composer flow diagram; canvas boot via `?view=` and `localStorage` key `nlfr.view-spec`.
- `join_fn` registry: `remote_lens_model` → future `apps/canvas/src/pageModel.ts`.

## Acceptance self-check

| Check | Result |
|-------|--------|
| Catalog row count = 15 | pass (numbered table + per-kind sections) |
| Truth-guard testids in catalog | pass — cross-ref `truth-guard.mjs` + canvas audit |
| No App.tsx changes | pass — docs only |
| Composer references schema path | pass — links to `view-spec.v1.schema.json` |
| Patch ops documented | pass — `apply_patch` + op reference table |

## Deferred / coordination notes

- **`view-spec.v1.schema.json`** and **`routing.md`** owned by `t3-d-schema-routing`; catalog links to them but does not duplicate schema JSON.
- **T3-I testids** for kinds without selectors today (`topbar-summary`, `zoom-controls`, `proof-constellation`, per-mode `mode-{id}`, block/dimension cards) documented as T3-I targets in catalog.
- **`pageModel.ts`** does not exist yet; join registry is a design contract for T3-I1.
- **Template JSON** (`nlfr-default-v0.json`) not in wave 2 scope; `list_templates` returns ids only.

## Return vocabulary

`DONE`
