# T3-I Composer — Provenance

**Worker:** `t3-i-composer`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Implemented library-only view composer MVP under `apps/canvas/src/composer/` per `docs/design/view-composer-protocol.md`. Delivers synchronous `list_catalog`, `list_templates`, `validate_spec`, `preview_spec`, and `apply_patch` APIs. Bundled templates reference `nlfr-default-v0` (from `defaultViewSpec.ts`), `graph-only`, and `proof-review` (from `public/views/`). Composer output enforces `source_kind` ∈ `{derived_v1, simulated_v1}` — never `collectable_v1`. No UI drawer added (library MVP only).

---

## Inputs read

| Artifact | Path |
|----------|------|
| KOS startup routing | `docs/sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md` |
| Composer protocol | `docs/design/view-composer-protocol.md` |
| Component catalog | `docs/design/component-catalog.md` |
| View schema | `docs/design/view-spec.v1.schema.json` |
| Shell provenance | `docs/sessions/handoffs/tier1-agent-vision/wave-3/provenance-t3-i-shell.md` |
| View JSON templates | `apps/canvas/public/views/graph-only.json`, `proof-review.json` |

---

## Deliverables written

| File | Role |
|------|------|
| `apps/canvas/src/composer/index.ts` | Public API: `list_catalog`, `list_templates`, `validate_spec`, `preview_spec`, `apply_patch`, `exportViewSpec` |
| `apps/canvas/src/composer/templates.ts` | Template refs + `getTemplateSpec` for three bundled views |
| `apps/canvas/src/composer/catalog.ts` | 15-kind v1 catalog with props_schema |
| `apps/canvas/src/composer/validate.ts` | 12-gate validation (schema, catalog, bindings, joins, modes, privacy, source_kind) |
| `apps/canvas/src/composer/patch.ts` | Atomic patch ops batch |
| `apps/canvas/src/composer/preview.ts` | Read-only `render_plan` from `visible_when` + fixtures |
| `apps/canvas/src/composer/types.ts` | Request/response shapes |
| This file | Worker provenance |

---

## Design decisions

### Library-only MVP

No `ComposerDrawer` or `OperatorPanel` hook — broker can wire UI in a follow-up worker. `exportViewSpec` reuses strict validation + browser download pattern from `persistViewSpec.ts`.

### Truth labels

- Template metadata: `nlfr-default-v0` → `simulated_v1`; `graph-only` / `proof-review` → `derived_v1`
- `validate_spec` rejects `source_kind: collectable_v1` on any spec (composer never claims collectable execution facts)

### Templates

`graph-only` and `proof-review` bodies imported from existing `public/views/` JSON (read-only). `nlfr-default-v0` uses in-code `DEFAULT_VIEW_SPEC` to avoid duplicating the 15-component default.

### Validation scope

Full JSON Schema validation deferred — gate-based checks cover v1 enum, binding resolution, join registry (`pageModel.joinFnRegistry`), mode consistency, privacy patterns, and duplicate `instance_id`. `strict: true` promotes warnings (run_group mismatch, orphan bindings, missing optional projection) to errors.

### Patch atomicity

Failed op rolls back entire batch; partial specs allowed only when `allow_partial: true` on `apply_patch`.

---

## no_touch honored

- `apps/canvas/src/App.tsx`
- `apps/canvas/public/views/` (import-only)

---

## Proof

```bash
npm --prefix apps/canvas run build
```

Result: **PASS** (tsc + vite build, exit 0)

---

## Claims touched

| Claim | source_kind | confidence |
|-------|-------------|------------|
| Composer catalog lists 15 v1 kinds | derived_v1 | high |
| Bundled templates match protocol IDs | derived_v1 | high |
| Patch ops are atomic | derived_v1 | high |
| Preview render_plan is read-only | derived_v1 | high |
