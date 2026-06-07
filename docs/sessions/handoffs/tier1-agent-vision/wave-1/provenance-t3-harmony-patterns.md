# Harmony Cockpit Patterns — NLFR Wave 1 Provenance

**Worker:** `t3-r-harmony` (explore)  
**Date:** 2026-06-06  
**Source:** `/Users/alecbot/Documents/harmony/cockpit/` (public four-page research packet + shipped desktop renderer)  
**Status:** `DONE`

## Executive summary

Harmony’s four-page cockpit is a **single shared operator shell** (brand, live/replay state, brain queue, tab nav, source banner, refresh/mute) wrapping four **work-first page lenses** on one `HarmonySnapshot` fixture. The product center of gravity is **canvas-left / operator-rail-right** on the home page; sibling pages reuse the shell and cross-page selection (`selectedSignal`, `selectedNode`) without inventing backend state.

For NLFR, the highest-value transfers are structural, not cosmetic: **projection-only rendering**, **truth-labeled status strips**, **preview-before-confirm mutation gating**, **inspector rails fed by evidence refs**, and **stable `data-testid` selectors**. Reject Harmony’s fake-provider action loop, multi-tab product surface, and warm-paper visual system unless NLFR explicitly expands scope beyond evidence-first recorder + sparse canvas.

Harmony proves the pattern “one instrument, many lenses” with fixture-backed E2E and public-boundary scans. NLFR already has a sparser single-canvas mode rail (`graph` / proof / compare); Harmony suggests how to add **worker lane** and **audit ledger** lenses later without breaking the evidence spine.

---

## Shell + grid anatomy

### Desktop grid (shared across all tabs)

```
┌─────────────────────────────────────────────────────────────────┐
│ HEADER: brand | brain-queue dock | tab nav | refresh/mute/tools │
├─────────────────────────────────────────────────────────────────┤
│ BANNER: source status strip (freshness, controls, local, network)│
├─────────────────────────────────────────────────────────────────┤
│ PAGE BODY (switches by activePage)                               │
└─────────────────────────────────────────────────────────────────┘
```

- **Root:** `.harmony-desktop` — CSS grid `rows: auto auto minmax(0,1fr)`, `max-width: 1680px`, `100vh`, warm paper tokens (`--h-paper`, `--h-pine`, `--h-moss`, `--h-clay`, `--h-gold`).
- **Header:** flex row — brand block (serif wordmark + attending dot + selected signal id), center **Brain queue dock**, right **page tabs** (`harmony | workers | atlas | ledger`), icon tools.
- **Banner:** `.harmony-banner` gold-soft strip with `SourceStatusStrip` — four `StatusPill` chips (source freshness, preview/apply capability, local fleet, external network).
- **State ownership:** `App.tsx` holds snapshot, `selectedSignalId`, `activePage`, `queueOpen`, `preview`, `auditEvents`, `replayState` (SSE), `busy`, `muted`. Child pages receive props; they do not fetch independently.

### Home page (`harmony`) — canonical two-column work grid

```
┌──────────────────────────────┬──────────────────┐
│ GRAPH PANEL (flex 1)         │ THREAD PANEL     │
│  toolbar: search + pills     │  (fixed 440px)   │
│  graph stage + node cards    │  head + scroll     │
│  quick actions (FAB, cmd-k)  │  review/provenance │
│  run strip (bottom chips)    │  preview + audit   │
│                              │  compose (disabled)│
└──────────────────────────────┴──────────────────┘
```

- `.harmony-main` → `grid-template-columns: minmax(0,1fr) 440px`.
- Graph panel: absolute-positioned flow nodes + SVG edges, selection popover, related-run chips.
- Thread panel: operator command surface — context chips (`Context`, `Preview first`, `Fake only`), scrollable cards (review packet, provenance manifest, action preview, audit log), draft-only composer.

### Sibling page grids (same shell, different primary work area)

| Page | Grid | Primary | Inspector / rail |
|------|------|---------|----------------|
| **Workers** | lane board + right inspector | role lanes with run stacks | proof, corpus, write scope, no-touch, verification; disabled live repair/config |
| **Atlas** | graph stage + dossier rail | search/filter/focus on fixture edges | relationships, linked signal, related runs, boundary notes |
| **Ledger** | single cockpit shell, inner `ledger-main-grid` | timeline + plan cartridge | preview boundary (freshness guard), trace detail, local-only proof grid |

### Shared page regions (research fidelity rules)

Every page is expected to expose:

1. **Pulse/context strip** — fleet stats, metric strip, or status pills at top of panel.
2. **Primary work area** — graph, lane board, or timeline (never table-first landing).
3. **Inspector or thread rail** — scrollable detail with modular sections.

### Layout helpers (`pageModel.ts`)

- `buildWorkerLanes(runs)` — group by role, sort by blocked/review/active weight.
- `buildGraphLayout(snapshot)` — fixed positions + curved SVG paths from fixture edges.
- `buildLedgerEntries(events)` — freshness (`fresh` / `stale` / `historical`) from preview age.
- `latestManifestForRun`, `signalForRun`, `statusTone` — cross-page selection glue.

---

## Operator patterns

### 1. Brain queue as attention router

- Collapsible dock in header; depth-coded rows (`loud` / `medium` / `quiet` → needs review / ready / drafted).
- Selecting a signal clears preview and closes queue — **selection resets mutable UI state**.
- Queue footer: explicit boundary copy (“Local replay only. No provider credentials are read.”).

### 2. Cross-page selection continuity

- `selectedSignal` drives Workers run auto-select, Atlas focus, Ledger intent context.
- `selectNode` on graph resolves signal via `nodeId` mapping.
- Pages sync local selection when parent prop changes (`useEffect` on `selectedSignal` / `propSelectedNodeId`).

### 3. Preview-first mutation pipeline

Canonical chain (research + Ledger lens strip):

```
ActionIntent → ActionPreview → ConfirmedFakeAction → AuditEvent
```

- Preview required before confirm; `canApply` + freshness window (~15 min) gates fake apply.
- `busy` flag disables concurrent preview/apply.
- SSE (`replayServer`) prepends audit events; snapshot `actionHistory` merged in Ledger.
- Disabled real-provider buttons always show **explicit reason** in `title` / adjacent copy.

### 4. Evidence cards in operator rail

Thread panel stacks typed cards:

- **Review packet** — decision, proof, risks (labeled `fictional`).
- **Provenance manifest** — tool-style fold with JSON subset (corpus, writeScope, verification).
- **Action preview** — `wouldChange` before/after in `<pre>`.
- **Audit trail** — last N local events with type tone.

### 5. Truth and boundary signaling

- Source banner always visible (not buried in settings).
- Status pills use `good` / `warn` / `bad` tone classes.
- Workers fleet disclosure + Ledger safety marquee repeat fixture/local-only policy.
- Chat-top chips surface policy at point of action (`Preview first`, `Fake only`).

### 6. Operator affordances (mostly demo-gated)

- Search bars present but may be read-only on home graph.
- Command K / Design loop FAB — visual cues only in public demo.
- Composer is draft-only; Send disabled with reason.
- Workers “Repair and config” section: disabled affordances with per-control `reason` string.

### 7. Test and release hooks

- Stable selectors: `data-testid="harmony-page"`, `harmony-tab-*`, `workers-page`, `workers-run-card`, `action-preview`, `audit-log`.
- `data-design-label` on key regions for screenshot review.
- E2E: click all four tabs, assert nonblank roots; public-boundary scan in CI.

---

## Portable patterns for NLFR

NLFR mandate (from `AGENTS.md`): evidence-first recorder; canvas renders **projection JSON only** with `source_kind`, `confidence`, `evidence_refs`, `redaction_state` on every projected claim.

### Adopt

| Harmony pattern | NLFR application |
|-----------------|------------------|
| **Single shell + mode/page lens** | Keep one canvas shell; add lenses (graph, proof packet, compare, future worker/ledger) as tabs or mode rail without new data sources. |
| **Top status / provenance strip** | Extend NLFR projection notice banner into a multi-pill strip: run group, projection fetch state, dominant `source_kind`, redaction summary. |
| **Canvas-wide + fixed inspector rail** | NLFR already uses graph + side panel; fix inspector width and scroll regions like Harmony’s 440px thread panel. |
| **Selection resets dependent state** | When switching run group or selected node, clear operator draft and any stale preview/confirm UI. |
| **Preview / confirm gating semantics** | Map to NLFR proof workflow: show projected change set before claiming “applied”; never enable actions without `evidence_refs`. |
| **Modular inspector sections** | Proof packet blocks, compare dimensions, and node dossiers as stacked modules with mono micro-labels. |
| **Disabled-with-reason controls** | For out-of-scope v1 features (live RE dashboard, OTLP, auth): show locked affordances with explicit “not captured in v1” reasons. |
| **`pageModel`-style pure layout functions** | Keep graph layout, lane grouping, ledger ordering in testable TS/Python pure functions over projection JSON — not in components. |
| **Stable `data-testid` contract** | Mirror Harmony’s tab/page/root selectors for Playwright truth-guard tests. |
| **Fixture-first public demo** | Align with NLFR `verify-demo.sh` + committed `apps/canvas/public/projections/`; fictional ids only in public artifacts. |

### Adapt

| Harmony pattern | NLFR adaptation |
|-----------------|---------------|
| **Brain queue (signals)** | Replace with **run-group queue** or **action attention queue** derived from Bazel/cache events in projection — depth becomes confidence or failure severity, not chat urgency. |
| **Worker lane board** | Port as **agent/run lane view** only when parser emits role-labeled runs with proof strings; use `derived_v1` labels, not fictional “call signs”. |
| **Atlas graph** | NLFR graph already uses D3 zoom + `layoutProjection`; add Harmony-style focus filters (`selection ring`, `signal-linked`) as projection-driven filters, not hardcoded SVG paths. |
| **Ledger timeline** | Port as **audit/history lens** over SQLite-exported events or proof packet timeline — freshness guard becomes “projection stale vs ingested_at”. |
| **Provenance manifest card** | Map to NLFR **proof packet** + artifact manifest hashes — never raw corpus paths from customer repos. |
| **Warm paper design system** | NLFR can keep sparse/dev aesthetic; borrow **information hierarchy** (serif title, mono labels, status tones) without full Harmony token set. |
| **SSE replay** | Adapt to optional **local refresh** of projection JSON after `nlfr graph export` — no fake provider EventSource unless explicitly scoped. |
| **ActionIntent / fake provider** | Adapt concept to **export/regenerate/ingest intents** (read-only) rather than external GitHub/Linear writes. |

### Reject

| Harmony pattern | Why not for NLFR v1 |
|-----------------|---------------------|
| **Four-tab product surface** | Scope creep; v1 order is cache proof → ingest → parsers → projection → sparse canvas. Extra tabs wait until evidence path is proven. |
| **Fake provider preview/apply loop** | NLFR is recorder, not operator console for third-party APIs. No `ActionIntent → ConfirmedFakeAction` unless redefined for local artifact exports only. |
| **Chat thread + composer** | Agent chat integration is out of scope; risks inventing backend state. Operator notes belong outside canvas or as non-persisted local draft only. |
| **Character / call-sign worker personas** | Violates evidence-first tone; use run ids, roles, and proof refs instead of “Patch Pilot”. |
| **Hardcoded graph edge SVG** | Home `GraphEdges` uses static paths; NLFR must render edges from projection only. |
| **Live/replay SSE as source of truth** | Canvas must not treat stream as authoritative; SQLite + projection export remain canonical. |
| **External network / provider mode toggles** | Misleading for NLFR demo unless tied to real NativeLink modes (`cache-only`, future LRE). |
| **Full Harmony visual clone** | Risks UI-first dashboard drift; NLFR canvas stays projection-sparse. |
| **Table-first or landing-page framing** | Research rules explicitly forbid; keep graph/work area primary. |
| **Claims of worker/queue correlation** | Do not copy Harmony’s implied fleet correlation without direct evidence (AGENTS.md truth labels). |

---

## Anti-patterns

1. **Dashboard drift** — Leading with metric tables or marketing copy instead of graph/canvas work area. Harmony research gate calls this out explicitly; NLFR DEMO_SCRIPT already warns “surface vs spine.”

2. **UI-invented state** — Rendering nodes, edges, or audit events not present in projection JSON or proof packet. Harmony avoids this via fixture `HarmonySnapshot`; NLFR must keep `sampleProjection` fallback visibly labeled (`usingFixtureFallback`).

3. **Silent mutation** — Enabling confirm/apply without preview freshness guard. Ledger’s `getPreviewFreshness` + disabled confirm is the positive pattern.

4. **Hidden boundary** — Credentials, live writes, or external network implied but not labeled. Harmony repeats boundary in queue foot, Workers disclosure, Ledger marquee.

5. **Monolithic page components** — `App.tsx` is large but delegates pages; layout math belongs in `pageModel.ts`. Avoid stuffing ingest/layout logic into React components in NLFR.

6. **Static graph decoration** — Harmony home graph uses fixed `nodePosition(index)` and static SVG paths for demo fidelity. NLFR must not copy this — edges and positions must come from `layoutProjection(projection)`.

7. **Cross-run correlation overclaim** — Atlas “related runs” and worker lanes suggest fleet narrative; NLFR compare lens already limits to `derived_v1` proof summaries with bounded `evidence_refs`.

8. **Privacy leakage in demos** — Real repo URLs, personal paths, raw traces. Harmony uses `Demo Lab` / `DL-*` fixtures and public-boundary CI scans; NLFR uses redacted paths and hashes.

9. **Broken selection sync** — Letting child pages keep stale `selectedRunId` when parent signal changes. Harmony uses `useEffect` guards; NLFR multi-lens selection needs the same discipline per run group.

10. **Untested lenses** — Shipping a new tab/mode without truth-guard E2E. Harmony requires tab clicks + nonblank roots + screenshot review; NLFR has `test:truth` — extend it when adding lenses.

---

## Source map (read-only audit)

| Artifact | Path |
|----------|------|
| Research gate | `harmony/cockpit/docs/four-page-cockpit-research.md` |
| Completion proof | `harmony/cockpit/docs/four-page-cockpit-completion.md` |
| Shared shell | `harmony/cockpit/apps/desktop/src/renderer/App.tsx` |
| Layout helpers | `harmony/cockpit/apps/desktop/src/renderer/pages/pageModel.ts` |
| Page slices | `WorkersPage.tsx`, `AtlasPage.tsx`, `LedgerPage.tsx` + CSS pairs |
| Design tokens | `harmony/cockpit/apps/desktop/src/renderer/styles.css` |
| NLFR canvas baseline | `nativelink-agent-flight-recorder/apps/canvas/src/App.tsx` |

No private credentials, live endpoints, or personal paths were copied into this handoff.
