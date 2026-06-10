# Reference: proof packet v1

**Quadrant:** Reference · **Audience:** proof reviewers, compare lens authors, evaluators

A proof packet is a versioned JSON projection of everything NLFR can honestly
claim about one **run group** after SQLite ingest. Export via
`python3 -m nlfr proof export --run-group <group>`.

Schema: [`contracts/proof_packet.v1.json`](../../../../contracts/proof_packet.v1.json)  
Projector: [`src/nlfr/projectors/proof.py`](../../../../src/nlfr/projectors/proof.py)

← [Contracts index](README.md) · [Canvas projection v1](canvas-projection-v1.md)

## Root object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | integer | yes | Must be `1` |
| `projection_kind` | string | yes | Must be `proof_packet` |
| `generated_at` | string | yes | ISO-8601 UTC timestamp |
| `run_group` | string | yes | Run group label |
| `summary` | object | yes | Counts: `runs`, `artifacts`, `targets`, `actions`, `cache_events`, `failures` |
| `blocks` | array | yes | Ordered proof blocks (see below) |

## Proof block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable block id (`scope`, `cache`, `remote_execution`, …) |
| `kind` | string | yes | Block kind (`derived_summary`, `agent_provenance`, …) |
| `title` | string | yes | Human title |
| `summary` | string \| null | yes | One-line scope statement |
| `claims` | string[] | no | Honest claim sentences |
| `metrics` | object | no | Numeric summaries |
| `payload` | any | no | Structured detail (endpoints, legs, agent metadata) |
| `source_kind` | enum | yes | Truth label |
| `confidence` | enum | yes | Truth label |
| `evidence_refs` | string[] | yes | Truth label |
| `redaction_state` | enum | yes | Truth label |

Every block requires all four truth fields. Stored `proof_blocks` rows from M8
ingest are appended verbatim after the derived blocks.

## Standard derived blocks

The projector always emits these blocks (empty evidence yields `future` / `unknown` labels):

| `id` | Title | Primary evidence | Compare uses |
|------|-------|------------------|--------------|
| `scope` | Proof Scope | `runs` | — |
| `invocations` | Invocation Results | `invocations` | — |
| `cache` | Cache Evidence | `cache_events` | `cache_metrics` dimension |
| `cache_economics` | Cache Economics | multi-run cache legs | — (when ≥2 runs with scenarios) |
| `remote_execution` | Remote Execution Boundary | `invocations` + `proof_blocks` | `worker_identity` dimension |
| `validation` | Validation Surface | `targets`, `actions`, `failures` | — |
| `artifacts` | Artifact Chain | `artifacts` | — |

### `cache` metrics shape

| Key | Type | Meaning |
|-----|------|---------|
| `hits` | integer | Cache events with `hit == 1` |
| `misses` | integer | Cache events with `hit == 0` |
| `unknown` | integer | Events without hit classification |
| `hit_rate` | float \| omitted | `hits / (hits + misses)` when known |

### `remote_execution` conditional claims (M7)

`metrics.worker_identity_observed` is `true` only when:

1. A recorded invocation has `--remote_executor`, and
2. Direct worker admin stdout is attached pre-ingest with M7 regex match.

Without stdout, worker identity stays in `payload.unsupported_claims`. Queue time
and scheduler assignment are never claimed.

### Agent provenance blocks (M8)

Ingested blocks with `kind == "agent_provenance"` carry bounded payload:

- `agent.model`, `agent.prompt_sha256` — never raw prompts
- `change.patch_sha256`, `change.change_class`
- Truth labels from the sidecar ingest row

## Example block (redacted)

From [`tests/fixtures/compare/left-proof.json`](../../../../tests/fixtures/compare/left-proof.json):

```json
{
  "id": "cache",
  "kind": "derived_summary",
  "title": "Cache Evidence",
  "summary": "Cache hit/miss records extracted from available Bazel evidence.",
  "claims": [],
  "metrics": {
    "hits": 1,
    "misses": 0,
    "unknown": 0,
    "hit_rate": 1.0
  },
  "source_kind": "derived_v1",
  "confidence": "medium",
  "evidence_refs": ["execution-log:fixture-left"],
  "redaction_state": "safe"
}
```

## Proof samples

Real-run `summary.json` excerpts with truth labels:

| Sample | `source_kind` · `confidence` | Relevant blocks |
|--------|------------------------------|-----------------|
| [`cold-warm-summary.json`](../../../../proof-samples/cold-warm-summary.json) | `collectable_v1` · `high` | Cache economics, cold/warm legs |
| [`two-worker-summary.json`](../../../../proof-samples/two-worker-summary.json) | `collectable_v1` · `high` | Remote execution boundary |
| [`agent-loop-summary.json`](../../../../proof-samples/agent-loop-summary.json) | mixed · `high` | Agent provenance + validation |
| [`fleet-claims-matrix-sample.json`](../../../../proof-samples/fleet-claims-matrix-sample.json) | `derived_v1` · `high` | Unsupported claim policy |

## Out of scope

A proof packet does **not** prove:

- Scheduler assignment or queue timing (`future`).
- Fleet-wide cache performance or dollar savings.
- Live backend state — only ingested SQLite rows.

## Related

- [Truth labels](../truth-labels.md) — M7 conditional worker identity
- [Compare projection v1](compare-projection-v1.md) — reads `cache` and `remote_execution` blocks
- [Export and compare run groups](../../how-to/export-and-compare-run-groups.md)
