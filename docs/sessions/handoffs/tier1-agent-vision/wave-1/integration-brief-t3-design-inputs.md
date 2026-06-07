# Wave 1.5 Integration Brief — T3-D Design Inputs

**From:** Wave 1 research (`coord-t3-research` + broker integration)  
**For:** `coord-t3-design` (T3-D) — blocked until this brief is acknowledged  
**Date:** 2026-06-06

## Purpose

Synthesize five wave-1 research workers into actionable design constraints for Tier 3 GUI substrate. Track B (canvas/view system) proceeds in parallel with Track A spine work; T3-D must not wait for `tier1-agent-demo.sh` but must align with tier1 run groups and compare dimensions.

---

## North-star constraints (non-negotiable)

1. **Projection-only rendering** — canvas and view specs never invent nodes, edges, or audit events.
2. **Truth labels on every claim** — `source_kind`, `confidence`, `evidence_refs`, `redaction_state` on projected slices and derived layout metadata.
3. **Evidence-first, not dashboard-first** — graph/work area primary; tables and marketing chrome secondary.
4. **No raw prompt export** — agent views show `model` + `prompt_sha256` prefix only (M8 contract).
5. **Honest boundaries** — remote/worker/queue claims stay gated until direct evidence exists.

---

## Research synthesis

### Canvas audit (`t3-r-canvas-audit`)

- `App.tsx` is a 947-line monolith with five implicit modes (`graph`, `runway`, `proof`, `remote`, `compare`).
- Layout math is correctly isolated in `layout.ts`; extraction should follow I1→I4 phases in audit doc.
- **Resolve `runway.json` orphan** — either bind as projection or remove from `public/projections/`.
- Truth-guard covers graph id parity + compare schema only; extend in T3-I to cover proof packet labels.

### Harmony patterns (`t3-r-harmony`)

**Adopt:**

- Single shell + mode lens (not four product tabs).
- Fixed-width inspector rail (~440px).
- Selection resets dependent UI state.
- Disabled controls with explicit reason strings.
- Pure `pageModel.ts` functions over projection JSON.

**Reject:**

- Fake provider preview/apply loop.
- Chat composer as persisted claim source.
- Static SVG graph decoration.
- Character/call-sign worker personas.

### View systems (`t3-r-view-systems`)

- Introduce `nlfr.view-spec.v1` as the explicit view document.
- `component_kind` catalog maps 1:1 from current lenses (15 kinds).
- `projection_binding` contract centralizes fetch + selector + fallback policy.
- Composer MVP exports JSON; canvas loads via query param or localStorage.

### Spine cross-track inputs (for demo alignment)

| Track A gap | T3-D implication |
|-------------|------------------|
| `compare-agent-runs.sh` missing | Compare lens should tolerate missing binding; tier1 demo copies one pairwise JSON to `public/projections/` |
| `agent-bugfix-1` run group | Proof/agent blocks may appear — remote lens unchanged; compare dimension 4 relevant |
| `bounded_llm_v1` vs `cursor_adapter_v1` | View spec docs explain kind labels; no UI conflation |

---

## T3-D deliverables (prioritized)

### P0 — Schema and catalog

1. **`docs/design/view-spec.v1.schema.json`**
   - Envelope fields from `provenance-t3-view-systems.md`
   - `projection_binding` sub-schema
   - `component_kind` enum (15 v1 kinds)

2. **`docs/design/component-catalog.md`**
   - Table: kind → props → binding → testid
   - Copy stable selectors from current App.tsx for Playwright continuity

3. **`docs/design/routing.md`**
   - `modes` registry replaces `CanvasMode`
   - `visible_when` rules for rail components

### P1 — Default specs

4. **`docs/design/view-specs/nlfr-default-v0.json`**
   - Equivalent to current monolith behavior

5. **`docs/design/view-specs/tier1-demo.json`**
   - Graph + proof + compare modes
   - Bindings pointing at tier1 projection paths
   - Notice banner for collectable vs simulated

### P2 — Composer protocol

6. **`docs/design/composer-protocol.md`**
   - `list_catalog`, `validate_spec`, `preview_spec` messages
   - Validation gates (no secrets, binding keys resolve)

---

## Grid shell design (T3-D → T3-I1)

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

- CSS: extend `styles.css` grid areas; do not Harmony-clone warm paper tokens.
- Rail width: 440px desktop; collapse to bottom sheet < 720px (from view-spec responsive block).

---

## Binding resolver design (T3-D → T3-I2)

Single module `apps/canvas/src/bindings/resolver.ts`:

1. Load view spec (default bundled JSON).
2. Fetch all `bindings.*.path` in parallel.
3. Apply fallbacks; set global `usingFixtureFallback`.
4. Expose `{ actionGraph, proofPacket, compareProjection, runway? }` to components.
5. Reject specs that reference unknown projection kinds at validate time.

**No per-component fetch** — eliminates triple `useEffect` in App.tsx.

---

## Truth-guard extensions (design acceptance criteria)

T3-D spec should require these E2E checks before T3-I merge:

| Check | Current | Target |
|-------|---------|--------|
| Graph node parity | yes | keep |
| Compare schema | yes | keep |
| Proof block truth keys | no | validate committed `proof.json` |
| Projection notice when fallback | no | assert `data-testid=projection-notice` |
| Mode rail testids | partial | add `data-testid` per mode from view spec |

---

## Implementation sequencing (coord-t3-implement)

| Phase | Scope | Depends on |
|-------|-------|------------|
| T3-I1 | GridShell + binding resolver + default view spec | T3-D schema |
| T3-I2 | Extract graph + inspector | I1 |
| T3-I3 | Extract proof/remote/compare lenses | I2 |
| T3-I4 | Composer MVP + persist | I3 |

Do not start I1 until `view-spec.v1.schema.json` validates the default spec JSON.

---

## Parallelism with Track A

- T3-I can proceed with committed `public/projections/` fixtures while Track A records live tier1 run groups.
- When `compare-agent-runs.sh` lands, copy `compare-canvas-dev-vs-agent-bugfix-1.json` → `public/projections/compare-projection.json` for demo.
- Tier1 demo script is **not** a blocker for schema design; it is a blocker for tier1-specific view spec acceptance tests.

---

## Proof matrix (T3-D completion)

```bash
# Schema validates default spec
# (add after T3-D lands)
python3 -c "import json, jsonschema; ..."

# Existing canvas truth path unchanged until I1
npm --prefix apps/canvas run test:truth
uv run pytest -q
```

---

## Open questions for human review

1. **`runway.json`** — promote to bound projection or delete from public artifacts?
2. **Operator command bar** — keep in v1 view spec or defer to local-only dev tool?
3. **Run-group selector** — defer to wave 4 or include disabled placeholder with reason in tier1 demo spec?

---

## Handoff artifact index

| Worker | Provenance |
|--------|------------|
| t3-r-harmony | `provenance-t3-harmony-patterns.md` |
| t3-r-canvas-audit | `provenance-t3-canvas-audit.md` |
| t3-r-view-systems | `provenance-t3-view-systems.md` |
| t1-spine-r-adapter-scenario | `provenance-t1-spine-audit-adapter-scenario.md` |
| t1-spine-r-compare-retention | `provenance-t1-spine-audit-compare-retention.md` |
| broker integrate | `worker-results.json`, this brief |
