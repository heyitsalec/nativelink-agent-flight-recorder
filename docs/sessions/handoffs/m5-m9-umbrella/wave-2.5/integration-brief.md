# Wave 3 Integration Brief — M9 Multi-run Compare

**From:** Wave 2.5 review (2026-06-06)  
**For:** M9 coordinator (`m9-multi-run-compare`) — blocked until this brief publishes  
**Branch context:** `feat/frontier-wave` · M7/M8 landed in Wave 2

## Wave 2 carryover (close in parallel, non-blocking for M9)

- Update [`ONE_PAGER.md`](../../../ONE_PAGER.md) and [`ARCHITECTURE_TRACK.md`](../../../ARCHITECTURE_TRACK.md): `worker_identity` is **conditional** when M7 stdout is attached — not blanket-unproven
- Promote redacted CI summaries to `docs/proof-samples/` after first green GHA run (**DEFERRED** — GHA offline)
- Operator path for M8: document live `record-agent-change.sh` (without `--dry-run`) in `adapters/cursor/README.md`

## M9 — Multi-run retention + compare

**Objective:** Foundation for comparing agent runs over time; GUI compare lens; honest `derived_v1` deltas only.

### Dependencies on Wave 2

| Upstream | M9 consumption |
|----------|----------------|
| M5 `record-proof` / `canvas-dev` run groups | Left/right compare inputs via SQLite |
| M7 `worker_identity_observed` | Compare dimension from `remote_execution` proof block metrics |
| M8 `agent_provenance` blocks | Compare dimension for agent leg presence (not raw prompts) |

### Deliverables

| Path | Purpose |
|------|---------|
| `src/nlfr/projectors/compare.py` | `export_compare_projection(conn, left_run_group, right_run_group)` |
| `src/nlfr/commands/compare_cmd.py` | `compare export` + `compare index` retention CLI |
| `scripts/compare-proof.sh` | Cross-DB compare (e.g. record-proof vs canvas-dev) → `summary.json` |
| `apps/canvas/src/App.tsx` | Compare lens loading `compare-projection.json` only |
| `apps/canvas/scripts/truth-guard.mjs` | Compare schema + lens visibility |
| `tests/test_compare.py` | Fixture-backed export and index |

### Compare dimensions (`derived_v1`)

| Dimension | Source | Must not claim |
|-----------|--------|----------------|
| `run_counts` | proof packet summaries | cross-run worker correlation |
| `cache_metrics` | cache proof blocks | dollar savings |
| `worker_identity` | `worker_identity_observed` per run group | queue time, placement |
| `agent_provenance` | `agent_provenance` block presence | raw prompt or model reasoning |
| `status_deltas` | SQLite run status counts | scheduler assignment |

All nodes/claims require four truth labels + `evidence_refs` to `run_group:{left}` and `run_group:{right}`.

### Retention policy (v1 ceiling)

- `compare index` lists run groups in SQLite — **index only**
- No automatic purge in v1; document honest blocker in proof packet if retention grows unbounded
- Export APIs are projection JSON files, not new truth sources

### Rules

- Canvas compare lens renders **only** exported `compare-projection.json`
- No invented nodes, metrics, or backend state
- Compare does not merge worker graphs across runs — summary-level deltas only

### Proof matrix for M9 completion

```bash
uv run pytest -q tests/test_compare.py
npm --prefix apps/canvas run test:truth
./scripts/compare-proof.sh   # requires record-proof + canvas-dev DBs
```

Optional dogfood:

```bash
PYTHONPATH=src uv run python -m nlfr compare index --db data/record-proof/nlfr.sqlite --json
PYTHONPATH=src uv run python -m nlfr compare export \
  --db data/record-proof/nlfr.sqlite \
  --left record-proof --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json
```

## Retrospective validation (2026-06-06)

M9 implementation matches this brief per [`wave-3/provenance-m9-compare.md`](../wave-3/provenance-m9-compare.md). Local `compare-proof.sh` PASS in Wave 2.5 e2e review. Remaining gaps for human design (Wave 4):

1. Compare lens visual polish — read index/export data only
2. Run selector UX wired to `compare index` JSON
3. Optional committed `compare-projection.json` — generate via export, not invented defaults

## Wave 4 preview (do not start until 2.5 pack published)

Human design pass per [`wave-4/human-design-handoff.md`](../wave-4/human-design-handoff.md): typography, Action Graph worker nodes, Proof Drawer density, screenshot baselines after design changes.
