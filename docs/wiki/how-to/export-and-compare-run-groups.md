# How-to: export and compare run groups

**Quadrant:** How-to · **Audience:** operators comparing agent validation runs  
**Milestone:** M9 — multi-run retention + compare lens

Export projection JSON for one run group, or build a `derived_v1` compare projection
across two groups. The canvas Compare mode renders **only** exported compare JSON.

← [Wiki hub](../README.md) · [CLI reference](../reference/cli.md)

## Prerequisites

- At least one SQLite DB with ingested runs (`nlfr.sqlite` under a proof output dir)
- For cross-DB compare: two DBs (e.g. `record-proof` and `canvas-dev`)

M9 does **not** merge worker graphs across runs or claim queue time / placement.
See [Architecture track](../../ARCHITECTURE_TRACK.md) and
[m5-m9-umbrella integration brief](../../sessions/handoffs/m5-m9-umbrella/wave-2.5/integration-brief.md).

## List run groups (retention index)

```bash
PYTHONPATH=src uv run python -m nlfr compare index \
  --db data/record-proof/nlfr.sqlite \
  --json
```

Output is an index only — v1 does not auto-purge old groups.

## Export single-run projections

```bash
PYTHONPATH=src uv run python -m nlfr graph export \
  --db data/record-proof/nlfr.sqlite \
  --run-group record-proof \
  --output apps/canvas/public/projections/graph-projection.json

PYTHONPATH=src uv run python -m nlfr proof export \
  --db data/record-proof/nlfr.sqlite \
  --run-group record-proof \
  --output apps/canvas/public/projections/proof-packet.json
```

Default `--run-group` is `latest` when omitted.

## Export compare projection (same DB)

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --db data/record-proof/nlfr.sqlite \
  --left record-proof \
  --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json
```

## Export compare projection (two DBs)

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/record-proof/nlfr.sqlite \
  --right-db data/canvas-dev/nlfr.sqlite \
  --left record-proof \
  --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json
```

## Run the compare proof script

End-to-end proof with fixture-backed DBs:

```bash
./scripts/compare-proof.sh
```

Writes `data/compare-proof/summary.json` and projections under
`data/compare-proof/projections/`.

Redacted committed excerpt (fixture-backed `record-proof` vs `canvas-dev`):
[`compare-summary.json`](../../proof-samples/compare-summary.json) and
[`compare-projection-sample.json`](../../proof-samples/compare-projection-sample.json).

Environment overrides: `NLFR_RECORD_PROOF_OUTPUT`, `NLFR_CANVAS_DEV_OUTPUT`,
`NLFR_COMPARE_LEFT`, `NLFR_COMPARE_RIGHT`, `NLFR_COMPARE_OUTPUT`.

## Compare dimensions (`derived_v1`)

| Dimension | Source | Must not claim |
|-----------|--------|----------------|
| `run_counts` | proof summaries | cross-run worker correlation |
| `cache_metrics` | cache proof blocks | dollar savings |
| `worker_identity` | M7 `worker_identity_observed` per group | queue, placement |
| `agent_provenance` | M8 block presence | raw prompt |
| `status_deltas` | SQLite run status | scheduler assignment |

All compare nodes need four [truth labels](../reference/truth-labels.md) and
`evidence_refs` to both `run_group:{left}` and `run_group:{right}`.

## Canvas compare lens

1. Export `compare-projection.json` to `apps/canvas/public/projections/`
2. Start canvas: `npm --prefix apps/canvas run dev`
3. Select **Compare Runs** mode (`data-testid="canvas-mode-compare"`)

Mode contract: [design routing](../../design/routing.md).

## Verify

```bash
uv run pytest -q tests/test_compare.py tests/test_compare_proof_sample.py
npm --prefix apps/canvas run test:truth
```

## GHA offline

Compare proof is local-gate friendly. CI promotion of redacted samples is deferred:
[GHA offline proof shift](../../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Related

- M7 worker dimension: [proof scripts matrix § M7](../reference/proof-scripts-matrix.md)
- M8 agent dimension: [Cursor adapter](../../../adapters/cursor/README.md)
- [One pager](../../ONE_PAGER.md) — unsupported fleet claims
