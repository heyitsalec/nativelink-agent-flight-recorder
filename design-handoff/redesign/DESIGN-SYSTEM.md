# Handoff: NLFR Canvas UI Redesign

## Overview

Ground-up visual redesign of the **NLFR (NativeLink Agent Flight Recorder) canvas** — the single-page operator console that renders truth-labeled build/test evidence projections for AI-agent-authored code. The redesign keeps every existing capability and replaces the visual system: one token system, one unified "truth language" for all four truth labels + agent provenance, first-class dark mode, a density-solved Action Graph, a scannable Proof Packet, and a command-palette reframing of the operator bar.

The product invariant that shapes everything: **only recorded evidence is shown, and no claim may ever look stronger than its label.** Every visual decision below serves that.

## About the Design Files

The file in this bundle (`NLFR Redesign.dc.html`) is a **design reference created in HTML** — a pannable canvas of 15 hi-fi mockup boards, not production code. Your task is to **recreate these designs in the existing NLFR canvas codebase**: React 19 + Vite + TypeScript, `d3` for the graph, `lucide-react` for icons, no CSS framework. Replace the current ~1959-line hand-rolled `styles.css` with the token system in this document (a reference `tokens.css` is included). Keep the projection-only rendering model: the app reads static JSON from `public/projections/` — no backend, no sockets, no external fonts/CDNs.

The mockups render against the real sample projections (`action-graph.json` / `proof.json` / `compare-projection.json` shapes). Every value shown maps to a real projection field; do not add UI for data that isn't in the projections.

## Fidelity

**High-fidelity.** Colors, type sizes/weights, spacing, radii, shadows, and copy are final. Recreate pixel-faithfully using the codebase's patterns (lucide-react replaces the inline SVG icons — names are given per component below).

Boards are referenced by their canvas ids: 1a foundations, 1b truth language, 1c/1d Action Graph light/dark, 1e/1f Proof Packet light/dark, 1g Evidence Inspector, 1h Remote Boundary, 1i Compare Runs, 1j Validation Runway, 1k Composer, 1l command palette + states, 1m mobile 390w, 1n rationale, 1o remaining proof blocks + node variants.

---

## Design Tokens

Reference implementation: `tokens.css` in this folder. Light values live on `:root`; dark re-maps the same custom properties under `[data-theme="dark"]` (also honor `prefers-color-scheme: dark` when no explicit override). Declare `color-scheme: light dark`.

### Truth hues (semantic anchors — never repurpose)

| Token | Light | Dark | Tint (bg) light / dark |
|---|---|---|---|
| `--truth-collectable` | `#0C7A68` | `#3ECFB4` | `rgba(12,122,104,0.10)` / `rgba(62,207,180,0.12)` |
| `--truth-derived` | `#A8660F` | `#E2A55B` | `rgba(168,102,15,0.10)` / `rgba(226,165,91,0.12)` |
| `--truth-simulated` | `#505AAD` | `#9AA5EF` | `rgba(80,90,173,0.10)` / `rgba(154,165,239,0.12)` |
| `--truth-future` | `#64747F` | `#8FA2AD` | `rgba(100,116,127,0.10)` / `rgba(143,162,173,0.10)` |
| `--failure` | `#B23C33` | `#F08A82` | `rgba(178,60,51,0.06)` / `rgba(240,138,130,0.07)` |

Fallback-banner tint: `#FBF3E4` bg + `#E3C98F` border + `#7A4C10` text (derived hue at ~12%; dark: derive from `--truth-derived` at 12% alpha).

### Neutral ramps

Light `--n0…--n9`: `#FBFCFC #F4F6F7 #E9EDEE #D8DFE1 #B9C4C7 #8FA0A4 #5F7378 #3F545A #23363C #122026`
Dark `--n0…--n9` (re-mapped, darkest first): `#0B1315 #121D20 #1A282C #24343A #3A4C52 #5C7075 #82999E #A8BCBF #CCDADB #EAF2F2`

Semantic aliases (light → dark):
- app bg `#EEF2F3` → `#0B1315`; dot-grid `radial-gradient(circle, rgba(13,32,38,0.055) 1px, transparent 1px) 0 0/24px 24px` (dark: `rgba(234,242,242,0.05)`)
- ink `#15262C` → `#EAF2F2`; body `#33474D` → `#A8BCBF`; muted `#5F7378` → `#82999E`; faint `#8FA0A4` → `#5C7075`; disabled/faintest `#B9C4C7` → `#3A4C52`
- hairline `#E9EDEE` → `#24343A`; control border `#D8DFE1` → `#24343A`; row bg `#F9FAFB` → `#1A282C`

### Elevation (one frosted-glass recipe, three levels)

| Level | Background | Blur | Border | Shadow |
|---|---|---|---|---|
| E1 card | solid `#FFFFFF` / `#121D20` | none | `1px solid rgba(13,32,38,0.10)` / `rgba(234,242,242,0.10)` | none |
| E2 floating panel | `rgba(255,255,255,0.85)` / `rgba(18,29,32,0.85)` | `backdrop-filter: blur(14px)` | same as E1 | `0 10px 30px rgba(13,32,38,0.12)` / `rgba(0,0,0,0.35–0.45)` |
| E3 drawer/overlay | `rgba(255,255,255,0.90)` / `rgba(18,29,32,0.92)` | `blur(20px)` | `1px solid rgba(13,32,38,0.12)` / `rgba(234,242,242,0.12)` | `0 24px 60px rgba(13,32,38,0.20)` / `rgba(0,0,0,0.5)` |

### Spacing, radius, focus

- Space scale (4px base): `4 8 12 16 24 32 48` → `--space-1…7`
- Radius: `6` controls · `10` chips/cells · `14` cards · `16` drawers · `20` boards · `999` pills → `--radius-control/chip/card/drawer/panel/pill`
- Focus ring (everywhere, both themes): `2px` solid `--truth-collectable` + `3px` halo `rgba(12,122,104,0.25)`

### Type scale (system stack, zero dependency — floor 11px, weights 400/500/600/700 only)

- UI: `-apple-system, "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`
- Mono (hashes, ids, metrics, enums): `ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace`

| Token | Size/line | Weight | Use |
|---|---|---|---|
| `--text-display` | 26/32 | 650 | drawer & lens titles |
| `--text-title` | 19/26 | 600 | panel headers |
| `--text-heading` | 14/20 | 600 | card titles |
| `--text-body` | 13/19 | 400 | summaries, prose |
| `--text-secondary` | 12–12.5 | 400–600 | row labels, chips |
| `--text-caption` | 11/14 | 500–600 | captions, meta — the floor |
| `--text-overline` | 11/14 | 600, +8% tracking, uppercase | section labels ("TRUTH LEGEND") |
| `--text-mono` | 12/17 (11–11.5 in dense rows) | 450–600 | evidence refs, metrics |

Stat numerals: mono 16–22/600. **Nothing below 11px; retire all 8–9px / 700–820 styles.**

---

## The Truth Language (load-bearing — implement exactly)

One encoding, learned once, read everywhere. **Never color alone** — every state has a shape/weight difference that survives grayscale.

### 1. `source_kind` → shape + hue
- `collectable_v1` — **filled circle** ●, collectable teal. Human label "Recorded / from real tools".
- `derived_v1` — **diamond** ◆ (square rotated 45°, r≈1.5px), derived amber. "Computed / from artifacts".
- `simulated_v1` — **filled triangle** ▲, simulated indigo. "Simulated / deterministic fixture".
- `future` — **dashed-outline circle** ◌ (1.5–1.6px dashed), future slate. "Not yet collected". **Future/unproven is ALWAYS dashed** (rings, borders, connector lines) and never gets a filled glyph.

Glyph sizes: 9–11px in rows/legends, 8px inline in node meta.

### 2. `confidence` → neutral 3-bar meter (never colored by source hue)
Three ascending bars (widths 3–3.5px, heights 4/6.5/9 small or 5/8/11 in card headers, gap 1.5px, radius 1px). Filled = `--n7` light / `--n7`-dark (`#A8BCBF`); empty = hairline (`#D8DFE1` / `#24343A`).
- high = 3 filled · medium = 2 · low = 1 · unknown = 0 filled + mono `?` suffix.
Tooltip on hover: `confidence: high ▮▮▮ · medium ▮▮ · low ▮ · unknown ?`.

### 3. `redaction_state` → treatment on the value itself
- `safe` — quiet: small check glyph + muted "safe" in truth grids/card headers; no chrome on the value.
- `redacted` — **lock chip on the value**: mono text (e.g. `[REDACTED:abs_path]/bazel-test.log`), lock icon, 1px control border, radius 6, and hatched bg `repeating-linear-gradient(45deg, rgba(63,84,90,0.08) 0 4px, transparent 4px 8px)` (dark: `rgba(204,218,219,0.10)`). Redacted values keep their layout slot — withheld ≠ missing.
- `blocked` — solid chip: bg `--n7`/`#A8BCBF`, inverted text, slash-circle icon. Value never rendered.
- `unknown` — dotted-border chip with `?`.

### 4. `provenance_class` → same families reused (agents)
Pill badge (radius 999, mono 10.5/600, tint bg + 1px tinted border):
- `receipt_verified_v1` → filled teal circle w/ check — collectable family — "receipt_verified" / short "● verified"
- `operator_asserted_v1` → amber diamond — derived family — "◆ asserted"
- `stub_receipt_v1` → indigo triangle — simulated family — "▲ stub"

### 5. Status → glyph, not color alone
completed/pass = check (teal stroke), failed = `✕`/alert in failure red. **Red is rationed**: it appears ONLY on recorded failures and unsupported-claims chips. "Not observed" is slate-dashed and calm, never red.

### Unsupported-claims chip
Mono 11px, failure color, `1px solid` failure @ 35%, tint bg, radius 999, slash-circle icon, e.g. `⊘ worker identity`. Section heading: overline in failure color — "UNSUPPORTED CLAIMS — NAMED, NOT HIDDEN".

---

## Screens / Views

### Global shell (all screens; boards 1c/1d)

- **Context banner** — 36px tall, full width, tone = evidence mix: collectable tint bg (`rgba(12,122,104,0.09)`) + 1px bottom border @22% + dark-teal text (`#0B5A4E` light / `#7FD8C6` dark). Left: 9px source dot + "**canvas-dev** run group — `collectable_v1` dogfood projection · 70 nodes" (12px). Right: "evidence mix" caption + 110×6px stacked bar (segments per source-kind share, slate for future). Compare lens re-tones the banner with the derived tint.
- **Header** — 60px, E2 surface, `blur(14px)`, hairline bottom. Left→right, 20px gaps: wordmark (28px radius-9 teal square with 14px white crosshair-node glyph; "NLFR" 13.5/700 +2% tracking over "NativeLink Agent Flight Recorder" 11px faint), **View picker** (bordered control, radius 8: overline "VIEW" + "NLFR Default Canvas" 12.5/600 + chevron-down), spacer, **run-summary strip** (mono 14/600 numbers + 11.5px faint labels: `7 runs · 70 nodes · 0 cache events · 0 failures`, 1px hairline separators), **honest remote pill** (1.25px dashed border pill: dashed-circle glyph + "remote execution — not observed" 11px), theme toggle (32px bordered square, moon/sun).
- **Left tool rail** — floating E2 panel 44px wide at (16, 116), radius 12, 32px icon buttons: zoom-in, zoom-out, fit; divider; 5 lens buttons (icons: graph = 3-node network, runway = 3 horizontal bars, proof = file-check, remote = globe, compare = split columns; lucide: `zoom-in zoom-out maximize network rows-3/list file-check globe columns-2`). Active lens = solid ink chip (`--n9` light / `--n9`-dark `#EAF2F2`) with inverted icon.
- **Truth legend** — bottom-left E2 card, 280px, padding 12/14 (board 1b shows both themes). Header row: overline "TRUTH LEGEND" + `⌘L` keycap. Four rows (hover bg `rgba(13,32,38,0.05)` / `rgba(234,242,242,0.06)`, radius 8, `title` tooltip carries the raw enum + definition): glyph (18px slot) + human label 12/600 ("Recorded", "Computed", "Simulated", "Not yet collected") + 11px faint descriptor. Divider. Bottom row: three hoverable icon groups with tooltips — confidence meter + "Confidence", hatched lock mini-chip + "Redaction", ●◆▲ trio + "Provenance" (11/600 muted labels).
- **Operator command bar** — bottom-center pill, 660px, E3: `⌘K` keycap chip, placeholder "Filter or jump — failures, cache, agents, proof, runway, reset" (12.5px faint, single line, ellipsis), hairline divider, info icon + "local filter · not evidence" (10.5px faintest, tooltip: "Operator commands filter and navigate the loaded projection only. They are never persisted or exported as evidence.").

### 1. Action Graph (default; 1c light / 1d dark)

Density model replaces the 8-node cap: **group by run, expand on demand, level-of-detail on zoom.**
- Node = rounded card (radius 12): 160–190px wide, padding 9/11, source-hue border 1.5px (1.25px for artifacts/invocations), E1/E2 bg, soft shadow. Contents: 26–28px radius-8 kind-icon plate on source tint; label 12/600 (mono 11.5/600 for file/command labels) with faint mono suffix (`#1`, `cmd:0`); meta row = 8px source glyph + mini confidence meter + mono 11px kind/duration (`run · 5.4s`) + status check.
- Kind icons (lucide): run `play`, invocation `terminal`, artifact `file-text`, agent `bot`, change `git-commit-vertical`, target `target`, action `zap`, worker/remote-exec = icon plate clipped to hexagon `clip-path: polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)` (board 1o).
- Cluster capsules (collapsed groups): dashed 1.25px source-hue pill, mono 11/600 teal — "2 invocations · 6 artifacts", "3 artifacts" — with chevron; connected by dashed edges. Multi-node clusters (the 7-changes card) add a stacked halo `box-shadow: 0 0 0 4px rgba(12,122,104,0.07)`.
- Edges: 1.5px curved cubic paths in source hue @ 35–45% opacity; dashed to collapsed capsules. Agent → change → run → invocation → artifact flows left→right; 7 runs in a vertical column (95px pitch).
- Emphasis (run #1 expanded): border 1.5–2px + halo `0 0 0 3px rgba(12,122,104,0.16)`.
- Top-right grouping pill (E2): grid icon + "group **by run** · detail **auto**" + chevron. Bottom-right zoom readout: mono 11px faint "fit · 100% · 70 nodes / 70 shown" — the count must always prove nothing is hidden.
- Agent nodes show the provenance badge directly below the node.

### 2. Evidence Inspector (1g)

Right drawer 420px, E3, radius 16, at (right:16, top:112, bottom:16). Selected node gets 2px border + `0 0 0 4px rgba(12,122,104,0.22)` halo; non-neighbors dim to 45–55% opacity; connected edge brightens to 70%.
Sections (hairline-divided, padding 14/22, each with an 11px overline):
1. Header: overline "EVIDENCE INSPECTOR" + close ✕; 40px icon plate + label 19/600 + mono id 11px faint.
2. **Truth labels** — 2×2 grid of `--n1` cells (radius 10): caption ("source/confidence/redaction/status") over value with its encoding (glyph + "Recorded" in hue; meter + "high"; check + "safe"; check + "completed").
3. **Agent receipt** (if present): overline + `receipt_verified` badge; key–value rows (110px label column, 11.5px): model (mono 600 + "server-resolved" note), `prompt_sha256` / `response_sha256` (mono, middle-truncated, copy icon), raw prompt → hatched lock chip "never exported — hash only".
4. Failure callout (if any; board 1o): failure-tint box (1px @30% border, radius 10): alert icon + "Recorded failure — exit 1" 13/600 in failure color + mono command + capture note; below it, truth row proving origin stays teal: "a failure is still high-confidence recorded evidence — red marks the outcome, teal marks the origin".
5. **Recorded run** details: run_group, scenario · mode, started/ended (mono full timestamps), duration (mono 600).
6. **Evidence refs** — collapsible: chevron + mono "evidence refs" + count pill; rows = `--row-bg` radius-7, mono 11.5px, copy icon.
7. **Raw payload** — collapsed by default, explicitly secondary: chevron + "raw payload" + "developer · 12 lines JSON" caption + copy button; one-line mono preview in an `--n1` box.

### 3. Validation Runway (1j)

Full E3 panel (left:96, top:132, right:36, bottom:36), padding 24/28. Header: "Validation runway" 19/600 + mono meta "7 runs · 14 invocations · 42 artifacts · 2026-06-06 23:31 → 06-07 05:17 UTC" + right note "selection is shared with the graph". Header-right scale toggle: segmented pill **sequence** (active, ink chip) | time.
Lanes (hairline-separated rows, 110px label gutter: overline lane name + mono count): 
- **runs**: 7 chips in a 7-col grid — chip = radius 10, source dot + "#n" 12/600 + check, mono 10.5 "23:31 · 5.4s"; selected chip = 2px border + halo; others 1.25px @50% border.
- **invocations**: run #1 expanded into 2 stacked chips (`cmd:0 ✓`, `cmd:1 ✓`, terminal icon); other columns dashed "×2" capsules.
- **artifacts**: per-column count pills (file icon + mono "6").
- **cache** and **failures**: empty lanes render one full-width 1.25px-dashed row: dashed-circle glyph + "no cache events recorded in this projection" / "no failures recorded — 14 of 14 commands completed" (11.5px faint). Empty lanes state their emptiness — never blank.
- Bottom axis row: mono 10.5 faintest tick labels (`23:31 23:32 00:24 02:04 02:51 03:55 05:17`).

### 4. Proof Packet (1e light / 1f dark / 1o remaining blocks) — flagship

Right drawer 560px, E3, radius 16 (right:16, top:112, bottom:16), three zones:
**A. Header** (padding 20/24, hairline bottom): overline "PROOF PACKET" + right "Export JSON" bordered button (download icon) + close; "canvas-dev" 26/650 + mono "7 blocks · generated 2026-06-07 05:17 UTC"; rollup pills ("● 3 recorded" teal tint pill, "◌ 4 not yet collected" slate tint pill, plain "0 computed · 0 simulated"); 6-col summary grid of `--n1` stat cells (mono 16/600 over 11px caption: runs 7, artifacts 42, actions 0, targets 0, cache ev. 0, failures 0).
**B. Block index** (the scannable TOC; padding 14/24): overline "BLOCKS"; one row per block: source glyph (16px slot) + title (12.5/600 ink for asserting blocks; 12.5/500 muted for future blocks) + right meta (mono count like "14 cmds"/"42 artifacts", or "no claim" faint, or "5 unsupported" failure-tint pill) + confidence meter or `?` + chevron. Active block row = collectable tint bg. Rows hover + scroll-jump to their card.
**C. Cards** (scroll region, 14px gap, padding 16/24): every card same rhythm —
`header row (glyph · title 14/600 · [chips] · meter · redaction) → summary 13px → metrics → claims → [unsupported] → refs`.
- **Asserting card** (Proof Scope, Invocation Results, Artifact Chain): E1 card, radius 14, padding 16/18. Metrics = `--n1` stat cells (mono 17/600 + 11px caption). Claims = 12.5px rows with 5px square teal bullets; negative claims bold the "not" ("Does **not** claim remote worker assignment…").
- **Future card** (Cache Evidence, Cache Economics, Remote Execution Boundary, Validation Surface): 1.25px **dashed** border, 60% bg opacity, dashed source glyph, muted title, "no claim recorded" dashed pill, hollow meter + `?`, dashed stat cells with muted values (`n/a`, `0`).
- **Evidence refs** (every card): collapsible footer — chevron + mono "evidence refs" + count pill. Expanded: rows = `--row-bg` radius-7, mono 11.5, middle-truncated (`run:run_4d3e7b3a82e1…bccbdd16b5e`), copy icon; then "show 6 more…" teal 11.5/600. Collapsed default for >0 counts except the active block.
- **Remote Execution Boundary card** additionally: bolded summary line, 2 requirement claims, unsupported-claims chip set (worker identity, action placement, queue time, scheduler assignment, load distribution).
- **Cache Economics** (1o): per-leg list — 7 rows `--row-bg`: mono index `#1`, "canvas-build", mono duration `5.36s`, mono faint `0/0`; caption "hits / misses per leg — none recorded".
- Scroll fade at drawer bottom + pill "▾ 3 more blocks — Cache Economics · Validation Surface · Artifact Chain".
Behind the drawer the graph dims to 35–40% opacity; proof lens active in rail.

### 5. Remote Boundary (1h)

Centered E3 panel 780px (top:150), padding 32/36:
- Lead: 52px dashed-circle globe emblem + overline "REMOTE EXECUTION BOUNDARY · DERIVED JOIN" + statement 26/650 "No remote execution was observed in recorded invocations." + 13px explainer ("This is a stated boundary, not a failure… Nothing beyond this line is claimed.").
- 3×2 grid of **dashed** metric cells (1.25px dashed hairline, radius 12): mono 20/600 `0` × 3 (remote invocations / executor endpoints / executor overrides) and dashed-glyph + mono "not observed" × 3 (worker identity / scheduler assignment / queue time). Slate, never red.
- "WHAT WOULD EARN THESE CLAIMS" overline + 2 bullets (`--remote_executor` invocation; worker log/admin evidence).
- Divider, then unsupported-claims chips + a truth footer row: dashed glyph `future` + hollow meter `? unknown` + "this block asserts nothing it cannot prove".

### 6. Compare Runs (1i)

Banner re-toned derived amber: "**canvas-dev ↔ agent-bugfix-1** — `derived_v1` compare projection · 4 dimensions". Header-right: two run-group pills separated by an arrow-swap icon ("canvas-dev · 6 runs", "agent-bugfix-1 · 2 runs").
- Row of 3 dimension cards (E1, radius 14): header = **derived diamond** + title 14/600 + medium meter (2 bars). Body = left value / delta pill / right value: Run Counts (mono 22/600 `6` vs `2`, pill `Δ −4`), Cache Metrics (`0 / 0` hits/misses each, `Δ 0`), Worker Identity (dashed "not observed" both, pill "match"). 12px caption each ("Derived from proof-packet cache blocks only — no fleet-wide claim.").
- **Agent Provenance** full-width card: header + "differs · +2 blocks" amber pill + medium meter. Two-column body: LEFT = dashed empty box — "No agent receipts recorded", "0 agent_provenance blocks in this packet — stated, not padded"; RIGHT = "AGENT-BUGFIX-1 · 2 RECEIPTS" with two receipt rows (`--row-bg`): verified badge + mono model `claude-sonnet-4-5` + mono truncated `response:…` hash.
- **Honest empty state** (when `compare-projection.json` absent — shown as inset): 480px dashed card — dashed glyph + "No comparison is bound" 13/600 + "Place `compare-projection.json` in `public/projections/`… NLFR never fabricates a comparison." + teal link "Open Composer to bind run groups →".

### 7. Composer drawer (1k) — fixes the undefined-CSS-var bug by construction

Header gains an active "Composer" ink button (pencil icon). Drawer 500px right, E3. Sections:
1. **View template** — fully tokened listbox (1px control border, radius 10): selected row = teal tint + 4.5px-ring radio + name 12.5/600 + 11px descriptor ("NLFR Default Canvas — graph + summary + legend"); others hover rows (Two-Act Spark — failure → fix narrative; Proof review; Runway focus; Compare acts). *(Template names beyond the first two are placeholders — use the real registry.)*
2. **Run group** — selectable pills: active = 1.5px teal border + tint; each shows dot + name + mono run count.
3. **Panels · 5** + "+ add panel" teal action: rows (`--row-bg`, radius 8) with grip-dots icon, name 12.5/500, mono descriptor, 28×16 toggle (teal on / `--n3` off; off rows at 60% opacity).
4. **Validation** (live): warning box in fallback tint (triangle-alert icon, 11.5px: "Compare panel is off but `compare-projection.json` is absent — enabling it will render the honest empty state.") + ok row (teal check, "spec valid · 4 panels active · 0 errors").
5. **Live preview** — 170×104 wireframe thumbnail of the composed shell (banner/header/rail/nodes/legend/command bar as tinted blocks), caption "updates as you edit". Re-renders on every edit via the existing view-spec engine.
6. Footer: primary ink button "Persist locally" (save icon) + bordered "Export JSON" + right caption "view spec is URL-encoded · never evidence". Both button labels `white-space: nowrap`.

### 8. Operator command palette (1l)

`⌘K` (and clicking the bar) opens a centered modal 520px over scrim `rgba(13,32,38,0.28)`: E3, radius 16. Input row (search icon, 14px text, teal caret, `esc` keycap). Grouped results with overline headers — **FOCUS — FILTERS THE LOADED PROJECTION** (`focus failures` — "isolate failing actions on the graph", `focus cache misses`, `agent loop`), **LENSES** (`proof`, `runway`, `remote`, `compare`), **CANVAS** (`reset` — "clear focus, fit graph, keep selection"). Row = 26px icon plate + name 12.5/600 (typed substring highlighted with teal-tint mark) + 11px description + `↵` on active row (teal-tint bg). Footer bar (`--row-bg`): info icon + "Commands filter and navigate the loaded projection only — never persisted, never exported as evidence."
Fuzzy match on the ~8 keywords; empty query lists everything (that IS the discoverability).

### 9. System states (1l)

- **Loading** (`role="status"`): 16px spinner (2px ring, teal top) + "Loading `action-graph.json`…" + skeleton bars.
- **Error** (`role="alert"`): failure-tint box: alert icon + "Projection failed to parse" 12.5/600 + detail "`proof.json` line 214 — invalid JSON. Nothing partial is rendered."
- **Honest fallback banner**: fallback tint: derived diamond + "Using fixture fallback" 600 + "`runway.json` is absent — showing the bundled `simulated_v1` fixture, labeled as such."
- **Redacted values**: lock chips as specced above (`[REDACTED:abs_path]/bazel-test.log`, `${HOME}/workspace`); blocked = solid chip "blocked · github_token".
- **Resting / no selection**: centered 36px muted graph-icon plate + "Select any node to open its evidence dossier" 12px faint.
- **Focus applied**: dismissible ink pill "focus: failures ✕" + "0 of 70 nodes match" — an empty match says so; the graph never silently hides evidence.

### Mobile 390w (1m)

Compact banner (30px, truncating); 52px header (logo square, "NLFR", "Default ▾" picker, hamburger); lens switcher becomes a horizontal chip row under the header (active = ink pill with icon); zoom buttons float top-right (34px); graph nodes at full desktop sizing (≥44px touch targets). Bottom sheet (E3, top-radius 18, grab handle): collapsed row = the four source glyphs + "Truth legend" + chevron-up (expands to the full legend) + primary "Commands" ink pill (opens the palette full-screen); below, one-line summary "7 runs · 70 nodes · 0 failures · remote execution not observed". The legend is reachable on mobile — do not hide it.

---

## Interactions & Behavior

- Lens switching is local UI state; never mutates data. Selection is shared across graph/runway/inspector and resets sensibly on lens change. Routing reflects lens + selection.
- Graph: d3-zoom pan/zoom/fit; zoom % + "N / N shown" readout always visible. Clusters expand/collapse on click (animate ~200ms ease-out). Level-of-detail: below ~60% zoom, node meta rows hide and labels condense; capsules stay labeled.
- Collapsible evidence-ref lists everywhere: show count pill collapsed; expand shows first 3 + "show N more…"; every ref row has copy-to-clipboard.
- Tooltips: every truth glyph/meter/chip carries a tooltip naming the raw enum (`source_kind: collectable_v1 — …`). Use a styled tooltip component (the mocks use native `title` as a stand-in).
- Hovers: rows use the 4–5% ink wash (`rgba(13,32,38,0.05)` / `rgba(234,242,242,0.06)`); ref rows step `--row-bg` → `--n1`/`--n2`. No transform/scale hovers.
- Theme toggle in header; persist choice (`data-theme` attribute + localStorage), default to `prefers-color-scheme`.
- Transitions: 150–200ms ease-out on drawer slide-in, palette fade/scale, cluster expand. No decorative animation.
- Legend: `⌘L` toggles; hover rows highlight matching nodes on the graph (optional enhancement).

## State Management

- `lens` (graph | runway | proof | remote | compare), `selection` (node id | null), `focus` (command filter | null), `theme`, `groupBy`/`detail` for the graph, expanded-set for clusters/refs/blocks, composer draft spec.
- Command palette parses typed intent → sets `focus`/`lens`; ephemeral, never serialized into exports.
- Composer edits a view-spec object; live preview renders it; "Persist locally" writes URL-encoded spec (existing mechanism); it is never part of any projection/export.
- Data: fetch static JSON from `public/projections/` once per lens need; load-order preference for the run-group picker unchanged (compact index → history → pairwise fallback). Deterministic render — same projection, same output (screenshot + truth-guard tests must keep passing).

## Non-negotiable invariants (enforced by `npm run test:truth`)

1. All four truth labels rendered/rolled up everywhere; 2. no styling that makes `simulated_v1`/`future` read as `collectable_v1` (dashed geometry is the guarantee); 3. only recorded projection fields on screen; 4. unsupported claims explicit; 5. redacted values rendered honestly; 6. missing optional data → honest empty states; 7. operator bar non-evidentiary; 8. static projections only.

## Assets

None external. All icons are lucide (stroke 2, sizes 9–19px as noted); the wordmark glyph is a simple crosshair-node in a rounded square (recreate as a tiny inline SVG). Fonts are system stacks — ship nothing.

## Files

- `NLFR Redesign.dc.html` — the full 15-board hi-fi canvas (open in a browser; boards labeled 1a–1o). This is the visual source of truth.
- `tokens.css` — reference token implementation (light `:root` + `[data-theme="dark"]`), matching every value in this README.
