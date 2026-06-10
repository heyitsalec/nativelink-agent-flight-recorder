# Demo rehearsal script (condensed)

**Source:** [`docs/DEMO_SCRIPT.md`](../../../../DEMO_SCRIPT.md) + Tier 1 live Bazel paths  
**Time:** Tier 1 ~5 min · Tier 2 ~15 min · Tier 3 ~30 min  
**Mandatory rule:** Say `source_kind` aloud whenever opening a lens or JSON file.

---

## Prep (all tiers)

```bash
uv sync
npm --prefix apps/canvas install
```

Skim [`docs/ONE_PAGER.md`](../../../../ONE_PAGER.md) "explicitly unproven" list before any external demo.

---

## Tier 1 — Agent vision (~5 min)

**Thesis:** "AI wrote it; here's proof."  
**DAGs:** [`tier1-agent-vision.md`](../../../../dags/tier1-agent-vision.md) · [`tier1-live-bazel.md`](../../../../dags/tier1-live-bazel.md)

### Primary path (Nix + real Bazel)

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

| Artifact | Label | Say aloud |
|----------|-------|-----------|
| `data/tier1-live-bazel/summary.json` | `collectable_v1` | Live Bazel validation spine |
| `data/agent-bugfix-1/summary.json` | `collectable_v1`, `bazel_validated: true` | Act 1 — bugfix |
| `data/agent-feature-compare/summary.json` | `collectable_v1`, `bazel_validated: true` | Act 2 — feature |

### Act 3 — compare (derived, not fleet)

```bash
./scripts/compare-agent-runs.sh
./scripts/promote-tier1-compare.sh
```

**Say:** Compare lens is **`derived_v1`** — deltas across run groups, **no worker correlation**.

### Canvas (Tier 1 view)

```bash
npm --prefix apps/canvas run preview
# http://127.0.0.1:5174/?view=tier1-demo  (Compare lens)
# http://127.0.0.1:5174/?view=graph-only
```

Operator: type `composer` for view-spec export drawer. Confirm truth legend bottom-left.

### No-Nix fallback

Open committed samples — still honest:

- `docs/proof-samples/agent-bugfix-summary.json`
- `docs/proof-samples/agent-feature-summary.json`

Point at `bazel_validated` and `validation: bazel`. **Not** the mixed `agent-loop-summary.json` (that one is bounded `simulated_v1` agent leg).

### Pytest-only fallback (blocker smoke, not demo headline)

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
./scripts/tier1-agent-demo.sh --dry-run --json
```

Use only when explaining CI gate — **do not** present as live Bazel proof.

---

## Tier 1 quick steps (evaluator ladder)

Condensed from DEMO_SCRIPT Steps 1–3 for a 5-minute path without Nix.

| Step | Time | Command | Point |
|------|------|---------|-------|
| 1 Doctor | ~30s | `PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json` | Recorder honest about environment before recording |
| 2 Tests | ~30s | `uv run pytest tests -q` | Spine under test (SQLite + fixtures) |
| 3 Canvas | ~2 min | `npm --prefix apps/canvas run dev -- --host 127.0.0.1` | Default **canvas-dev `collectable_v1`** dogfood projection |

**Canvas drive:** Action Graph → Proof Packet (unsupported claims) → Remote Boundary → Compare Runs (if loaded).

**Optional fixture:** `docs/proof-samples/agent-loop-summary.json` — narrate **mixed** labels (validation collectable, agent simulated).

---

## Tier 2 — NativeLink team (~15 min, recommended)

| Time | Segment | Action |
|------|---------|--------|
| 0:00–0:30 | Thesis | README north star |
| 0:30–1:30 | Dual heroes | `docs/media/nlfr-canvas-tour.gif` + `nlfr-evidence-loop.gif` — **curated replay, not live shell** |
| 1:30–5:30 | Live canvas | `npm --prefix apps/canvas run preview` — green **canvas-dev collectable_v1** banner |
| 5:30–8:30 | Evidence spine | Terminal simulate → ingest → graph export (below) |
| 8:30–11:30 | Proof samples | `cold-warm-summary.json`, `two-worker-summary.json`, `agent-loop-summary.json` |
| 11:30–13:30 | Honesty | ONE_PAGER unsupported list; M9 compare = `derived_v1` |
| 13:30–15:00 | Close | Offer Tier 3 live Nix if they want exit codes |

### Tier 2 evidence spine (terminal)

```bash
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario safe-leaf-change --output-dir /tmp/nlfr-demo \
  --run-group demo-tier2 --skip-run --json

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

**Say:** "Canvas consumes this contract; it never calls NativeLink APIs at runtime."

### Tier 2 cue cards (do not skip)

| If you show… | Must say… |
|--------------|-----------|
| canvas-dev projection | **collectable_v1** — real dogfood record |
| cold-warm sample | **collectable_v1** — real Bazel through NativeLink cache |
| two-worker sample | **collectable_v1** — endpoint readiness only, **not** distributed execution |
| agent-loop sample | **Mixed** — validation collectable, agent/change simulated |
| agent-bugfix / agent-feature samples | **collectable_v1** — live agent record, `bazel_validated: true` |
| Compare lens | **derived_v1** — no worker correlation |
| Remote Boundary | Worker identity **conditional** on M7 stdout |

### Tier 2 fallback

If canvas fails: hero GIFs + `docs/proof-samples/` only. Truth labels in narration still required.

---

## Tier 3 — Skeptics (~30 min, Nix)

| Step | Command | Proof |
|------|---------|-------|
| Cold/warm | `nix develop` then `scripts/cold-warm-cache-proof.sh` | `data/cold-warm-proof/summary.json` — hit_rate 0.0 → 1.0 |
| Agent loop | `scripts/agent-loop-proof.sh` | `chain_complete=true`; validation collectable, agent simulated |
| M7 worker | `./scripts/worker-evidence-proof.sh` | `worker_identity_observed` only when stdout matches |

---

## One-command verify (pre-demo smoke)

```bash
./scripts/verify-demo.sh
```

Runs tests, doctor, proof scripts, fixture simulate+ingest, canvas build. Exports **simulated_v1** fixtures to `data/demo-proof/projections/` — does **not** replace committed canvas-dev default.

---

## Closing line

"When AI writes the code, NativeLink makes validating it fast, and NLFR makes validating it trustworthy — with every claim labeled by how it was proven."

---

## Tier 1 file map (quick reference)

| Path | Role |
|------|------|
| `scripts/tier1-live-bazel-proof.sh` | Acts 1+2 live Bazel gate |
| `scripts/tier1-agent-demo.sh` | Three-act orchestrator |
| `scripts/tier1-bugfix-setup.sh` / `tier1-feature-setup.sh` | Repo state for acts |
| `scripts/compare-agent-runs.sh` | Act 3 compare narrative |
| `scripts/promote-tier1-compare.sh` | Promote compare projection to canvas |
| `demo/scenarios/tier1/agent-bugfix-1.json` | Act 1 scenario |
| `demo/scenarios/tier1/agent-feature-compare.json` | Act 2 scenario |
| `apps/canvas/public/views/tier1-demo.json` | Tier1 view spec |
| `docs/proof-samples/agent-bugfix-summary.json` | No-Nix Act 1 sample |
| `docs/proof-samples/agent-feature-summary.json` | No-Nix Act 2 sample |
