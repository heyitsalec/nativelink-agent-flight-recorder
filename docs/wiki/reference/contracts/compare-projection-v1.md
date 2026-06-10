# Reference: compare projection v1

**Quadrant:** Reference · **Audience:** operators comparing run groups, canvas Compare lens authors

A compare projection summarizes **deltas** between two run groups. It is always
`derived_v1`: values are computed from proof packet summaries and SQLite run
rows — never from live scheduler or fleet APIs.

There is no separate JSON Schema file yet; this page is the implementation
contract aligned with
[`src/nlfr/projectors/compare.py`](../../../../src/nlfr/projectors/compare.py).

Export:

```bash
python3 -m nlfr compare export --left <group-a> --right <group-b> \
  --db data/nlfr/nlfr.sqlite --output compare-projection.json
```

← [Contracts index](README.md) · [Proof packet v1](proof-packet-v1.md) · [How-to: export and compare](../../how-to/export-and-compare-run-groups.md)

## Root object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | integer | yes | Must be `1` |
| `projection_kind` | string | yes | Must be `compare` |
| `generated_at` | string | yes | ISO-8601 UTC timestamp |
| `left_run_group` | string | yes | Baseline run group |
| `right_run_group` | string | yes | Comparison run group |
| `summary` | object | yes | Dimension and count summary |
| `dimensions` | array | yes | Five compare dimensions (fixed order) |
| `source_kind` | enum | yes | Always `derived_v1` at root |
| `confidence` | enum | yes | Typically `medium` at root |
| `evidence_refs` | string[] | yes | `run_group:<left>` and `run_group:<right>` |
| `redaction_state` | enum | yes | Typically `safe` |

### `summary` fields

| Key | Type | Meaning |
|-----|------|---------|
| `dimensions` | integer | Always `5` |
| `left_runs` | integer | Run rows for left group |
| `right_runs` | integer | Run rows for right group |
| `left_artifacts` | integer | From left proof packet `summary.artifacts` |
| `right_artifacts` | integer | From right proof packet `summary.artifacts` |

## Compare dimension

Each dimension compares a facet of the two run groups.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Dimension id (see table below) |
| `title` | string | yes | Display title |
| `summary` | string | yes | One-line description |
| `left` | object | yes | Left-side values |
| `right` | object | yes | Right-side values |
| `delta` | object | yes | Computed deltas |
| `claims` | string[] | yes | Honest sentences for reviewers |
| `source_kind` | enum | yes | Always `derived_v1` |
| `confidence` | enum | yes | `medium` default; `high` when worker identity observed |
| `evidence_refs` | string[] | yes | Both `run_group:<name>` refs |
| `redaction_state` | enum | yes | Typically `safe` |

### Fixed dimensions (order)

| `id` | Title | Inputs | Key `delta` fields |
|----|-------|--------|-------------------|
| `run_counts` | Run Counts | Proof packet `summary.runs` | `runs` (right − left) |
| `cache_metrics` | Cache Metrics | Proof block `cache.metrics` | `hits`, `misses`, `hit_rate` |
| `worker_identity` | Worker Identity | Block `remote_execution.metrics.worker_identity_observed` | `worker_identity_observed_changed` |
| `agent_provenance` | Agent Provenance | `agent_provenance` proof blocks | `present_changed`, `block_count_delta` |
| `status_deltas` | Status Deltas | SQLite `runs.status` counts | `by_status`, `changed` |

### `cache_metrics` shape

**`left.metrics` / `right.metrics`:**

| Key | Type |
|-----|------|
| `hits` | integer |
| `misses` | integer |
| `unknown` | integer |
| `hit_rate` | float \| omitted |

**`delta`:** `hits`, `misses`, `hit_rate` (right − left; `hit_rate` omitted when unknown).

### `worker_identity` honesty

Claims state explicitly that worker identity is true only when direct worker admin
evidence exists in the proof packet (M7). `confidence` is `high` when either side
observed identity; otherwise `medium`.

### `agent_provenance` block summaries

When present, `left.blocks` / `right.blocks` list redacted summaries:

| Field | Meaning |
|-------|---------|
| `id` | Proof block id |
| `title` | Block title |
| `model` | Agent model label |
| `prompt_sha256_prefix` | First 12 hex chars of prompt hash |
| *truth fields* | Copied from the proof block |

Never includes raw prompts.

### `status_deltas.by_status`

Per status key:

```json
{
  "completed": { "left": 1, "right": 1, "delta": 0 }
}
```

## Example (redacted)

Canonical fixture:
[`tests/fixtures/compare/compare-projection.json`](../../../../tests/fixtures/compare/compare-projection.json)

Excerpt — cache metrics dimension:

```json
{
  "id": "cache_metrics",
  "title": "Cache Metrics",
  "summary": "Cache hit/miss counts and hit rates from recorded Bazel evidence.",
  "left": {
    "metrics": { "hits": 1, "misses": 0, "hit_rate": 1.0, "unknown": 0 }
  },
  "right": {
    "metrics": { "hits": 2, "misses": 1, "hit_rate": 0.6666666666666666, "unknown": 0 }
  },
  "delta": { "hits": 1, "misses": 1, "hit_rate": -0.33333333333333337 },
  "claims": [
    "Cache metrics are derived from proof packet cache blocks only.",
    "Left: 1 hit(s), 0 miss(es).",
    "Right: 2 hit(s), 1 miss(es).",
    "Hit rate delta is -33.33%."
  ],
  "source_kind": "derived_v1",
  "confidence": "medium",
  "evidence_refs": ["run_group:fixture-left", "run_group:fixture-right"],
  "redaction_state": "safe"
}
```

Input proof packets for the fixture:

- [`left-proof.json`](../../../../tests/fixtures/compare/left-proof.json)
- [`right-proof.json`](../../../../tests/fixtures/compare/right-proof.json)

## Run group index

`python3 -m nlfr compare index` returns retention rows (not a compare projection):

| Field | Meaning |
|-------|---------|
| `run_group` | Group label |
| `run_count` | Runs in group |
| `first_started_at` | Earliest run timestamp |
| `last_started_at` | Latest run timestamp |

## Proof samples

Compare is `derived_v1` over existing proof packets. Ground individual legs with:

| Sample | Use as compare leg |
|--------|-------------------|
| [`cold-warm-summary.json`](../../../proof-samples/cold-warm-summary.json) | Cache economics baseline |
| [`agent-bugfix-summary.json`](../../../proof-samples/agent-bugfix-summary.json) vs [`agent-feature-summary.json`](../../../proof-samples/agent-feature-summary.json) | Agent provenance delta |

No committed compare sample in `docs/proof-samples/` yet — run
`scripts/compare-proof.sh` locally or use the fixture above.

## Out of scope

Compare projection does **not**:

- Merge two action graphs into one canvas topology.
- Claim scheduler assignment, queue time, or fleet load distribution.
- Introduce new `collectable_v1` evidence — only summarizes ingested proof packets.

## Related

- [Truth labels § Compare claims](../truth-labels.md#compare-claims-m9)
- [Compare projection flow diagram](../../../diagrams/compare-projection-flow.md)
- CLI: [compare export](../cli.md#compare-m9)
- Tests: [`tests/test_compare.py`](../../../../tests/test_compare.py)
