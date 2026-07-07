# How-to: export and compare run groups

**Quadrant:** How-to · **Audience:** operators comparing agent validation runs  
**Milestone:** M9 — multi-run retention + compare lens

Export projection JSON for one run group, or build a `derived_v1` compare projection
across two groups. The canvas Compare mode renders **only** exported compare JSON.

← [Wiki hub](../README.md) · [CLI reference](../reference/cli.md)

## Prerequisites

- At least one SQLite DB with recorded runs. `nlfr record` writes a per-run-group
  database at **`data/nlfr-record/<run-group>/nlfr.sqlite`** (relative to the
  Bazel workspace):

  ```bash
  PYTHONPATH=src uv run python -m nlfr record --run-group baseline -- bazel test //...
  # -> data/nlfr-record/baseline/nlfr.sqlite
  ```

- For a cross-DB compare of two recorded groups: record two groups, each in its
  own per-run-group database.

> **Read commands never create a database.** A nonexistent, zero-byte, or
> non-SQLite `--db` (or `--left-db`/`--right-db`) is a hard error (exit 2) that
> names the path and fabricates no file — a typo can never conjure an empty,
> zero-value projection. Record a run first, or point `--db` at an existing
> database.

M9 does **not** merge worker graphs across runs or claim queue time / placement.
See [Architecture track](../../ARCHITECTURE_TRACK.md) and the
[compare projection contract](../reference/contracts/compare-projection-v1.md).

## List run groups (retention index)

```bash
PYTHONPATH=src uv run python -m nlfr compare index \
  --db data/nlfr-record/baseline/nlfr.sqlite \
  --json
```

Limit the newest groups when the index grows large (index-only; no purge):

```bash
PYTHONPATH=src uv run python -m nlfr compare index \
  --db data/nlfr-record/baseline/nlfr.sqlite \
  --limit 5 \
  --json
```

### V1 retention policy

| Mode | Constant | Meaning |
|------|----------|---------|
| Discovery | `index_only` | `compare index` lists run groups from SQLite |
| Purge | `no_auto_purge` | NLFR v1 never deletes rows or artifact files |
| Lifecycle | `operator_managed` | Operators prune local DBs and artifact dirs manually |

Proof packet exports include a `retention` block with these notes (`derived_v1`,
`high`). There is no `nlfr purge` or TTL job in v1.

## Export single-run projections

```bash
PYTHONPATH=src uv run python -m nlfr graph export \
  --db data/nlfr-record/baseline/nlfr.sqlite \
  --run-group baseline \
  --output apps/canvas/public/projections/graph-projection.json

PYTHONPATH=src uv run python -m nlfr proof export \
  --db data/nlfr-record/baseline/nlfr.sqlite \
  --run-group baseline \
  --output apps/canvas/public/projections/proof-packet.json
```

Default `--run-group` is `latest` when omitted — note `latest` is a **literal
match**, not a resolver; pass the run group you actually recorded.

## Export compare projection (two recorded groups, cross-DB)

Because `nlfr record` writes one database per run group, the realistic way to
compare two recorded groups is the cross-DB form — one `--*-db` per group. Each
side is opened read-only and validated independently, so an empty side names
*which* side failed:

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/nlfr-record/baseline/nlfr.sqlite \
  --right-db data/nlfr-record/candidate/nlfr.sqlite \
  --left baseline \
  --right candidate \
  --output apps/canvas/public/projections/compare-projection.json
```

## Export compare projection (same DB)

Use the single-`--db` form only when one database holds **both** groups — e.g.
runs recorded into a shared `--output-dir`, or multiple groups ingested into one
`nlfr.sqlite`:

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --db data/nlfr-record/shared/nlfr.sqlite \
  --left baseline \
  --right candidate \
  --output apps/canvas/public/projections/compare-projection.json
```

## Run the compare proof script

End-to-end proof with **demo-fixture** DBs. This script has its own output dirs
(`data/record-proof/`, `data/canvas-dev/`) written by the demo record scripts —
distinct from the `data/nlfr-record/<run-group>/` layout `nlfr record` produces:

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

## Related

- M7 worker dimension: [proof scripts matrix § M7](../reference/proof-scripts-matrix.md)
- M8 agent dimension: [Cursor adapter](../../../adapters/cursor/README.md)
- [One pager](../../ONE_PAGER.md) — unsupported fleet claims
