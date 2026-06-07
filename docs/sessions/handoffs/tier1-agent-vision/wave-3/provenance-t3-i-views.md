# T3-I Views — Provenance

**Worker:** `t3-i-views`  
**Coordinator:** `coord-t3-implement`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Authored three schema-valid `nlfr.view-spec.v1` JSON instances under `apps/canvas/public/views/` for T3-I1 canvas boot. The default spec (`nlfr-default-v0.json`) includes all 15 v1 `component_kind` values, five mode lenses, and bindings for `action_graph`, `proof_packet`, and optional `compare`. Slim templates `graph-only.json` and `proof-review.json` match composer protocol descriptions. No `apps/canvas/src/**` edits.

---

## Inputs read

| Artifact | Path |
|----------|------|
| KOS routing | `docs/sessions/handoffs/tier1-agent-vision/KOS-startup-routing.md` |
| JSON Schema | `docs/design/view-spec.v1.schema.json` |
| Routing spec | `docs/design/routing.md` |
| Component catalog | `docs/design/component-catalog.md` |
| Composer templates | `docs/design/view-composer-protocol.md` |
| Projection run_group | `apps/canvas/public/projections/action-graph.json` (`canvas-dev`) |

---

## Deliverables written

| File | Description |
|------|-------------|
| `apps/canvas/public/views/nlfr-default-v0.json` | Full tier1 layout: 15 components, 5 modes, 3 bindings |
| `apps/canvas/public/views/graph-only.json` | Graph + runway + inspector; action_graph binding only |
| `apps/canvas/public/views/proof-review.json` | Proof-primary layout; dimmed graph; proof_packet binding |
| This file | Worker provenance |

---

## Design decisions

### Default spec (`nlfr-default-v0`)

- **Components (15):** All v1 catalog kinds — shell chrome, graph canvas, mode overlays (runway, proof constellation), rails (inspector, proof drawer, remote join, compare lens), child cards (proof block, compare dimension), operator bar.
- **Bindings:** `binding.action_graph` and `binding.proof_packet` required with fixture fallbacks; `binding.compare` optional (`required: false`, `fallback: none`) per routing.md compare tolerance.
- **Remote lens:** Inline `join_v1` on component with `join_fn: remote_lens_model` and truth labels.
- **Runway:** Graph-derived via `binding.action_graph` (routing recommended default until T3-I2 promotes `binding.runway`).
- **Props arrays:** Schema `component_props` allows only scalar values; list props encoded as comma-separated strings (e.g. `modes: "graph,runway,..."`).

### `graph-only`

- Modes: `graph`, `runway` only.
- Bindings: `binding.action_graph` only — no proof/compare/remote components.
- Operator commands trimmed to graph/runway keywords.

### `proof-review`

- Single `proof` mode; `primary_component` is `proof-constellation` (drawer in rail).
- Graph remains mounted with `dimmed: true` prop for background context.
- Bindings: `action_graph` + `proof_packet`.

---

## Proof

```bash
python3 -c "import json; [json.load(open(p)) for p in ['apps/canvas/public/views/nlfr-default-v0.json','apps/canvas/public/views/graph-only.json','apps/canvas/public/views/proof-review.json']]"
# exit 0

python3 -c "import json; s=json.load(open('apps/canvas/public/views/nlfr-default-v0.json')); assert s['schema_version']=='nlfr.view-spec.v1'; assert len(s['components'])>=10; assert len(s['modes'])==5"
# exit 0 — components: 15, modes: 5

# Additional schema validation (jsonschema Draft202012Validator):
# OK nlfr-default-v0.json, graph-only.json, proof-review.json
```

---

## Out of scope (honored)

- `apps/canvas/src/**` — T3-I1 GridShell/resolver implementation
- View composer UI — T3-I4
- Binding resolver / pageModel joins — T3-I2/I3

---

## Return

```json
{
  "worker_id": "t3-i-views",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/tier1-agent-vision/wave-3/",
  "artifacts": {
    "provenance": "provenance-t3-i-views.md",
    "views": [
      "apps/canvas/public/views/nlfr-default-v0.json",
      "apps/canvas/public/views/graph-only.json",
      "apps/canvas/public/views/proof-review.json"
    ]
  },
  "claims_touched": [],
  "blockers": []
}
```
