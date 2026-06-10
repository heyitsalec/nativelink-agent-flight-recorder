# View Composer Protocol — `nlfr.view-spec.v1`

**Schema:** [`view-spec.v1.schema.json`](./view-spec.v1.schema.json)  
**Catalog:** [`component-catalog.md`](./component-catalog.md)  
**Routing:** [`routing.md`](./routing.md)  
**Status:** normative design (T3-D wave 2)  
**Date:** 2026-06-06

The view composer lets operators assemble `nlfr.view-spec.v1` documents from the [component catalog](./component-catalog.md) **without editing React**. MVP scope is **export JSON only** — validation, preview, and persistence are implemented in T3-I4 (`apps/canvas/src/composer/`). No server is required for MVP.

---

## Purpose

| Goal | Constraint |
|------|------------|
| Author layouts from the 15-kind catalog | Every instance must reference a valid `component_kind` |
| Bind projections declaratively | All fetches through resolver; no per-component fetch |
| Preview before export | Read-only canvas render from `preview_spec` |
| Persist operator layouts | File export + optional `localStorage`; not evidence |

Composer output is **layout metadata** (`source_kind: derived_v1` or `simulated_v1` for bundled templates). It must never claim collectable execution facts.

---

## Composer flow

```
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ list_catalog │ → │ list_templates   │ → │ Load template     │
│ list kinds   │    │ pick view_id     │    │ (nlfr-default-v0) │
└──────────────┘    └─────────────────┘    └──────────────────┘
         │                    │                        │
         v                    v                        v
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ apply_patch  │ → │ validate_spec    │ → │ preview_spec      │
│ edit spec    │    │ schema + gates   │    │ render_plan       │
└──────────────┘    └─────────────────┘    └──────────────────┘
         │                    │                        │
         v                    v                        v
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ apply_patch  │ → │ validate_spec    │ → │ Export view-spec  │
│ (iterate)    │    │ (final)          │    │ .json             │
└──────────────┘    └─────────────────┘    └──────────────────┘
```

---

## Message API

All messages are **synchronous function calls** in a static TS module (`apps/canvas/src/composer/index.ts`). Shapes are normative for T3-I4.

### `list_catalog`

**Request:** `{}`

**Response:**

```json
{
  "component_kinds": [
    {
      "kind": "action_graph_canvas",
      "region": "primary",
      "default_testid": "action-graph-svg",
      "binding_required": true,
      "props_schema": {
        "show_truth_legend": { "type": "boolean", "default": false },
        "zoom_controls": { "type": "boolean", "default": true }
      }
    }
  ],
  "schema_version": "nlfr.view-spec.v1",
  "count": 15
}
```

Returns one entry per v1 kind from [component-catalog.md](./component-catalog.md). Future kinds (wave 4+) are omitted.

---

### `list_templates`

**Request:** `{}`

**Response:**

```json
{
  "templates": [
    {
      "view_id": "nlfr-default-v0",
      "title": "NLFR Default Canvas",
      "description": "Equivalent to current App.tsx behavior",
      "source_kind": "simulated_v1"
    },
    {
      "view_id": "graph-only",
      "title": "Action Graph Only",
      "description": "Graph + inspector; no proof/compare lenses",
      "source_kind": "derived_v1"
    },
    {
      "view_id": "proof-review",
      "title": "Proof Review",
      "description": "Proof drawer primary; graph dimmed",
      "source_kind": "derived_v1"
    }
  ]
}
```

Template bodies ship as bundled JSON in T3-I4 or are generated from `nlfr-default-v0` skeleton. Wave 2 does not commit instance JSON under `docs/design/view-specs/`.

---

### `validate_spec`

**Request:**

```json
{
  "spec": { },
  "projections_root": "/projections",
  "strict": true
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `spec` | yes | Full or partial `nlfr.view-spec.v1` document |
| `projections_root` | no | Prefix for optional path existence checks during preview |
| `strict` | no | When true, warnings fail validation (default `false`) |

**Response:**

```json
{
  "ok": false,
  "errors": [
    { "code": "UNKNOWN_COMPONENT_KIND", "path": "/components/2/component_kind", "message": "…" }
  ],
  "warnings": [
    { "code": "RUN_GROUP_MISMATCH", "path": "/run_group", "message": "spec run_group canvas-dev != action_graph latest" }
  ]
}
```

---

### `preview_spec`

**Request:**

```json
{
  "spec": { },
  "projections_root": "/projections",
  "mode": "graph",
  "fixtures": {
    "binding.action_graph": "fixture:sampleProjection"
  }
}
```

**Response:**

```json
{
  "render_plan": {
    "regions": {
      "notice": ["notice"],
      "header": ["topbar", "modes", "zoom"],
      "primary": ["graph", "legend"],
      "rail": ["inspector-selected-node"],
      "operator": ["operator"]
    },
    "bindings_resolved": [
      { "key": "binding.action_graph", "status": "ok", "projection_kind": "action_graph" },
      { "key": "binding.compare", "status": "missing", "required": false }
    ],
    "visible_components": ["notice", "topbar", "modes", "graph", "legend", "operator"],
    "testids": ["nlfr-canvas-app", "projection-notice", "canvas-mode-rail", "action-graph-svg"]
  }
}
```

`render_plan` is read-only — preview does not mutate canvas state or projections.

---

### `apply_patch`

**Request:**

```json
{
  "spec": { },
  "ops": [
    { "op": "add_component", "value": { } },
    { "op": "remove_component", "instance_id": "legend" },
    { "op": "set_binding", "key": "binding.compare", "value": { } }
  ]
}
```

**Response:**

```json
{
  "spec": { },
  "applied": 3,
  "errors": []
}
```

If any op fails, **no ops are applied** (atomic batch). Partial specs are rejected unless `allow_partial: true` is set on the request.

---

## Patch operations

Patch ops are the **authoring mutation surface** for the composer UI. They produce a new spec object; they do not write to disk until export.

### Op reference

| `op` | Required fields | Effect |
|------|-----------------|--------|
| `add_component` | `value` (component instance) | Append to `components[]`; `instance_id` must be unique |
| `remove_component` | `instance_id` | Remove instance; clear `modes[].rail_component` / `primary_component` refs |
| `update_component` | `instance_id`, `value` (partial) | Merge into existing instance (`props`, `visible_when`, `projection_binding`) |
| `move_component` | `instance_id`, `region` | Change `region` slot |
| `set_binding` | `key`, `value` | Upsert `bindings[key]` |
| `remove_binding` | `key` | Delete binding; error if any component still references key |
| `add_mode` | `value` (mode object) | Append to `modes[]` |
| `update_mode` | `mode_id`, `value` (partial) | Merge mode entry |
| `remove_mode` | `mode_id` | Remove mode; error if `mode_rail.props.modes` still lists it |
| `set_layout` | `value` (partial layout) | Merge `layout` object (grid shell only) |
| `set_envelope` | `value` (partial) | Merge top-level fields (`title`, `description`, `run_group`, truth metadata) |
| `replace_components` | `value` (array) | Replace entire `components[]` (template load) |
| `replace_bindings` | `value` (object) | Replace entire `bindings` map (template load) |

### Op examples

**Add graph with legend:**

```json
{
  "ops": [
    {
      "op": "add_component",
      "value": {
        "instance_id": "graph-main",
        "component_kind": "action_graph_canvas",
        "region": "primary",
        "projection_binding": "binding.action_graph",
        "props": { "show_truth_legend": true },
        "visible_when": { "mode": ["graph", "runway", "proof", "remote", "compare"] }
      }
    }
  ]
}
```

**Wire optional compare binding:**

```json
{
  "ops": [
    {
      "op": "set_binding",
      "key": "binding.compare",
      "value": {
        "projection_kind": "compare",
        "path": "/projections/compare-projection.json",
        "required": false
      }
    }
  ]
}
```

**Add remote lens with join:**

```json
{
  "ops": [
    {
      "op": "add_component",
      "value": {
        "instance_id": "remote-lens",
        "component_kind": "remote_boundary_lens",
        "region": "rail",
        "projection_binding": {
          "kind": "join_v1",
          "sources": ["binding.action_graph", "binding.proof_packet"],
          "join_fn": "remote_lens_model",
          "source_kind": "derived_v1",
          "confidence": "medium",
          "evidence_refs": ["binding.proof_packet:blocks.remote_execution"]
        },
        "visible_when": { "mode": ["remote"] }
      }
    }
  ]
}
```

### Patch invariants

1. `component_kind` must be one of the 15 v1 enum values after every successful batch.
2. `instance_id` values are unique within `components[]`.
3. `projection_binding` as a string must resolve to a key in `bindings`.
4. `join_v1` `join_fn` must exist in the join registry (below).
5. `remove_binding` fails if references remain (fail-closed).

---

## Validation gates

Validation runs on `validate_spec` and before export. Order is fixed:

| # | Gate | Severity | Rule |
|---|------|----------|------|
| 1 | JSON Schema | error | Validate against [`view-spec.v1.schema.json`](./view-spec.v1.schema.json) |
| 2 | Catalog membership | error | Every `component_kind` ∈ v1 catalog (15 kinds) |
| 3 | Binding resolution | error | Every string `projection_binding` key exists in `bindings` |
| 4 | Join registry | error | Every `join_v1.join_fn` ∈ `pageModel` registry |
| 5 | Mode consistency | error | `mode_rail.props.modes` ⊆ `modes[].mode_id` |
| 6 | Region slots | error | Each `region` ∈ `layout.regions` keys |
| 7 | Secrets / privacy | error | Reject `props` containing env-var patterns, API keys, raw prompts, credentials |
| 8 | Agent provenance | error | Agent-related props may only use `model` + `prompt_sha256` prefix (M8) |
| 9 | Run group mismatch | warning | `spec.run_group` ≠ loaded `action_graph.run_group` |
| 10 | Orphan binding | warning | Binding key defined but no component references it |
| 11 | Missing optional projection | warning | `required: false` binding path not found at `projections_root` |
| 12 | Duplicate instance_id | error | Unique `components[].instance_id` |

### Error codes

| Code | Meaning |
|------|---------|
| `SCHEMA_VIOLATION` | JSON Schema validation failed |
| `UNKNOWN_COMPONENT_KIND` | Kind not in v1 enum |
| `UNRESOLVED_BINDING` | `projection_binding` string not in `bindings` |
| `UNKNOWN_JOIN_FN` | `join_fn` not registered |
| `BINDING_IN_USE` | `remove_binding` blocked by component ref |
| `DUPLICATE_INSTANCE_ID` | Collision in `components[]` |
| `SECRET_IN_PROPS` | Privacy gate tripped |
| `RAW_PROMPT_IN_PROPS` | Full prompt text in props |
| `MODE_REF_ORPHAN` | Mode points at missing `instance_id` |
| `RUN_GROUP_MISMATCH` | Warning: spec vs projection run_group differ |

---

## `join_fn` registry

Cross-binding joins must reference **pure functions** in `apps/canvas/src/pageModel.ts` (T3-I1). No ad hoc join logic inside components.

| `join_fn` | Sources | Output shape | Maps from (`App.tsx`) |
|-----------|---------|--------------|------------------------|
| `remote_lens_model` | `binding.action_graph`, `binding.proof_packet` | `RemoteLensModel` | `remoteLensModel()` |

Registry contract:

```typescript
type JoinFnRegistry = Record<
  string,
  (sources: Record<string, unknown>, ctx: ViewContext) => unknown
>;
```

New joins require a design doc update and registry entry before composer acceptance.

---

## Canvas boot (design only)

View spec loading at canvas startup — implemented in T3-I1, specified here for composer export targets.

| Mechanism | Precedence | Behavior |
|-----------|------------|----------|
| Query `?view=<view_id>` | 1 | Load bundled template or fetch `/view-specs/<view_id>.json` |
| `localStorage` key `nlfr.view-spec` | 2 | Parse stored JSON; validate before apply |
| Default | 3 | `nlfr-default-v0` bundled spec |

On successful load, binding resolver fetches all `bindings` once. Mode and selection state remain local; **mode or run-group change clears operator draft and stale selection** (Harmony adopt per routing.md).

---

## Implementation notes (T3-I4)

| Topic | Decision |
|-------|----------|
| Module path | `apps/canvas/src/composer/` — `catalog.ts`, `validate.ts`, `patch.ts`, `preview.ts` |
| Server | None for MVP; all messages in-process |
| Export | `downloadViewSpec(spec)` → `view-spec.json` + console validation report |
| Import | File picker → `validate_spec` → `localStorage.setItem('nlfr.view-spec', …)` |
| Tests | Unit tests for patch ops + validation gates; Playwright uses catalog testids |

Composer UI screens (MVP):

1. **Template picker** — `list_templates`
2. **Binding editor** — `set_binding` / `remove_binding` patch ops
3. **Component panel** — `add_component` / `remove_component` / `update_component`
4. **Mode editor** — `add_mode` / `update_mode` with rail mapping
5. **Preview** — `preview_spec` against fixtures or `public/projections/`
6. **Export** — `validate_spec` with `strict: true` then download

---

## Anti-patterns

1. **Live mutation path** — Composer exports JSON; it does not hot-patch running canvas without reload/validate.
2. **Server-side spec storage** — MVP is file + `localStorage` only; no multi-tenant spec DB.
3. **Inventing join functions in specs** — `join_fn` must be pre-registered; composer rejects unknown names.
4. **Bypassing validation on export** — Export always runs `validate_spec` with `strict: true`.
5. **Embedding projections in specs** — Specs reference paths only; never inline `nodes` or `blocks`.

---

## Related documents

| Document | Role |
|----------|------|
| [`component-catalog.md`](./component-catalog.md) | 15 kinds, testids, props |
| [`view-spec.v1.schema.json`](./view-spec.v1.schema.json) | Machine validation |
| [`routing.md`](./routing.md) | Modes, `visible_when`, selection-reset |
