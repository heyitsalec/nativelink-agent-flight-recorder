# NLFR walkthrough

← [Docs index](INDEX.md) · [Wiki hub](wiki/README.md)

**Quadrant:** Tutorial · **Audience:** evaluators learning the system shape.

This is the guided tour for understanding the NativeLink Agent Flight Recorder
(NLFR) as it exists today. Read it with the repo open. The goal is to move from
the product idea to the concrete files, commands, screenshots, and proof
artifacts that make the MVP work.

If you only read one path, follow this order:

1. This file for the system shape and demo flow.
2. [`IMPLEMENTATION_WALKTHROUGH.md`](internal/IMPLEMENTATION_WALKTHROUGH.md) for the
   file-by-file code tour.
3. [`USEFULNESS_ROADMAP.md`](USEFULNESS_ROADMAP.md) for what is needed to make
   NLFR useful beyond the demo.

## What NLFR is

NLFR is a local-first black-box recorder for agent validation loops. It does
not try to become a CI system, dashboard, tracing stack, or SaaS product in the
MVP. It records evidence from a Bazel/NativeLink validation path, normalizes it
into SQLite, exports truth-labeled projection JSON, and renders a sparse canvas
from that projection only.

The short thesis from [`ONE_PAGER.md`](ONE_PAGER.md):

> When AI writes the code, NativeLink makes validating it fast, and NLFR makes
> validating it trustworthy.

The repo rule that matters most:

> Build an evidence-first recorder, not a UI-first dashboard.

That means every node, edge, metric, and proof claim needs truth labels:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, or `future`.
- `confidence`: `high`, `medium`, `low`, or `unknown`.
- `evidence_refs`: artifact or fixture references backing the claim.
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`.

## Default canvas projection (M6) — no contradiction

Two projections serve different evaluator intents:

| Projection | Location | `source_kind` | Purpose |
|------------|----------|---------------|---------|
| **canvas-dev** (default) | `apps/canvas/public/projections/` | `collectable_v1` | Dogfood record of NLFR building its GUI (`record-canvas-build.sh`) |
| **Demo fixtures** | `data/demo-proof/projections/` after `verify-demo.sh` | `simulated_v1` | Agent-loop teaching shape; not committed as default |

The dev/preview server loads **`canvas-dev`** by default. Green banner =
`collectable_v1` dogfood. `verify-demo.sh` does **not** overwrite committed
`apps/canvas/public/projections/`.

If projections fail to load, the canvas shows a **fixture fallback banner**
(`usingFixtureFallback` in `App.tsx`) and uses committed demo fixtures — honest
`simulated_v1`, not fake live proof.

**Screenshots below** (`docs/images/canvas-*.png`) are captured from the
committed **canvas-dev** `collectable_v1` dogfood projection — the real record of
NLFR building its own canvas (`record-canvas-build.sh`). What you see here is what
preview loads by default; the banner reads
`canvas-dev run group — collectable_v1 projection · 70 nodes`. These are the
redesigned (v2) canvas, so every truth label is a grayscale-safe **shape + hue**
glyph, not a color-only dot.

## The current app in pictures

These screenshots render the committed `canvas-dev` `collectable_v1` projection —
real recorded build evidence, not invented backend state. The redesigned canvas is
an instrument panel: a density Action Graph, four rail lenses over it, a
grayscale-safe truth legend, a composer + command palette, first-class dark mode,
and a first-class mobile layout. The real proof summaries live in
[`proof-samples/`](proof-samples/), and the real scripts write under ignored
`data/`.

### Action Graph

![Action Graph canvas rendered from the canvas-dev collectable_v1 projection](images/canvas-desktop.png)

This is the main canvas. Nodes are **cards** laid out by a deterministic density
model, grouped by run: the first `canvas-build` run is expanded into its recorded
invocations (`npm --prefix …`, `uv run pytest …`) and artifacts (`run.json`,
`outputs/…`), while the six later runs collapse into cluster cards
(`2 invocations · 6 artifacts`) so nothing is hidden and nothing is invented. The
honest readout (bottom-right) states the partition exactly —
`fit · 89% · 70 total · 11 cards · 59 in 9 clusters`. The evidence chain reads
left to right:

`change → run → invocation → artifact`

The **TRUTH LEGEND** (bottom-left) is the key to the whole surface. Truth is
encoded by **shape + hue**, so it survives grayscale and color-blindness — the
shape is the guarantee, the hue is a convenience:

- **● Recorded** — filled circle, `collectable_v1`: captured from real tool output.
- **◆ Computed** — diamond, `derived_v1`: computed from recorded artifacts.
- **▲ Simulated** — triangle, `simulated_v1`: a deterministic fixture.
- **○ Not yet collected** — dashed hollow circle, `future`: a claim not yet collected.

Below the glyphs the legend names the three secondary encodings a node can carry:
a **confidence** meter (bar height, never source-hued), a **redaction** lock chip
(surfaces real `[REDACTED:…]` paths, never a bare token), and a **provenance** trio
for agent receipts. The legend's visibility is a panel toggle — open the
**Composer** drawer and toggle the truth-legend panel (`show_truth_legend`) to
hide or show it. In the `canvas-dev` dogfood every node is `collectable_v1`, so the
default graph is all filled-circle Recorded evidence; simulated/future glyphs appear
in the fixture views (e.g. `?view=two-act-spark`).

### Agent-loop focus

![Agent-loop focus rendered from the canvas-dev projection](images/canvas-agent-loop.png)

The operator bar at the bottom drives focus and jumps. Type `agent loop` (or open
the **⌘K command palette** and pick it) to isolate agent and change provenance on
the graph without leaving the projection. The bar labels itself honestly —
`local filter · not evidence` — because focusing is a view operation, never a new
claim.

Important honesty point: this is not a live LLM call. An agent scenario carries a
`model` label and `prompt_sha256`, but the raw prompt is never stored and no
tokens are spent. Contrast with M8 `record-agent-change.sh` and tier1-live-bazel
samples (`collectable_v1` agent leg).

### Proof Packet

![Proof Packet drawer rendered from the canvas-dev proof projection](images/canvas-proof.png)

The Proof Packet lens answers "what can we actually claim?" It opens as a drawer
with a block index and a rollup that counts blocks by source kind
(`3 recorded · 4 not yet collected · 0 computed · 0 simulated`), so an
un-collected claim is stated as such, never quietly dropped. Each block — Proof
Scope, Invocation Results, Cache Evidence, Cache Economics, Remote Execution
Boundary, Validation Surface, Artifact Chain — carries its own glyph, confidence,
evidence refs, and any unsupported claims (`5 unsupported` on the remote block).
**Export JSON** downloads the packet verbatim. Future blocks read `no claim`
rather than a fabricated value.

### Remote Boundary

![Remote Boundary lens showing gated worker claims](images/canvas-remote-boundary.png)

The Remote Boundary lens is intentionally conservative. It states what was
observed and encodes every count and flag as a neutral, dashed "not observed" —
never red, never a fabricated fleet metric. It can show when a recorded Bazel
invocation was configured with remote execution or when a proof script observed
worker endpoints. **Worker identity** is **conditional** (M7): promoted to
`collectable_v1` when admin stdout is attached pre-ingest and the M7 regex
matches — see `worker-evidence-proof.sh`. Scheduler assignment, queue time,
action placement, and load distribution stay unsupported without direct evidence.

### Failure focus

![Failure focus view rendered from the canvas-dev projection](images/canvas-failure-focus.png)

Type `failures` (or use the ⌘K palette) to isolate failure nodes and open the
evidence inspector. The point is not to hide failed validation; it is to make
failed proof inspectable and labeled. Red is rationed to genuine recorded
failures only — the `canvas-dev` dogfood records `0 failures`, so this focus
honestly reports `0 of 70 nodes match` rather than inventing one.

### Mobile shape

![Mobile canvas — the 390-wide responsive layout](images/canvas-mobile.png)

Mobile is now a **first-class 390-wide layout**, not an afterthought. The vertical
tool rail becomes a horizontal **lens chip row** (Graph / Runway / Proof / Remote /
Compare); zoom floats top-right; the truth legend and operator command move into a
bottom **sheet** whose "Commands" pill opens the full-screen ⌘K palette. The graph
anchors on real populated cards at a legible, pannable zoom with ≥44px touch
targets, and the honest count readout stays on screen. It is the same recorded
projection and the same grayscale-safe truth labels — nothing is dropped to fit
the small screen.

### Composer and command palette

<video controls src="images/canvas-operator-flow.webm" width="900"></video>

The operator surface is two complementary things: the always-present operator
command input (type `proof`, `failures`, `agent loop`, `reset`, …) and the **⌘K
command palette** for the same commands by fuzzy search. The **Composer** button
in the header opens a drawer to recompose the view — pick a template, toggle
panels, bind run groups — and export the resulting view-spec JSON, labeled "never
evidence" because composing a view is not a claim. If your Markdown renderer does
not play WebM inline, open
[`images/canvas-operator-flow.webm`](images/canvas-operator-flow.webm).

To regenerate these assets from a running canvas preview server:

```bash
npm --prefix apps/canvas run build
npm --prefix apps/canvas run preview -- --host 127.0.0.1   # 127.0.0.1:5174
CANVAS_URL=http://127.0.0.1:5174/ npm --prefix apps/canvas run capture
cp output/playwright/canvas-*.png docs/images/
cp output/playwright/canvas-operator-flow.webm docs/images/
npm --prefix apps/canvas run capture:tour                  # docs/media/nlfr-canvas-tour.gif
```

The committed files in `docs/images/` are the walkthrough copies. Fresh captures
land in ignored `output/playwright/` first.

## M7 — Worker identity (landed)

M7 promotes **one** fleet claim when direct stdout evidence exists.

| Piece | Path |
|-------|------|
| Parser | `src/nlfr/ingest/worker_admin_stdout.py` |
| Proof script | `scripts/worker-evidence-proof.sh` |
| Output | `data/worker-evidence-proof/summary.json` (`worker_identity_observed`) |
| Fleet stdout attach | `scripts/local-exec-proof.sh` (live path) |

Default proof mode is **fixture-replay** (no Nix required). Live path chains
`local-exec-proof.sh` when `nativelink` and Bazel are on PATH.

```bash
./scripts/worker-evidence-proof.sh
# fixture: NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 (implicit when tools absent)
```

Deep dive: [Wiki § M7](wiki/README.md#frontier-tracks-pointers) · [`dags/m7-worker-parser.md`](dags/m7-worker-parser.md)

**Claim boundary:** regex match on attached stdout only — not scheduler, queue, or placement.

## M8 — Real agent adapter (landed)

Thin Cursor adapter records **`model` + `prompt_sha256`** — never raw prompts.

| Piece | Path |
|-------|------|
| Recorder | `scripts/record-agent-change.sh` |
| Docs | [`adapters/cursor/README.md`](../adapters/cursor/README.md) |
| Live Bazel acts | `scripts/tier1-live-bazel-proof.sh` → `agent-bugfix-summary.json`, `agent-feature-summary.json` |

```bash
./scripts/record-agent-change.sh --change-path README.md --model composer-2.5 \
  --prompt-file /tmp/prompt.txt --dry-run
```

`agent-loop-proof.sh` still uses a **simulated_v1** bounded patch on the agent
leg; tier1-live-bazel proves the **collectable_v1** adapter path with
`bazel_validated: true`.

Deep dive: [Wiki § M8](wiki/README.md#frontier-tracks-pointers) · [`dags/m8-agent-adapter.md`](dags/m8-agent-adapter.md)

## M9 — Multi-run compare (landed)

Compare is **`derived_v1`** — diffs across run groups, no worker correlation.

| Piece | Path |
|-------|------|
| CLI | `nlfr compare export`, `nlfr compare index` |
| Projector | `src/nlfr/projectors/compare.py` |
| Proof script | `scripts/compare-proof.sh` |
| Canvas | Compare Runs lens (`compare-projection.json`) |

```bash
PYTHONPATH=src uv run python -m nlfr compare index --db data/record-proof/nlfr.sqlite --json
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/record-proof/nlfr.sqlite \
  --right-db data/canvas-dev/nlfr.sqlite \
  --left record-proof --right canvas-dev \
  --output data/compare-proof/projections/compare-projection.json
./scripts/compare-proof.sh
```

Deep dive: [Export and compare run groups](wiki/how-to/export-and-compare-run-groups.md) · [`dags/m9-multi-run-compare.md`](dags/m9-multi-run-compare.md)

## LRE proof ladder (high level)

Local Remote Execution proofs advance in phases. Each phase has a script and
optional CI job — see [`CI_RECIPE.md`](CI_RECIPE.md). GHA may be offline; run
locally inside `nix develop`.

| Phase | Claim ceiling | Script | CI job |
|-------|---------------|--------|--------|
| 1 | `lre_substrate_ready` | `lre-proof.sh` | `lre-proof-probe` |
| 2 | `lre_bazelrc_generated` | `lre-nix-toolchain-proof.sh` | `lre-nix-ci` |
| 4 | `lre_cache_parity_observed` | `lre-cold-warm-proof.sh` | `lre-cold-warm-ci` |

Phase 4 expects x86_64-linux + generated `lre.bazelrc` + `demo/nativelink/lre.json5`
+ Bazel `--config=lre`. Darwin and missing toolchain produce honest
`environment-blocker.json` samples in [`proof-samples/`](proof-samples/).

Deep dive: [Wiki § LRE](wiki/README.md#frontier-tracks-pointers)

**Unsupported:** hermetic container-image parity, fleet dashboards, queue/action correlation.

## How someone uses the demo today

There are two evaluator paths.

### Path A: fixture-backed canvas, no Nix

Use this when the evaluator wants to understand the interface quickly.

```bash
uv sync
npm --prefix apps/canvas install
uv run pytest tests -q
scripts/verify-demo.sh
npm --prefix apps/canvas run preview -- --host 127.0.0.1
```

Then open the Vite URL and drive the operator bar:

- `agent loop` highlights agent/change provenance.
- `proof` opens the proof packet.
- `remote` opens the remote boundary lens.
- `failures` isolates failure evidence.
- `cache` highlights cache events.
- `reset` returns to the full graph.

What this path proves:

- The backend tests pass.
- Fixture evidence can be ingested and projected.
- The canvas can render projection JSON.
- Committed **canvas-dev** default is `collectable_v1` dogfood.

What this path does not prove:

- Live NativeLink cache behavior.
- Live remote execution worker behavior (beyond fixture shapes).
- Live LLM agent behavior.

### Path B: real Nix proof path

Use this when the evaluator is a skeptic and wants to re-run evidence.

```bash
nix develop
scripts/cold-warm-cache-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w \
  scripts/local-exec-proof.sh
scripts/worker-evidence-proof.sh
scripts/agent-loop-proof.sh
./scripts/tier1-live-bazel-proof.sh   # optional Acts 1+2
```

The scripts write summaries and projections under ignored `data/`. Redacted
copies of representative summaries are committed in
[`proof-samples/`](proof-samples/).

What this path proves today:

- Cold/warm NativeLink cache behavior can be recorded from real tool output.
- A warm cache leg recorded higher hit rate and lower duration in the current
  proof sample.
- Two local worker endpoints can be configured and observed live.
- Worker identity when M7 stdout is attached (`worker-evidence-proof.sh`).
- A deterministic bounded-agent patch can be linked to validation/cache evidence
  through the action graph.
- Tier1 acts with live Bazel when `tier1-live-bazel-proof.sh` completes.

What remains explicitly unproven:

- Scheduler assignment, queue time, action placement, load distribution.
- Multi-machine fleet behavior.
- Production AI-agent identity/auth beyond M8 bounded fields.
- Worker identity **without** attached admin stdout matching M7 regex.

## The system architecture

The core architecture is a one-way evidence pipeline:

```text
Bazel / NativeLink / scenario
  -> immutable artifacts with SHA-256 hashes
  -> SQLite evidence spine
  -> projection JSON
  -> canvas and proof docs
```

The UI is last on purpose. The canvas does not query Bazel, NativeLink, logs, or
an API at runtime. It reads projection JSON from `apps/canvas/public/projections/`.

### Layer 0: commands

The CLI starts at `src/nlfr/cli.py` and registers subcommands through
`src/nlfr/commands/__init__.py`.

The commands you will use most:

- `nlfr doctor`: environment readiness.
- `nlfr run`: run Bazel/NativeLink and record process artifacts.
- `nlfr ingest`: parse Bazel evidence into SQLite.
- `nlfr graph export`: export Action Graph JSON.
- `nlfr proof export`: export Proof Packet JSON.
- `nlfr runway export`: export Validation Runway JSON.
- `nlfr compare export` / `compare index`: M9 multi-run compare (`derived_v1`).
- `nlfr simulate`: apply deterministic agent patch scenarios and record
  provenance.

### Layer 1: artifact capture

`src/nlfr/artifacts.py` owns immutable artifact writes. It hashes bytes with
SHA-256, writes each artifact once, and appends `artifact_manifest.json`.

This is the "do not trust memory" layer. If a proof refers to a file, that file
has a manifest entry, hash, size, producer command, redaction state, source kind,
confidence, and evidence refs.

### Layer 2: SQLite evidence spine

`src/nlfr/db/schema.py` defines the core tables:

- `runs`
- `changes`
- `invocations`
- `artifacts`
- `targets`
- `actions`
- `cache_events`
- `failures`
- `graph_nodes`
- `graph_edges`
- `proof_blocks`

All core rows carry the truth-label columns. This is what prevents the UI from
accidentally implying a stronger claim than the recorder captured.

### Layer 3: ingest

`src/nlfr/ingest/bazel.py` parses compact Bazel evidence:

- BEP JSON/JSONL into targets, actions, and failures.
- Execution log JSON into cache events.
- Bazel profile JSON into derived cache observations.

`src/nlfr/ingest/worker_admin_stdout.py` (M7) parses admin stdout for conditional
`worker_identity` promotion.

`src/nlfr/ingest/sqlite.py` inserts parsed evidence into the schema with stable
keys so ingest is idempotent.

### Layer 4: projectors

Projectors read SQLite and export versioned JSON:

- `src/nlfr/projectors/graph.py` creates nodes and edges for the Action Graph.
- `src/nlfr/projectors/proof.py` creates proof blocks and cache economics.
- `src/nlfr/projectors/runway.py` creates a simplified validation sequence.
- `src/nlfr/projectors/compare.py` creates M9 compare projection (`derived_v1`).
- `src/nlfr/projectors/remote_execution.py` sanitizes and gates remote-execution
  claims.

This layer is where truth labels become visible product behavior.

### Layer 5: canvas

The canvas is in `apps/canvas/src/`. The central file is `App.tsx`.

It fetches:

- `/projections/action-graph.json`
- `/projections/proof.json`
- `/projections/compare-projection.json` (optional — Compare Runs lens)

Then it renders:

- Action Graph nodes and edges (density model, grouped by run).
- Proof Packet drawer.
- Remote Boundary lens.
- Compare Runs lens (M9).
- Validation Runway lens.
- Operator command input and the ⌘K command palette.
- Composer drawer (view-spec recompose + export).
- Truth-label legend (grayscale-safe shape + hue glyphs).

The layout is deterministic (`layout.ts`) and the types are explicit
(`types.ts`).

## Walk the repo in this order

Start here:

1. `AGENTS.md` for product and engineering rules.
2. `README.md` for the quick-start and current proof paths.
3. `docs/ONE_PAGER.md` for the shortest product framing.
4. `docs/DEMO_SCRIPT.md` for the rehearsal path.
5. `docs/proof-samples/README.md` and the JSON samples.
6. [Wiki hub](wiki/README.md) for Diátaxis deep links.

Then trace the backend:

1. `src/nlfr/cli.py`
2. `src/nlfr/commands/run_cmd.py`
3. `src/nlfr/artifacts.py`
4. `src/nlfr/db/schema.py`
5. `src/nlfr/commands/ingest_cmd.py`
6. `src/nlfr/ingest/bazel.py`
7. `src/nlfr/ingest/worker_admin_stdout.py`
8. `src/nlfr/ingest/sqlite.py`
9. `src/nlfr/projectors/graph.py`
10. `src/nlfr/projectors/proof.py`
11. `src/nlfr/projectors/compare.py`
12. `src/nlfr/commands/simulate_cmd.py`
13. `src/nlfr/commands/compare_cmd.py`

Then trace the UI:

1. `apps/canvas/public/projections/action-graph.json`
2. `apps/canvas/public/projections/proof.json`
3. `apps/canvas/src/types.ts`
4. `apps/canvas/src/layout.ts`
5. `apps/canvas/src/App.tsx`
6. `apps/canvas/src/styles.css`
7. `apps/canvas/scripts/capture-proof.mjs`

Then trace the proofs:

1. `scripts/verify-demo.sh`
2. `scripts/cold-warm-cache-proof.sh`
3. `scripts/local-exec-proof.sh`
4. `scripts/worker-evidence-proof.sh`
5. `scripts/agent-loop-proof.sh`
6. `scripts/compare-proof.sh`
7. `scripts/tier1-live-bazel-proof.sh`
8. `scripts/lre-proof.sh` (LRE phase 1)

Finally read the tests:

1. `tests/test_cli.py`
2. `tests/test_ingest_bazel.py`
3. `tests/test_projectors.py`
4. `tests/test_simulate_cmd.py`
5. `tests/test_compare.py`
6. `tests/test_worker_admin_stdout.py`
7. `tests/test_artifacts.py`

## The key mental model

NLFR is not trying to say "the build is good" or "the agent was smart."

It is trying to say:

1. Here is exactly what ran.
2. Here are the artifacts we captured.
3. Here are their hashes.
4. Here is what we parsed into SQLite.
5. Here is the projection JSON.
6. Here is what the canvas can show.
7. Here are the claims we still cannot make.

That last item is not a weakness of the demo. It is the product's differentiator.

## Where the MVP stops

The MVP is now credible as a local proof kit. It is not yet "actually useful" as
a day-to-day platform tool for a team. The largest missing pieces are covered in
[`USEFULNESS_ROADMAP.md`](USEFULNESS_ROADMAP.md), but the short version is:

- Package the reference architecture so another repo can adopt it quickly.
- Multi-run history and comparison are **landed** (M9) — retention is index-only.
- Make proof exports easy to attach to PRs or CI artifacts.
- Preserve the evidence spine while improving operator ergonomics.
- Do not build SaaS/auth/billing or a worker dashboard before direct evidence
  exists for the claims those surfaces would imply.

← [Docs index](INDEX.md)
