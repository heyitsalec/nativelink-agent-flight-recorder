# How-to: browse run history

**Quadrant:** How-to · **Audience:** operators reviewing multiple validation runs  
**Wave:** 12 — multi-run history beyond M9 pairwise compare

Export a `derived_v1` run-history projection from the retention index, then load
it in the canvas run-group picker or any JSON consumer. History summarizes proof
packet metadata per group — it does **not** invent fleet trends or auto-purge rows.

← [Wiki hub](../README.md) · [Export and compare run groups](export-and-compare-run-groups.md)

## Prerequisites

- SQLite DB with ingested runs (`nlfr.sqlite` under a proof output dir)
- M9 retention semantics: `compare index` lists groups; v1 never auto-purges

## List run groups (index)

Same retention index as M9 compare:

```bash
PYTHONPATH=src uv run python -m nlfr compare index \
  --db data/record-proof/nlfr.sqlite \
  --json
```

Limit when the index grows:

```bash
PYTHONPATH=src uv run python -m nlfr compare index \
  --db data/record-proof/nlfr.sqlite \
  --limit 10 \
  --json
```

## Export multi-run history projection

```bash
PYTHONPATH=src uv run python -m nlfr compare history \
  --db data/record-proof/nlfr.sqlite \
  --output apps/canvas/public/projections/run-history.json
```

Limit to the newest groups (index-only; no purge):

```bash
PYTHONPATH=src uv run python -m nlfr compare history \
  --db data/record-proof/nlfr.sqlite \
  --limit 5 \
  --output /tmp/run-history.json
```

### What each run group entry includes

| Field | Source | Must not claim |
|-------|--------|----------------|
| `run_count`, `first_started_at`, `last_started_at` | retention index | cross-run worker correlation |
| `status_counts` | SQLite `runs.status` | scheduler assignment |
| `proof_summary` | proof packet `summary` | live backend state |
| `cache_metrics` | proof block `cache` | dollar savings |
| `worker_identity_observed` | M7 remote-execution block | queue, placement |
| `agent_provenance_present` | M8 block presence | raw prompt |

Root `claims` state honest boundaries. Every entry carries four
[truth labels](../reference/truth-labels.md).

## Canvas run-group picker

Load order in `RunGroupSelector`:

1. **`compare-index.json`** — compact `run_group_index` (preferred when present)
2. **`run-history.json`** — richer multi-run projection with per-group summaries
3. **`compare-projection.json`** — pairwise fallback from `left`/`right` groups

Regenerate history for tier1 demo:

```bash
PYTHONPATH=src uv run python -m nlfr compare history \
  --db data/canvas-dev/nlfr.sqlite \
  --output apps/canvas/public/projections/run-history.json
```

Redact raw DB paths before committing fixtures. The committed
[`run-history.json`](../../../apps/canvas/public/projections/run-history.json)
lists `canvas-dev` and `agent-bugfix-1` with bounded proof summaries.

Open the View Composer drawer (`data-testid="composer-drawer"`) to see the
picker helper text when history JSON is loaded.

## Pairwise compare vs history

| Export | `projection_kind` | Use when |
|--------|-------------------|----------|
| `compare export` | `compare` | Delta between exactly two groups |
| `compare history` | `run_history` | Browse all indexed groups + summaries |

Use compare export for the Compare Runs lens; use history for browsing many runs
without picking a left/right pair first.

## Verify

```bash
uv run pytest -q tests/test_compare_history.py tests/test_compare.py
```

## Related

- M9 compare: [Export and compare run groups](export-and-compare-run-groups.md)
- [Usefulness roadmap § Gap 2](../../USEFULNESS_ROADMAP.md) — multi-run history
- [Retention policy](../../../src/nlfr/retention_policy.py) — `index_only`, `no_auto_purge`
