# T3 Canvas Audit — App.tsx Monolith, Truth Guards, Extraction

**Worker:** `t3-r-canvas-audit` (explore)  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder/apps/canvas`  
**Status:** `DONE`

## Executive summary

The NLFR canvas is a **single-file React monolith**: `apps/canvas/src/App.tsx` (~947 lines) owns routing-by-mode, three projection fetches, D3 zoom, five lenses, inspector, operator command bar, and all presentational subcomponents. Layout math correctly lives in `layout.ts`; types in `types.ts`. Truth labeling is **strong on rendered nodes and proof/compare blocks** but **incomplete on lens-level and shell-level aggregates**.

Tier 3 implementation (T3-I*) should extract components and introduce `nlfr.view-spec.v1` bindings without changing evidence semantics. `public/projections/` is the canonical runtime data plane; there is no `dist/views` build artifact today — any "views drift" risk is between **committed projections**, **sampleProjection fallback**, and **mode-specific UI not driven by projection JSON**.

---

## App.tsx structure map

### State and data plane

| State | Type | Source |
|-------|------|--------|
| `projection` | `ActionGraphProjection` | fetch `/projections/action-graph.json` → fallback `sampleProjection` |
| `proofPacket` | `ProofPacket` | fetch `/projections/proof.json` → fallback `sampleProofPacket` |
| `compareProjection` | `CompareProjection \| null` | fetch `/projections/compare-projection.json` → null on miss |
| `mode` | `CanvasMode` | local: `graph \| runway \| proof \| remote \| compare` |
| `focus` | `FocusFilter` | local operator focus |
| `selectedId` | `string \| null` | graph selection |
| `usingFixtureFallback` | `boolean` | set when projection or proof fetch fails |

Three independent `useEffect` fetches on mount — no shared loader, no run-group selector, no refresh after export.

### UI regions (top to bottom)

1. **Projection notice** — `projectionNotice` memo; tones: fallback, collectable, simulated, mixed
2. **Topbar** — brand + run strip (summary counts + `remoteLens.modeLabel`)
3. **Mode rail** — five `IconButton` modes + zoom controls
4. **Canvas stage** — SVG graph, conditional overlays per mode
5. **Operator bar** — keyword command parser (`cache`, `fail`, `proof`, `agent`, `compare`, `runway`, reset)

### Embedded components (all in App.tsx)

| Component | Lines (approx) | Responsibility |
|-----------|----------------|----------------|
| `GraphNode` | ~40 | SVG node rendering + truth styling |
| `Inspector` | ~40 | Selected node dossier |
| `RunwayOverlay` | ~30 | Validation runway timeline |
| `ProofConstellation` | ~25 | In-graph proof summary (foreignObject) |
| `ProofDrawer` | ~30 | Full proof packet drawer |
| `RemoteLens` | ~55 | Remote boundary panel |
| `CompareLens` | ~45 | Multi-run compare panel |
| `CompareDimensionView` | ~55 | Per-dimension truth grid |
| `ProofBlockView` | ~65 | Proof block cards |
| `TruthLegend` | ~25 | Source kind legend |
| `IconButton` | ~15 | Mode rail buttons |

### Pure helpers (bottom of file)

- `highlightedIds` — focus filter logic
- `remoteLensModel` — derives remote UI from proof blocks (not projection invent)
- `unsupportedClaimsFromPayload`, `laneIndex`, `centerTransform`, formatting helpers

**Not in App.tsx:** `layoutProjection` → `layout.ts` (D3 force + kind anchors).

---

## Mode / lens behavior

| Mode | Primary surface | Projection binding |
|------|-----------------|-------------------|
| `graph` | SVG nodes/edges | `action-graph.json` |
| `runway` | `RunwayOverlay` | same graph nodes, sorted by `laneIndex(kind)` |
| `proof` | `ProofDrawer` + `ProofConstellation` | `proof.json` |
| `remote` | `RemoteLens` | proof blocks `remote_execution`, worker readiness |
| `compare` | `CompareLens` | optional `compare-projection.json` |

Mode switching is **local state only** — no URL routing, no persisted view spec, no composer.

### Operator command bar

Keyword router in `runOperatorCommand()` — demo ergonomics, not evidence:

- Sets `mode` and `focus` from substring match
- Updates `operatorNote` string
- Does not mutate projections or call backend

Harmony research (see `provenance-t3-harmony-patterns.md`) recommends keeping this as **non-persisted local draft** or replacing with view-spec-driven filters in T3-D.

---

## Truth-guard gaps

### What `truth-guard.mjs` validates today

1. Parses committed `public/projections/action-graph.json`
2. Builds expected node id set; Playwright compares rendered `[data-graph-node-id]` parity
3. If `compare-projection.json` exists: schema checks on root + each dimension (truth keys, id/title/summary, claims array)
4. Clicks Compare Runs; asserts `[data-testid="compare-lens"]` visible when compare file present

### Gaps (not validated)

| Gap | Risk | Severity |
|-----|------|----------|
| **Proof packet truth labels** | `proof.json` blocks not schema-checked in truth-guard | Medium |
| **Per-node truth keys on graph** | Only id parity, not `source_kind`/`evidence_refs` per node | Medium |
| **Fixture fallback visibility** | `usingFixtureFallback` notice not asserted in E2E | Low |
| **Remote lens derived metrics** | `remoteLensModel` computes display strings; no guard that labels match proof | Medium |
| **Runway overlay** | No test that runway events match projection node set | Low |
| **Projection notice accuracy** | Heuristic `projectionNotice` not tied to proof packet | Low |
| **Compare optional miss** | Null compare is OK; no warning when tier1 demo expects compare | Low |
| **Runway.json** | Fourth projection file in `public/projections/` — **not loaded by App.tsx** | High (drift) |

### App-level truth labeling strengths

- `Inspector`, `ProofBlockView`, `CompareDimensionView` render all four truth fields
- `TruthLegend` documents source kinds
- `remoteLensModel` pulls `unsupported_claims` from proof payloads
- Compare empty state explicitly names missing file path

### App-level truth labeling weaknesses

- **Topbar run strip** — summary numbers without per-field `source_kind`
- **`remoteLens.modeLabel`** — can be derived string not identical to proof block text
- **`ProofConstellation`** — foreignObject HTML; truth counts computed client-side from blocks (OK if blocks are truthful)
- **Graph edges** — inherit `source_kind` class but no inspector for edges
- **No edge/evidence drill-down** from compare dimension to proof block id

---

## `dist/` / `views` drift

### Build outputs

- Vite builds to `apps/canvas/dist/` when `npm run build` executes — **not committed**
- No `dist/views/` or persisted view registry in repo
- No server-side view renderer

### Projection drift vectors

| Artifact | Loaded by App? | Notes |
|----------|----------------|-------|
| `action-graph.json` | yes | 48KB; canvas-dev collectable dogfood |
| `proof.json` | yes | proof packet |
| `compare-projection.json` | yes (optional) | 4.8KB; M9 fixture |
| `runway.json` | **no** | 36KB committed; **orphan relative to App.tsx** |

`runway.json` suggests a prior or parallel runway projection experiment. App derives runway from `projection.nodes` instead. T3-D should either:

- wire `runway.json` as a first-class projection fetch, or
- stop committing orphan projections and document runway as graph-derived only

### Fixture fallback drift

`sampleProjection` / `sampleProofPacket` in `sampleProjection.ts` provide simulated chain when fetch fails. Canvas sets `usingFixtureFallback` and shows notice — good. Risk: developers may not notice fallback during local dev if dev server serves stale `public/projections/`.

### Committed vs runtime

Truth-guard reads **committed** `public/projections/`, not `data/*/projections/`. After `record-canvas-build.sh`, operator must copy/redact exports into `public/projections/` for canvas parity — documented in demo scripts but easy to drift.

---

## Extraction candidates (T3-I phases)

Priority order for splitting App.tsx without behavior change:

### Phase I1 — Shell + layout

| Extract | Target file | Props |
|---------|-------------|-------|
| `Topbar`, `ModeRail`, `ProjectionNotice` | `components/Shell.tsx` | projection summary, mode, callbacks |
| `OperatorBar` | `components/OperatorBar.tsx` | command state, `runOperatorCommand` |
| `TruthLegend` | `components/TruthLegend.tsx` | static |

### Phase I2 — Graph stack

| Extract | Target file | Notes |
|---------|-------------|-------|
| `GraphNode`, SVG layers | `components/GraphCanvas.tsx` | keep D3 zoom in parent or hook |
| `Inspector` | `components/EvidenceInspector.tsx` | |
| `RunwayOverlay` | `components/RunwayLens.tsx` | later bind to `runway.json` if promoted |

### Phase I3 — Proof / remote / compare lenses

| Extract | Target file | Notes |
|---------|-------------|-------|
| `ProofDrawer`, `ProofBlockView`, `ProofConstellation` | `components/ProofLens.tsx` | |
| `RemoteLens` | `components/RemoteLens.tsx` | keep `remoteLensModel` in `pageModel.ts` |
| `CompareLens`, `CompareDimensionView` | `components/CompareLens.tsx` | |

### Phase I4 — Page model purity

Move to `pageModel.ts` (Harmony pattern):

- `highlightedIds`
- `remoteLensModel`
- `projectionNotice` heuristic → `deriveProjectionNotice(projection, usingFallback)`
- `laneIndex`, label formatters

### Test hooks to preserve

- `data-testid`: `nlfr-canvas-app`, `projection-notice`, `canvas-mode-rail`, `action-graph-svg`, `validation-runway`, `proof-drawer`, `remote-execution-lens`, `compare-lens`, `evidence-inspector`, `truth-legend`, `operator-chat`
- `data-graph-node-id` on nodes
- `aria-label` on mode buttons (truth-guard uses `Compare Runs`)

---

## Monolith metrics

| Metric | Value |
|--------|-------|
| `App.tsx` LOC | ~947 |
| Embedded components | 11 |
| External modules | `layout.ts`, `types.ts`, `sampleProjection.ts`, `d3`, `lucide-react` |
| CSS | single `styles.css` (~1150+ lines) |
| Routes | 0 (mode state only) |

---

## Recommendations for T3-D / T3-I

1. **Extract lenses before GridShell** — lower risk than redesigning shell first
2. **Resolve `runway.json` orphan** — load or remove from `public/projections/`
3. **Extend truth-guard** — validate proof.json truth keys; assert `projection-notice` when using fixture
4. **Do not add backend fetch** — canvas stays projection-only per AGENTS.md
5. **Run-group selector** — out of scope for monolith audit; belongs in view-spec composer (see `provenance-t3-view-systems.md`)

---

## Source map

| Artifact | Path |
|----------|------|
| Monolith | `apps/canvas/src/App.tsx` |
| Layout | `apps/canvas/src/layout.ts` |
| Types | `apps/canvas/src/types.ts` |
| Fixtures | `apps/canvas/src/sampleProjection.ts` |
| Truth guard | `apps/canvas/scripts/truth-guard.mjs` |
| Projections | `apps/canvas/public/projections/` |
| Styles | `apps/canvas/src/styles.css` |
| Harmony patterns | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t3-harmony-patterns.md` |
