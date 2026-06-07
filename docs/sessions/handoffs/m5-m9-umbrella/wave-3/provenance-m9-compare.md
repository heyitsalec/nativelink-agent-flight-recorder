# Wave 3 M9 Multi-run Compare Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Agent:** M9 multi-run compare

## Deliverables

| Path | Purpose |
|------|---------|
| `src/nlfr/projectors/compare.py` | Compare projection from proof packet summaries (5 dimensions) |
| `src/nlfr/commands/compare_cmd.py` | `compare export` + `compare index` retention CLI |
| `scripts/compare-proof.sh` | Cross-DB compare of record-proof vs canvas-dev → `summary.json` |
| `apps/canvas/src/App.tsx` | Optional compare lens loading `compare-projection.json` |
| `apps/canvas/scripts/truth-guard.mjs` | Compare projection schema + lens visibility checks |
| `tests/test_compare.py` | Fixture-backed compare export and index |

## Truth labels

| Surface | `source_kind` | Notes |
|---------|---------------|-------|
| Compare projection root | `derived_v1` | Aggregates two proof packets |
| Each compare dimension | `derived_v1` | Claims bounded to proof summaries + run rows |
| Canvas compare lens | renders labels only | No invented nodes or backend state |

Evidence refs use `run_group:{left}` and `run_group:{right}` — no cross-run worker/queue correlation claims.

## Compare dimensions

1. **run_counts** — proof summary run totals
2. **cache_metrics** — hits/misses/hit_rate delta
3. **worker_identity** — `worker_identity_observed` from remote_execution block
4. **agent_provenance** — presence of `agent_provenance` proof blocks
5. **status_deltas** — per-status run counts from SQLite

## Proof matrix

| # | Command | Exit | Result | Key artifacts |
|---|---------|------|--------|---------------|
| 1 | `uv run pytest -q` | 0 | PASS | includes `tests/test_compare.py` |
| 2 | `npm --prefix apps/canvas run test:truth` | 0 | PASS | graph parity + optional compare schema |
| 3 | `./scripts/compare-proof.sh` | 0/1 | BLOCKED if record-proof/canvas-dev DBs absent | `data/compare-proof/summary.json` |

## Summary

M9 adds honest multi-run compare: proof-packet summary diffs with derived_v1 truth labels, a retention index CLI, cross-DB compare script for dogfood run groups, and a canvas compare lens that renders only exported compare projection JSON.
