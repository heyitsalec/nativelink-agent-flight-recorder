# NLFR demo script

Rehearsal paths for showing the Agent Flight Recorder. Every step is backed by
recorded evidence — nothing here narrates ahead of proof.

| Tier | Time | Audience | Doc section |
|------|------|----------|-------------|
| **Tier 1** | ~5 min | Quick evaluator | Steps 1–3 |
| **Tier 2** | ~15 min | **NativeLink team** (recommended) | [Tier 2 — NativeLink team](#tier-2--nativelink-team-15-min-recommended) |
| **Tier 3** | ~30 min | Skeptics wanting live Nix exit codes | Steps 4–5 |

---

## Before you start

```bash
uv sync
npm --prefix apps/canvas install
```

**Mandatory narration rule:** say the `source_kind` aloud whenever you open a lens
or JSON file — `collectable_v1`, `simulated_v1`, `derived_v1`, or `future`.

Talking point: "This is a local-first black-box recorder. The canvas only ever
renders recorded facts — it never invents backend state. Watch the truth labels."

---

## Tier 2 — NativeLink team (15 min, recommended)

**Presenter profile:** TypeScript-strong; no Rust required.  
**Prep (day before):** `npm --prefix apps/canvas run preview` smoke test on
`127.0.0.1:5174`; open `docs/proof-samples/` tabs; skim ONE_PAGER "explicitly
unproven" list; confirm committed projections are `canvas-dev` `collectable_v1`
(`./scripts/record-canvas-build.sh` if unsure).

| Time | Segment | Action | Say aloud |
|------|---------|--------|-----------|
| 0:00–0:30 | Thesis | README north star or one slide | "When AI writes the code, NativeLink makes validating it fast; NLFR makes validating it trustworthy." |
| 0:30–1:30 | Dual heroes | `docs/media/nlfr-canvas-tour.gif` + `nlfr-evidence-loop.gif` | "Surface vs spine. Evidence-loop GIF is a curated replay — not a live shell recording." |
| 1:30–5:30 | Live canvas | `npm --prefix apps/canvas run preview` | Banner: **canvas-dev collectable_v1**. Five-lens rail: Action Graph → Validation Runway → Proof Packet → Remote Boundary → Compare Runs. Truth legend bottom-left (shape+hue glyphs + confidence / redaction / provenance rows). Toggle dark mode; the ⌘K palette runs the same commands. |
| 5:30–8:30 | Evidence spine | Terminal walkthrough (below) | Point at `source_kind` and `evidence_refs` in exported JSON. |
| 8:30–11:30 | Real proof samples | Open `docs/proof-samples/cold-warm-summary.json`, `two-worker-summary.json`, `agent-loop-summary.json` | Cold/warm: **collectable_v1**. Two-worker: endpoints ready, **not** distributed work. Agent-loop: **mixed** labels. |
| 11:30–13:30 | Honesty slide | ONE_PAGER unsupported claims | Worker identity **conditional** (M7 stdout); queue time, scheduler assignment, action placement, fleet ops — unproven. Compare is **`derived_v1`** via `compare export` (M9 landed). |
| 13:30–14:30 | NativeLink fit | No Rust | "NLFR is a recorder around your stack — we don't patch NativeLink. We make cache/RBE outcomes auditable for agent loops." |
| 14:30–15:00 | Close | Offer Tier 3 | Invite live `nix develop` + cold-warm if they want exit codes. |

### Tier 2 — live canvas commands

```bash
npm --prefix apps/canvas run preview
# Open http://127.0.0.1:5174/
```

1. Confirm **canvas-dev collectable_v1** banner at top.
2. Click **Validation Runway** — recorded run / invocation / artifact lanes; empty lanes state their emptiness.
3. Click **Proof Packet** — block index + rollup; scroll unsupported claims.
4. Click **Remote Boundary** — worker claims gated ("not observed", never red).
5. Click **Compare Runs** (if `compare-projection.json` loaded) — **derived_v1** deltas only.
6. Point to **truth legend** — shape+hue glyphs (● recorded / ◆ computed / ▲ simulated / ○ not-yet-collected) plus confidence-meter, redaction lock-chip, and provenance rows. Toggle dark mode.

Default committed projection is **canvas-dev dogfood** (NLFR building its GUI),
not the agent-loop fixture. For agent-loop shape, use proof-samples JSON or
Tier 1 Step 3 fixture path.

### Tier 2 — evidence spine (terminal)

```bash
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario safe-leaf-change \
  --output-dir /tmp/nlfr-demo \
  --run-group demo-tier2 \
  --skip-run \
  --json

PYTHONPATH=src uv run python -m nlfr ingest \
  --database /tmp/nlfr-demo/nlfr.sqlite \
  --run-key simulation:safe-leaf-change:cache-only \
  --run-group demo-tier2 \
  --bep tests/fixtures/bazel/bep.jsonl \
  --execution-log tests/fixtures/bazel/execution-log.json \
  --profile tests/fixtures/bazel/profile.json \
  --source-kind simulated_v1

PYTHONPATH=src uv run python -m nlfr graph export \
  --db /tmp/nlfr-demo/nlfr.sqlite \
  --run-group demo-tier2 \
  --output /tmp/nlfr-demo/action-graph.json
```

Open `/tmp/nlfr-demo/action-graph.json` — show truth labels on nodes. **Say:**
"Canvas consumes this contract; it never calls NativeLink APIs at runtime."

### Tier 2 — fallback if canvas fails

Use hero GIFs + `docs/proof-samples/` only. Degrades gracefully; still lands the
trust story if you narrate labels.

### Tier 2 — cue cards (do not skip)

| If you show… | Must say… |
|--------------|-----------|
| Committed canvas (canvas-dev) | **collectable_v1** — real dogfood record |
| proof-samples cold-warm | **collectable_v1** — real Bazel through NativeLink cache |
| proof-samples two-worker | **collectable_v1** — endpoint readiness only, not distributed execution |
| proof-samples agent-loop | **Mixed** — validation leg collectable, agent/change simulated |
| proof-samples agent-bugfix / agent-feature | **collectable_v1** — live agent record, `bazel_validated: true` via `tier1-live-bazel-proof.sh` |
| Compare lens | **derived_v1** — diff across run groups, no worker correlation |
| Remote Boundary | Configured remote execution — worker identity conditional on M7 stdout; placement unproven |
| M7 worker evidence | **collectable_v1** when stdout regex matches — `./scripts/worker-evidence-proof.sh` |
| M9 compare export | **derived_v1** — `nlfr compare export`, not a shell stub |

---

## Tier 1 Agent Vision — "AI wrote it; here's proof" (~5 min)

Live Bazel proof: [How-to: tier1 live Bazel](wiki/how-to/run-tier1-live-bazel-demo.md)  
Proof samples: [`proof-samples/README.md`](proof-samples/README.md) —
`agent-bugfix-summary.json`, `agent-feature-summary.json`

```bash
# Primary path — Acts 1+2 with real Bazel (inside nix develop)
nix develop --command ./scripts/tier1-live-bazel-proof.sh
# → data/tier1-live-bazel/summary.json (collectable_v1, validation: bazel)
# → data/agent-bugfix-1/summary.json + data/agent-feature-compare/summary.json
#   (bazel_validated: true on each act summary)

# Fixture-backed gate (blocker smoke; optional live with NLFR_RUN_TIER1_LIVE_BAZEL=1)
uv run pytest tests/test_tier1_live_bazel.py -q

# Plan all three acts + compare triple (no SQLite writes)
./scripts/tier1-agent-demo.sh --dry-run --json

# Fallback — pytest-only validation (no Bazel on PATH)
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state broken --check   # expect fail
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state fixed
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --act 1
NLFR_SKIP_BAZEL=1 ./scripts/tier1-feature-setup.sh --state feature
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --act 2

# Act 3 — three-way compare narrative (derived_v1)
./scripts/compare-agent-runs.sh
./scripts/promote-tier1-compare.sh
```

**Say aloud:** Act 1+2 summaries are **`collectable_v1`** with
**`bazel_validated: true`** (`agent-bugfix-summary.json`,
`agent-feature-summary.json`). Agent leg is live **`cursor_adapter_v1`** — not the
**`simulated_v1`** bounded patch in `agent-loop-summary.json`. Compare lens is
**`derived_v1`** — no worker correlation.

**No Nix?** Open `docs/proof-samples/agent-bugfix-summary.json` and
`agent-feature-summary.json` — redacted excerpts from a real
`tier1-live-bazel-proof.sh` run. Point at `bazel_validated` and
`validation: bazel` in each file.

Canvas: `npm --prefix apps/canvas run preview` — `?view=tier1-demo` (Compare lens) or `?view=graph-only`.
Composer: click the **Composer** button in the header (or open the **⌘K** palette) for the view-spec recompose + export drawer.

---

## Step 1 — Doctor: the environment is honest (~30s)

```bash
PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json
```

Show: the JSON reports tool availability and an explicit `ok` flag. Outside Nix
it records a blocker instead of pretending. **Point:** the recorder tells the
truth about its own environment before it records anything.

## Step 2 — Backend tests are green (~30s)

```bash
uv run pytest tests -q
```

Show: the full suite passes. **Point:** projections, ingest idempotency, and
truth-labeling are all under test against real SQLite and fixture files.

## Step 3 — Canvas: default dogfood projection (~2 min)

```bash
npm --prefix apps/canvas run dev -- --host 127.0.0.1
```

Open the dev server. The committed default is **`canvas-dev` `collectable_v1`**
(dogfood record of NLFR building its canvas). Green banner confirms the label.

Drive the five-lens rail:

1. **Action Graph** — invocation / artifact / run cards, grouped by run, from the generic record.
2. **Validation Runway** — recorded run / invocation / artifact lanes; empty lanes state their emptiness honestly.
3. **Proof Packet** — block index + source-kind rollup; unsupported claims listed explicitly.
4. **Remote Boundary** — gated worker claims ("not observed", never red).
5. **Compare Runs** — derived deltas if compare JSON is present.

**Optional fixture path:** to show the agent-loop chain (`simulated_v1`), export
fixture projections from `verify-demo.sh` output under `data/demo-proof/projections/`
and load manually — or narrate from `docs/proof-samples/agent-loop-summary.json`.

Show: the **truth-label legend** — grayscale-safe shape+hue glyphs plus the
confidence-meter, redaction lock-chip, and provenance rows. **Point:** every node
carries `source_kind`, and the shape (not just the color) is the guarantee.

> No Nix? Stop here after Tier 2 proof-samples. `docs/proof-samples/` holds
> redacted real summaries.

---

## Step 4 — Real cold/warm cache economics (~10 min, Nix)

```bash
nix develop
scripts/cold-warm-cache-proof.sh
```

Show: `data/cold-warm-proof/summary.json` — cold `hit_rate` 0.0 vs warm
`hit_rate` 1.0. **Point:** **collectable_v1** — measured from real Bazel runs
through a real NativeLink cache.

## Step 5 — Agent-loop closure: validation/cache spine (~15 min, Nix)

```bash
scripts/agent-loop-proof.sh
./scripts/worker-evidence-proof.sh   # M7 — fixture replay or live stdout
```

Show: `data/agent-loop-proof/summary.json` with `chain_complete=true`. **Point:**
validation/cache leg is **collectable_v1**; agent/change provenance stays
**simulated_v1** (deterministic patch, zero LLM tokens). That distinction is the
product. Worker identity is separate: M7 promotes only when admin stdout matches
(`data/worker-evidence-proof/summary.json`).

---

## One-command version

```bash
scripts/verify-demo.sh
```

Runs tests, doctor, real-tool smoke, cold/warm, local-exec, agent-loop proof,
fixture simulate+ingest, and canvas build. Exports **simulated_v1** fixture
projections to `data/demo-proof/projections/` only — it does **not** overwrite
committed `apps/canvas/public/projections/` (canvas-dev default).

---

## Closing line

"When AI writes the code, NativeLink makes validating it fast, and NLFR makes
validating it trustworthy — with every claim labeled by how it was proven."
