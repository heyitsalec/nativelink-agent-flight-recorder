# T3-I Shell — Provenance

**Worker:** `t3-i-shell`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Implemented view-spec-driven canvas shell infrastructure under `apps/canvas/src/` without modifying `App.tsx`, `panels/`, or `public/views/`. Delivers `GridShell`, binding resolver, view load/persist, routing hooks (`visible_when`, selection-reset), `pageModel` join registry, and bundled `nlfr-default-v0` spec equivalent to current `App.tsx` layout per `routing.md`.

---

## Inputs read

| Artifact | Path |
|----------|------|
| KOS startup routing | `docs/sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md` |
| Routing spec | `docs/design/routing.md` |
| View composer protocol | `docs/design/view-composer-protocol.md` |
| View schema | `docs/design/view-spec.v1.schema.json` |
| Canvas types | `apps/canvas/src/types.ts` |
| App patterns (read-only) | `apps/canvas/src/App.tsx` |

---

## Deliverables written

| File | Role |
|------|------|
| `apps/canvas/src/view/types.ts` | `ViewSpec`, bindings, `visible_when`, layout types |
| `apps/canvas/src/view/defaultViewSpec.ts` | Bundled `nlfr-default-v0` (15 components, 5 modes, 3 bindings) |
| `apps/canvas/src/view/loadViewSpec.ts` | `?view=` → localStorage → default precedence |
| `apps/canvas/src/view/persistViewSpec.ts` | `nlfr.view-spec` localStorage + download helper |
| `apps/canvas/src/view/ViewContext.tsx` | Provider: spec load, resolver, route state, join resolution |
| `apps/canvas/src/bindings/resolver.ts` | Parallel binding fetch + fixture fallback |
| `apps/canvas/src/pageModel.ts` | `remote_lens_model`, projection notice, highlight/focus helpers |
| `apps/canvas/src/layout/GridShell.tsx` | CSS grid shell, region slots, 720px rail bottom-sheet |
| `apps/canvas/src/routing/useViewRoute.ts` | Mode + selection state with Harmony reset policy |
| `apps/canvas/src/routing/visibleWhen.ts` | Declarative `visible_when` evaluator |
| `apps/canvas/src/routing/selectionReset.ts` | Mode/run-group selection-reset pure functions |
| This file | Worker provenance |

---

## Design decisions

### Bundled default spec

`public/views/` is no-touch for this worker; `nlfr-default-v0` ships in `defaultViewSpec.ts` and is returned by `loadViewSpec()` when no query param or localStorage override exists.

### Runway binding

Per `routing.md` recommendation: `validation_runway` binds `binding.action_graph`; dedicated `binding.runway` deferred to T3-I2.

### Join registry

`remote_lens_model` registered in `pageModel.ts` `joinFnRegistry`; matches `view-composer-protocol.md` contract.

### GridShell integration surface

`GridShell` accepts `renderComponent(instance)` — panel extraction (T3-I2/I3) wires catalog kinds without shell changes. `ViewProvider` remains optional until broker integrates `App.tsx`.

### Selection reset (routing.md)

- Mode change: clear operator draft; apply `default_focus`; preserve `selectedId` on graph↔runway; clear on proof/remote/compare.
- Run-group change: clear selection, focus `all`, operator draft, zoom reset hook.

---

## no_touch honored

- `apps/canvas/src/App.tsx`
- `apps/canvas/src/panels/`
- `public/views/`

---

## Proof

```bash
npm --prefix apps/canvas run build
# exit 0 — tsc -b && vite build
```

---

## Downstream

| Phase | Consumes |
|-------|----------|
| T3-I2 | Panel components + `GridShell` `renderComponent` wiring |
| T3-I3 | Proof/remote/compare lens panels |
| T3-I4 | Composer validates against schema + routing rules |
| Broker integrate | Replace `App` body with `ViewProvider` + `GridShell` |

---

## Return

`DONE`
