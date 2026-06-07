# T3-D Design Wave — Task Packet (coord-t3-design)

## KOS arming (mandatory)

Read before acting: [`../KOS-startup-routing.md`](../KOS-startup-routing.md) · Cursor adapter: `/Users/alecbot/Documents/knowledge-os/adapters/cursor/README.md`

**Coordinator:** `coord-t3-design` · **Return DispatchManifest only; do not spawn subagents.**  
**DAG:** T3-D · **Phase:** design (wave 2)  
**Date:** 2026-06-06  
**Repo:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Blocked by:** Wave 1 research + `integration-brief-t3-design-inputs.md` (acknowledged)

---

## Objective

Produce normative design docs for `nlfr.view-spec.v1` — the projection-only view substrate that replaces implicit `CanvasMode` routing in `App.tsx`. **Design docs only**; no `App.tsx`, resolver, or GridShell implementation (T3-I*).

---

## North-star constraints (non-negotiable)

1. **Projection-only rendering** — view specs describe layout and bindings; they never invent nodes, edges, or audit events.
2. **Truth labels** — every projected slice and derived layout claim carries `source_kind`, `confidence`, `evidence_refs`, `redaction_state`.
3. **Evidence-first** — graph/work area primary; tables and marketing chrome secondary.
4. **No raw prompt export** — agent views show `model` + `prompt_sha256` prefix only (M8 contract).
5. **Honest boundaries** — remote/worker/queue claims stay gated until direct evidence exists.

---

## Input artifacts (read-only)

| Artifact | Path |
|----------|------|
| Integration brief | `docs/sessions/handoffs/tier1-agent-vision/wave-1/integration-brief-t3-design-inputs.md` |
| View systems | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-view-systems.md` |
| Canvas audit | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-canvas-audit.md` |
| Harmony patterns | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-harmony-patterns.md` |
| Current monolith | `apps/canvas/src/App.tsx` |
| Types | `apps/canvas/src/types.ts` |
| Truth guard | `apps/canvas/scripts/truth-guard.mjs` |
| Projections | `apps/canvas/public/projections/` |

---

## Deliverables

| # | File | Owner worker | Priority |
|---|------|--------------|----------|
| 1 | `docs/design/view-spec.v1.schema.json` | `t3-d-schema-routing` | P0 |
| 2 | `docs/design/routing.md` | `t3-d-schema-routing` | P0 |
| 3 | `docs/design/component-catalog.md` | `t3-d-catalog-composer` | P0 |
| 4 | `docs/design/view-composer-protocol.md` | `t3-d-catalog-composer` | P2 |

**Out of scope for wave 2:** `docs/design/view-specs/*.json`, `apps/canvas/**`, Python/TS implementation.

---

## Worker split

### `t3-d-schema-routing` — schema + routing

**Writes:** `view-spec.v1.schema.json`, `routing.md`  
**Reads:** provenance-t3-view-systems, integration brief, `types.ts`

#### `view-spec.v1.schema.json` requirements

- `$schema` + `$id`: `nlfr.view-spec.v1`
- Top-level envelope: `schema_version`, `view_id`, `title`, `description`, `generated_at`, `run_group`, truth metadata
- `layout`: `grid_shell_v1` with regions (`notice`, `header`, `primary`, `rail`, `operator`), `responsive.breakpoint_px: 720`, `collapse_rail: bottom_sheet`
- `components[]`: `instance_id`, `component_kind`, `region`, `props`, `projection_binding`, `visible_when`
- `bindings`: map of binding keys → `projection_binding` sub-schema
- `modes[]`: lens registry replacing `CanvasMode`
- `component_kind` enum — **exactly 15 v1 kinds** (from view-systems provenance):
  - `projection_notice`, `topbar_summary`, `mode_rail`, `action_graph_canvas`, `evidence_inspector`, `validation_runway`, `proof_constellation`, `proof_drawer`, `proof_block_card`, `remote_boundary_lens`, `compare_lens`, `compare_dimension_card`, `truth_legend`, `operator_command_bar`, `zoom_controls`
- `projection_kind` enum: `action_graph`, `proof_packet`, `compare`, `runway`, `run_group_index`
- `projection_binding` sub-schema: `path`, `required`, `selector`, `fallback` (`fixture:*` | `none`), `refresh`
- Join binding variant: `kind: join_v1`, `sources[]`, `join_fn` (for remote lens)
- JSON Schema draft-2020-12 or draft-07 (match repo convention if any)

#### `routing.md` requirements

- **Modes registry** — five v1 modes mapped from current `CanvasMode`: `graph`, `runway`, `proof`, `remote`, `compare`
- Per-mode: `mode_id`, `label`, `icon`, `primary_component`, `rail_component`, `default_focus`, optional `requires_binding`
- **`visible_when` rules** — which components appear in which mode/region (replace hardcoded conditionals in App.tsx)
- Mode rail `data-testid` contract: preserve `canvas-mode-rail`; specify per-mode testid pattern for T3-I truth-guard extension
- Selection-reset policy (Harmony adopt): mode/run-group change clears operator draft and stale selection
- Responsive routing: rail → bottom sheet at `<720px`
- Compare mode: tolerate missing `binding.compare` (empty state, not synthesized data)
- Open questions documented with recommended default:
  - `runway.json` orphan → recommend graph-derived runway until T3-I2 promotes binding
  - operator command bar → include in v1 spec as `derived_v1` local-only chrome
  - run-group selector → defer; document disabled placeholder pattern for tier1 demo

---

### `t3-d-catalog-composer` — catalog + composer protocol

**Writes:** `component-catalog.md`, `view-composer-protocol.md`  
**Reads:** provenance-t3-view-systems, provenance-t3-canvas-audit, `App.tsx`, truth-guard

#### `component-catalog.md` requirements

- Table per `component_kind` (15 rows): kind → React source (App.tsx component) → props schema → `projection_binding` → `data-testid` → region slot
- Copy **stable selectors** from current canvas for Playwright continuity:

| kind | testid (preserve) |
|------|-------------------|
| shell root | `nlfr-canvas-app` |
| projection_notice | `projection-notice` |
| mode_rail | `canvas-mode-rail` |
| action_graph_canvas | `action-graph-svg` |
| validation_runway | `validation-runway` |
| proof_drawer | `proof-drawer` |
| remote_boundary_lens | `remote-execution-lens` |
| compare_lens | `compare-lens` |
| evidence_inspector | `evidence-inspector` |
| truth_legend | `truth-legend` |
| operator_command_bar | `operator-chat` |

- Note graph nodes use `data-graph-node-id` (not testid)
- Props: document boolean flags (`show_truth_legend`, `zoom_controls`) and binding key references
- Future kinds (wave 4+): `run_group_selector`, `agent_provenance_card`, `audit_ledger_timeline`, `worker_lane_board` — listed but marked **not in v1 enum**
- Anti-patterns section: no per-component fetch, no view-spec-as-data-source

#### `view-composer-protocol.md` requirements

- MVP purpose: operator-authored view specs without editing React; export JSON only (T3-I4 implements)
- Message table: `list_catalog`, `list_templates`, `validate_spec`, `preview_spec` (request/response shapes)
- Validation gates:
  - JSON Schema against `view-spec.v1.schema.json`
  - Every `component_kind` ∈ catalog
  - Every `projection_binding` key resolves in `bindings`
  - Reject secrets, env vars, raw prompts in `props`
  - Warn on `run_group` mismatch vs action graph projection
- Composer flow diagram (load catalog → template → bind → preview → export)
- Canvas boot: `?view=<view_id>` or `localStorage` key `nlfr.view-spec` (design only)
- Implementation note: static TS module in `apps/canvas/src/composer/` (T3-I4); no server for MVP
- Reference `join_fn` registry in `pageModel.ts` for cross-binding joins

---

## Grid shell reference (inform routing + schema)

```
┌────────────────────────────────────────────────────────────┐
│ projection_notice (banner)                                  │
├────────────────────────────────────────────────────────────┤
│ topbar_summary │ mode_rail │ zoom_controls (optional)       │
├──────────────────────────────┬─────────────────────────────┤
│ action_graph_canvas          │ rail: inspector OR lens     │
│ + truth_legend               │ (mode-dependent)            │
├──────────────────────────────┴─────────────────────────────┤
│ operator_command_bar (local draft only)                     │
└────────────────────────────────────────────────────────────┘
```

- Rail width: 440px desktop; collapse to bottom sheet `<720px`
- CSS: extend `styles.css` grid areas; do not Harmony-clone warm paper tokens

---

## Acceptance criteria (coordinator integrate)

| Check | Method |
|-------|--------|
| Schema is valid JSON | `python3 -c "import json; json.load(open('docs/design/view-spec.v1.schema.json'))"` |
| 15 component kinds in enum | grep/count in schema |
| Catalog row count = 15 | manual |
| All truth-guard testids preserved in catalog | cross-ref canvas audit |
| No App.tsx changes | git diff scope |
| Composer protocol references schema path | link check |

**Deferred to T3-I1:** schema validates `nlfr-default-v0.json` instance (spec JSON not in wave 2).

---

## Downstream (T3-I sequencing)

| Phase | Depends on T3-D |
|-------|-----------------|
| T3-I1 | GridShell + binding resolver + default view spec JSON |
| T3-I2 | Extract graph + inspector |
| T3-I3 | Extract proof/remote/compare lenses |
| T3-I4 | Composer MVP + persist |

Do not start T3-I1 until schema validates default spec (wave 3 or I1 worker creates instance JSON).

---

## Provenance (workers must write)

- `docs/sessions/handoffs/tier1-agent-vision/wave-2/provenance-t3-d-schema-routing.md`
- `docs/sessions/handoffs/tier1-agent-vision/wave-2/provenance-t3-d-catalog-composer.md`

---

## Return vocabulary

`DONE` | `DONE_WITH_CONCERNS` | `NEEDS_CONTEXT` | `BLOCKED`
