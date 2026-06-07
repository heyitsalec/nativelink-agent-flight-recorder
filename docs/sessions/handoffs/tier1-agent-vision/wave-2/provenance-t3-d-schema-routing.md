# T3-D Schema + Routing — Provenance

**Worker:** `t3-d-schema-routing`  
**Coordinator:** `coord-t3-design`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Delivered normative design artifacts for `nlfr.view-spec.v1`: JSON Schema (`docs/design/view-spec.v1.schema.json`) and routing specification (`docs/design/routing.md`). The schema uses draft-2020-12 (matching `contracts/*.json`), defines exactly **15** `component_kind` enum values, five `projection_kind` values, `projection_binding` direct + `join_v1` variants, `grid_shell_v1` layout with `720px` rail collapse, and a `modes` lens registry replacing `CanvasMode`. No `apps/` or `src/` edits.

---

## Inputs read

| Artifact | Path |
|----------|------|
| Task packet | `docs/sessions/handoffs/tier1-agent-vision/wave-2/task-packet-t3-design.md` |
| Integration brief | `docs/sessions/handoffs/tier1-agent-vision/wave-1/integration-brief-t3-design-inputs.md` |
| View systems | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-view-systems.md` |
| Canvas types | `apps/canvas/src/types.ts` (read-only) |
| Schema convention | `contracts/canvas_projection.v1.json` (draft-2020-12) |

---

## Deliverables written

| File | Description |
|------|-------------|
| `docs/design/view-spec.v1.schema.json` | Full envelope, layout, components, bindings, modes, truth labels, `$defs` |
| `docs/design/routing.md` | Modes registry, `visible_when` matrix, selection-reset, responsive, open questions |
| This file | Worker provenance |

---

## Schema decisions

### Identity

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: `nlfr.view-spec.v1` (per task packet)

### `component_kind` enum (15 v1 kinds)

`projection_notice`, `topbar_summary`, `mode_rail`, `action_graph_canvas`, `evidence_inspector`, `validation_runway`, `proof_constellation`, `proof_drawer`, `proof_block_card`, `remote_boundary_lens`, `compare_lens`, `compare_dimension_card`, `truth_legend`, `operator_command_bar`, `zoom_controls`

Future kinds (`run_group_selector`, `agent_provenance_card`, etc.) intentionally **excluded** — deferred to wave 4+ per view-systems provenance.

### `projection_binding`

- Direct: `projection_kind`, `path`, `required`, `selector`, `fallback` (`fixture:*` | `none`), `refresh`
- Join: `kind: join_v1`, `sources[]`, `join_fn` + truth labels for derived views (remote lens)
- Component-level binding: binding key string **or** inline `join_v1` object

### Layout

- `grid_shell_v1` with regions `notice`, `header`, `primary`, `rail` (440px), `operator`
- `responsive.breakpoint_px: 720`, `collapse_rail: bottom_sheet` (const-enforced in schema)

### Truth metadata

Envelope requires `source_kind`, `confidence`, `evidence_refs`, `redaction_state` — aligned with `types.ts` and AGENTS.md truth labels.

---

## Routing decisions

### Modes

Five modes map from `CanvasMode`: `graph`, `runway`, `proof`, `remote`, `compare` with icons, primary/rail `instance_id` references, `default_focus`, and optional `requires_binding`.

### `visible_when`

Replaces `App.tsx` conditionals (`mode === "proof"`, inspector gating, etc.) with declarative rules documented in `routing.md` matrix.

### Testid contract

- Preserve `canvas-mode-rail`
- Add per-mode pattern `canvas-mode-{mode_id}` for T3-I truth-guard extension

### Open questions — recommended defaults (documented in routing.md)

| Question | Default |
|----------|---------|
| `runway.json` orphan | Graph-derived runway via `binding.action_graph` until T3-I2 |
| Operator command bar | Include in v1 as `derived_v1` local-only chrome |
| Run-group selector | Defer; disabled placeholder pattern for tier1 demo |

---

## Proof

```bash
python3 -c "import json; json.load(open('docs/design/view-spec.v1.schema.json'))"
# exit 0

python3 -c "
import json
s = json.load(open('docs/design/view-spec.v1.schema.json'))
kinds = s['$defs']['component_kind']['enum']
assert len(kinds) == 15, kinds
print('component_kind count:', len(kinds))
"
```

---

## Out of scope (honored)

- `docs/design/component-catalog.md` → `t3-d-catalog-composer`
- `docs/design/view-composer-protocol.md` → `t3-d-catalog-composer`
- `docs/design/view-specs/*.json` → wave 3 / T3-I1
- `apps/canvas/**` implementation

---

## Return

`DONE`
