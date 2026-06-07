# T1-SPINE Audit — Compare Topology, Retention, Run Groups

**Worker:** `t1-spine-r-compare-retention` (explore)  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

## Executive summary

Multi-run compare is **implemented at the projector/CLI layer** (M9): `nlfr compare export` builds a five-dimension `derived_v1` compare projection from proof packet summaries; `nlfr compare index` lists run groups with retention metadata. `scripts/compare-proof.sh` performs cross-DB compare for dogfood pairs (`record-proof` vs `canvas-dev`).

Tier 1 still lacks **`scripts/compare-agent-runs.sh`** (named in DAG proof matrix and coord-t1-spine charter) despite partial output at `data/compare-agent-runs/`. The gap is a **tier-1 orchestration script** that indexes three agent run groups, emits pairwise compares, and writes a rollup `summary.json` for demo Act 3 (`agent-change` + compare triple).

---

## Compare topology

### Layer model

```
┌─────────────────────────────────────────────────────────────────┐
│ Tier 1 demo / operator scripts (GAPS: tier1-agent-demo,         │
│ compare-agent-runs.sh)                                            │
├─────────────────────────────────────────────────────────────────┤
│ Dogfood scripts: compare-proof.sh                               │
├─────────────────────────────────────────────────────────────────┤
│ CLI: nlfr compare export | nlfr compare index                   │
├─────────────────────────────────────────────────────────────────┤
│ Projector: src/nlfr/projectors/compare.py                       │
│   ← proof packets (export_proof_packet) + run_rows (SQLite)     │
├─────────────────────────────────────────────────────────────────┤
│ SQLite per output dir: {output}/nlfr.sqlite                     │
│   runs.run_group, proof_blocks, changes, artifacts              │
├─────────────────────────────────────────────────────────────────┤
│ Canvas: apps/canvas/src/App.tsx CompareLens                     │
│   ← public/projections/compare-projection.json (optional)       │
└─────────────────────────────────────────────────────────────────┘
```

### Single-DB vs cross-DB compare

| Mode | Entry | When |
|------|-------|------|
| Same DB | `nlfr compare export --db PATH --left G1 --right G2` | Both run groups ingested into one SQLite file |
| Cross-DB | `nlfr compare export --left-db A --right-db B --left G1 --right G2` | Dogfood dirs with separate `nlfr.sqlite` (compare-proof pattern) |

`compare-proof.sh` uses cross-DB mode because `record-proof` and `canvas-dev` live in separate output trees.

### Canvas wiring

- Fetch path: `/projections/compare-projection.json`
- Compare lens renders only when file present; otherwise shows explicit empty state
- `truth-guard.mjs` validates compare schema when file exists; checks lens visibility after tab click

Committed canvas projections include `compare-projection.json` (4816 bytes) alongside `action-graph.json`, `proof.json`, and `runway.json`.

---

## Five compare dimensions

All dimensions are `derived_v1` with bounded claims and `evidence_refs` limited to `run_group:{left}` and `run_group:{right}`.

| # | `id` | Title | Left/right inputs | Delta highlights |
|---|------|-------|-------------------|------------------|
| 1 | `run_counts` | Run Counts | `proof.summary.runs` | `delta.runs` |
| 2 | `cache_metrics` | Cache Metrics | proof block `id=cache` metrics | hits, misses, hit_rate deltas |
| 3 | `worker_identity` | Worker Identity | `remote_execution` block `worker_identity_observed` | boolean changed flag |
| 4 | `agent_provenance` | Agent Provenance | `agent_provenance` proof blocks | present, block_count, model/hash prefixes |
| 5 | `status_deltas` | Status Deltas | SQLite run rows per group | per-status counts |

### Dimension 4 — Tier 1 relevance

`agent_provenance` dimension is the bridge between M8 adapter and Act 3 compare narrative:

- Detects `block_kind == agent_provenance` or title prefix `Agent Provenance`
- Summarizes `model` and `prompt_sha256_prefix` (12 chars) per block
- Does **not** claim validation success — only block presence and metadata shape

For tier1 triple compare (`record-proof`, `canvas-dev`, `agent-bugfix-1`), expect dimension 4 to flip `present` when bugfix run group includes adapter-recorded provenance.

### Truth boundaries (enforced)

- No worker/queue/scheduler correlation across run groups
- Worker identity true only when direct evidence in proof packet
- Cache metrics derived from proof blocks only — not live NativeLink admin APIs

---

## Data / retention map

### Run group output directories (host snapshot)

| Run group | Typical output dir | Purpose |
|-----------|-------------------|---------|
| `record-proof` | `data/record-proof/` | Bazel/cache proof dogfood |
| `canvas-dev` | `data/canvas-dev/` | Canvas build record (`record-canvas-build.sh`) |
| `agent-bugfix-1` | `data/agent-bugfix-1/` | Tier 1 Act 1 bounded bugfix |
| `agent-feature-compare` | `data/agent-feature-compare/` | Tier 1 Act 2 feature slice |
| `agent-change` | `data/agent-change/` | Tier 1 Act 3 meta dogfood |
| `agent-change-proof` | `data/agent-change-proof/` | M8 default adapter output |
| `compare-proof` | `data/compare-proof/` | compare-proof.sh rollup |
| `compare-agent-runs` | `data/compare-agent-runs/` | **Partial** tier1 compare output (no script in repo) |

Each output dir follows the NLFR artifact pattern:

```
{output}/
  nlfr.sqlite
  runs/{run_id}/artifacts/...
  projections/action-graph.json   # after export
  projections/proof.json
  summary.json                    # script-specific rollup
```

### Retention index CLI

```bash
nlfr compare index --db data/nlfr/nlfr.sqlite
nlfr compare index --db data/record-proof/nlfr.sqlite --json
```

Returns per `run_group`:

- `run_count`
- `first_started_at`
- `last_started_at`

Sorted by `last_started_at DESC`. This is the **retention discovery** surface — not deletion policy. No automatic purge is implemented; retention rules remain a documented gap in `USEFULNESS_ROADMAP.md` Gap 2.

### Existing compare-agent-runs output (manual/partial)

`data/compare-agent-runs/summary.json` (host):

```json
{
  "status": "ok",
  "compare_count": 2,
  "run_groups": ["record-proof", "canvas-dev", "agent-bugfix-1"],
  "pairwise_compares": [
    ".../compare-record-proof-vs-canvas-dev.json",
    ".../compare-canvas-dev-vs-agent-bugfix-1.json"
  ],
  "source_kind": "derived_v1"
}
```

Projections on disk:

- `compare-record-proof-vs-canvas-dev.json`
- `compare-canvas-dev-vs-agent-bugfix-1.json`

**Missing pair for full triple:** `record-proof` vs `agent-bugfix-1` (3 choose 2 = 3 pairs; only 2 present).

---

## DAG run groups (tier1-agent-vision)

From `docs/dags/tier1-agent-vision.md`:

| Act | Run group | Demo | Compare role |
|-----|-----------|------|--------------|
| 1 | `agent-bugfix-1` | yes | Right/left leg in feature vs bugfix narrative |
| 2 | `agent-feature-compare` | yes | Paired with bugfix or baseline |
| 3 | `agent-change` + compare triple | story hook | Meta dogfood + 3-way rollup |

Act 3 expects **compare triple** across infrastructure proof (`record-proof`), canvas dogfood (`canvas-dev`), and agent bugfix (`agent-bugfix-1`). The partial `data/compare-agent-runs/` output demonstrates intent but lacks the orchestrating script and complete pairwise set.

---

## `compare-proof.sh` vs needed `compare-agent-runs.sh`

### `compare-proof.sh` (exists)

- Fixed pair: `record-proof` vs `canvas-dev`
- Cross-DB via env overrides (`NLFR_RECORD_PROOF_OUTPUT`, `NLFR_CANVAS_DEV_OUTPUT`)
- Writes `data/compare-proof/projections/compare-projection.json` + `summary.json`
- Single pairwise compare — not tier1 triple

### `compare-agent-runs.sh` (missing)

Charter requirements (coord-t1-spine):

1. Discover/index tier1 run groups across known output dirs
2. Emit **pairwise** compare projections for demo triple (3 pairs)
3. Write rollup `summary.json` with `compare_count`, `pairwise_compares`, `evidence_refs`
4. Exit non-zero with clear blocker message when a DB or run group is absent
5. Integrate with `tier1-agent-demo.sh --dry-run` (list planned compares without DB)

Suggested env contract (design input for wave 2):

| Env var | Default | Purpose |
|---------|---------|---------|
| `NLFR_COMPARE_AGENT_OUTPUT` | `data/compare-agent-runs` | Rollup dir |
| `NLFR_TIER1_GROUPS` | `record-proof,canvas-dev,agent-bugfix-1` | Compare triple |
| `NLFR_AGENT_BUGFIX_OUTPUT` | `data/agent-bugfix-1` | Per-group DB root |
| `NLFR_AGENT_FEATURE_OUTPUT` | `data/agent-feature-compare` | Act 2 dir |

Script should reuse `build_compare_projection` exactly as `compare-proof.sh` does — no new compare semantics.

---

## Gaps for `compare-agent-runs.sh` and T1-SPINE

### P0 — script deliverable

1. **Create `scripts/compare-agent-runs.sh`** — only script referenced in tier1 proof matrix that is absent from `scripts/`.
2. **Complete triple pairwise set** — add missing `record-proof` vs `agent-bugfix-1` projection.
3. **`tests/test_tier1_agent_demo.py`** — assert dry-run lists compares; optional fixture DB test for dimension ids.

### P1 — retention and discovery

4. **`nlfr compare index` integration** — script should call index per DB and fail loudly if expected run group missing from index.
5. **Document retention policy** — index lists groups; tier1 demo should state artifacts are local-only, no auto-prune.
6. **`compare_cmd --format`** — coord-t1-feature charter mentions formatted output; only JSON export exists today.

### P2 — canvas and demo

7. **Promote one pairwise compare to `apps/canvas/public/projections/compare-projection.json`** — canvas loads single file; tier1 demo may symlink/copy Act-relevant pair (e.g. `canvas-dev` vs `agent-bugfix-1`).
8. **Truth-guard** — already validates compare when present; extend to check dimension count === 5 when tier1 fixture loaded.
9. **Act 2 narrative** — `agent-feature-compare` not yet in `data/compare-agent-runs/summary.json`; add when feature recording lands.

### Non-gaps (already landed)

- Five-dimension compare projector
- Cross-DB export in CLI
- Compare lens in App.tsx
- M9 tests in `tests/test_compare.py`

---

## Proof commands

```bash
# Compare projector unit tests
uv run pytest tests/test_compare.py -q

# Single cross-DB compare (dogfood)
./scripts/compare-proof.sh

# Retention index
uv run python -m nlfr compare index --db data/record-proof/nlfr.sqlite --json

# Manual pairwise export
uv run python -m nlfr compare export \
  --left-db data/canvas-dev/nlfr.sqlite \
  --right-db data/agent-bugfix-1/nlfr.sqlite \
  --left canvas-dev \
  --right agent-bugfix-1 \
  --output /tmp/compare-canvas-vs-bugfix.json

# Tier 1 matrix (BLOCKED until script exists)
./scripts/compare-agent-runs.sh
```

---

## Source map

| Artifact | Path |
|----------|------|
| Compare projector | `src/nlfr/projectors/compare.py` |
| Compare CLI | `src/nlfr/commands/compare_cmd.py` |
| Dogfood compare | `scripts/compare-proof.sh` |
| M9 provenance | `docs/sessions/handoffs/m5-m9-umbrella/wave-3/provenance-m9-compare.md` |
| Partial tier1 output | `data/compare-agent-runs/` |
| Tier 1 DAG | `docs/dags/tier1-agent-vision.md` |
| Coordinator charter | `docs/sessions/handoffs/tier1-agent-vision/wave-0/coordinator-charters.md` |
| Canvas compare lens | `apps/canvas/src/App.tsx` (`CompareLens`) |
| Truth guard | `apps/canvas/scripts/truth-guard.mjs` |

No credentials or private host paths are required beyond standard repo-relative `data/` trees.
