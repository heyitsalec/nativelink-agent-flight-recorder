# M9 — Multi-run retention + compare

Milestone: architecture track M9. Status: **landed**.

## Objective

Foundation for comparing agent runs over time; GUI compare lens; PR attachment recipe.

## Deliverables

- [x] `src/nlfr/projectors/compare.py` — `export_compare_projection(conn, left_run_group, right_run_group)`
- [x] `src/nlfr/commands/compare_cmd.py` — `compare export` + `compare index`
- [x] `scripts/compare-proof.sh` — record-proof vs canvas-dev compare + `summary.json`
- [x] Canvas compare lens in `apps/canvas/src/App.tsx`
- [x] Truth guard extension for compare projection schema
- [x] `tests/test_compare.py` — fixture-backed compare export

Depends on M5 + M8 for meaningful compare data.

## CLI

```bash
nlfr compare index --db PATH [--json]
nlfr compare export --db PATH --left RUN_GROUP --right RUN_GROUP [--output PATH]
./scripts/compare-proof.sh
```

## Proof matrix

```bash
uv run pytest -q tests/test_compare.py
npm --prefix apps/canvas run test:truth
./scripts/compare-proof.sh   # requires record-proof + canvas-dev DBs
```

## Compare dimensions (derived_v1)

| Dimension | Source |
|-----------|--------|
| run_counts | proof packet summary |
| cache_metrics | proof cache block |
| worker_identity | remote_execution block metrics |
| agent_provenance | agent_provenance proof blocks |
| status_deltas | SQLite run status counts |

All claims include `evidence_refs` to `run_group:{left}` and `run_group:{right}`.
