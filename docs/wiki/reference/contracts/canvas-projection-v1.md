# Reference: canvas projection v1

**Quadrant:** Reference · **Audience:** canvas authors, UI contributors, proof reviewers

The canvas projection (action graph) is the JSON input for the sparse TypeScript
canvas. The UI renders **only** this file — it does not query SQLite or invent
backend state.

Schema: [`contracts/canvas_projection.v1.json`](../../../../contracts/canvas_projection.v1.json)  
Projector: [`src/nlfr/projectors/graph.py`](../../../../src/nlfr/projectors/graph.py)  
Export: `python3 -m nlfr graph export --run-group <group>`

← [Contracts index](README.md) · [Projection-only canvas](../../explanation/projection-only-canvas.md)

## Root object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | integer | yes | Must be `1` |
| `projection_kind` | string | yes | Must be `action_graph` |
| `generated_at` | string | yes | ISO-8601 UTC timestamp |
| `run_group` | string | yes | Run group label |
| `summary` | object | yes | Counts and status histograms |
| `nodes` | array | yes | Graph nodes |
| `edges` | array | yes | Directed edges |

### `summary` fields

| Key | Meaning |
|-----|---------|
| `runs` | Run count |
| `nodes` | Total node count |
| `edges` | Total edge count |
| `invocation_statuses` | Status histogram for invocations |
| `target_statuses` | Status histogram for targets |
| `cache_events` | Cache event count |
| `failures` | Failure count |
| `changes` | Agent change count |
| `agents` | Agent node count (M8) |

## Truth labels on nodes and edges

Both nodes and edges merge the shared `truth` definition with graph fields.
Every node and edge requires:

| Field | Type | Required |
|-------|------|----------|
| `source_kind` | enum | yes |
| `confidence` | enum | yes |
| `evidence_refs` | string[] | yes |
| `redaction_state` | enum | yes |

See [truth labels](../truth-labels.md) for enum values and review rules.

## Node

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable node id |
| `kind` | string | yes | Node kind (see table below) |
| `label` | string | yes | Display label |
| `status` | any | no | Run/invocation status or exit code |
| `payload` | object | no | Redacted row fields (commands sanitized) |

### Node kinds emitted by projector

| `kind` | Source rows | Notes |
|--------|-------------|-------|
| `run` | `runs` | One per recorded run |
| `agent` | `proof_blocks` (`agent_provenance`) | `model` + `prompt_sha256` only |
| `change` | `changes` | Linked from agent via `authored_change` |
| `invocation` | `invocations` | Bazel/NativeLink commands |
| `remote_execution_config` | derived from invocations | `configured_only: true` unless worker observed |
| `worker` | M7 stdout events | `collectable_v1` when admin regex matches |
| `artifact` | `artifacts` | Manifest-backed files |
| `target` | `targets` | Bazel targets |
| `action` | `actions` | Bazel actions |
| `cache_event` | `cache_events` | Hit/miss evidence |
| `failure` | `failures` | Validation failures |
| `graph_node` | `graph_nodes` | Explicit fixture/scenario nodes |

## Edge

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable edge id |
| `from` | string | yes | Source node id |
| `to` | string | yes | Target node id |
| `kind` | string | yes | Edge kind |
| `payload` | any | no | Optional metadata |
| *truth fields* | — | yes | Same four fields as nodes |

### Common edge kinds

| `kind` | Meaning |
|--------|---------|
| `authored_change` | Agent → change (M8) |
| `validated_by` | Change → run |
| `recorded_invocation` | Run → invocation |
| `configured_remote_execution` | Invocation → remote config |
| `observed_worker_identity` | Remote config → worker (M7) |
| `recorded_artifact` | Run → artifact |
| `evaluated_target` | Run → target |
| `produced_action` | Target/run → action |
| `observed_cache_event` | Parent → cache event |
| `observed_failure` | Run → failure |

## Example node (redacted)

Agent node from M8 ingest — prompt hash only:

```json
{
  "id": "agent:proof_blocks_a5b173bec1a0f92997baf9d2",
  "kind": "agent",
  "label": "compare-fixture-agent",
  "status": "completed",
  "payload": {
    "agent_kind": "cursor_adapter_v1",
    "agent_name": "compare-fixture-agent",
    "model": "composer-2.5",
    "prompt_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "change_class": "bugfix"
  },
  "source_kind": "collectable_v1",
  "confidence": "high",
  "evidence_refs": ["agent-provenance:fixture-right"],
  "redaction_state": "safe"
}
```

Remote executor args in invocation payloads are sanitized (endpoints redacted).

## Proof samples

Ground-truth run summaries that feed graph projection:

| Sample | Chain proved |
|--------|--------------|
| [`agent-loop-summary.json`](../../../../proof-samples/agent-loop-summary.json) | `agent → change → run → target → action → cache_event` |
| [`agent-bugfix-summary.json`](../../../../proof-samples/agent-bugfix-summary.json) | Tier 1 Act 1 live Bazel validation |
| [`two-worker-summary.json`](../../../../proof-samples/two-worker-summary.json) | Remote config nodes; worker identity conditional |

## Out of scope

The action graph does **not** represent:

- Live worker queues or scheduler placement.
- Cross-run-group unified topology (use [compare projection v1](compare-projection-v1.md)).
- Metrics invented at render time — all values come from projection JSON.

## Related

- [Projection-only canvas](../../explanation/projection-only-canvas.md)
- [Canvas projection boundary diagram](../../../../diagrams/canvas-projection-boundary.md)
- [Design: routing](../../../../design/routing.md) — canvas mode lenses
- CLI: [graph export](../cli.md#graph-export)
