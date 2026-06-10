## NLFR Proof Summary

**Run group:** `record-proof`  
**Generated:** 2026-06-06T12:00:00.000000Z  
**Export labels:** `derived_v1` · `high` · `safe`

| Metric | Count |
|--------|------:|
| actions | 0 |
| artifacts | 0 |
| cache_events | 1 |
| failures | 0 |
| runs | 1 |
| targets | 1 |

### Evidence paths

- **DB:** `<repo>/data/record-proof/nlfr.sqlite`
- **Manifest:** `<repo>/data/record-proof/artifact_manifest.json`
- **Graph JSON:** `<repo>/data/record-proof/projections/graph-projection.json`
- **Proof JSON:** `<repo>/data/record-proof/projections/proof-packet.json`
- **Runway JSON:** `<repo>/data/record-proof/projections/runway-projection.json`

### Validation status

- **Status:** ok
- **Failures:** 0

---

### Proof Scope

**Labels:** `collectable_v1` · `high` · `safe`

Local recorded evidence for AI-generated code validation (cache-only mode).

**Claims:**
- This packet can prove recorded commands, artifacts, statuses, and cache events present in the local evidence spine. (`collectable_v1` / `high`)
- This packet does not claim remote worker assignment, queue timing, or opaque SaaS telemetry. (`collectable_v1` / `high`)

**Evidence refs:** `run:record-proof`

### Invocation Results

**Labels:** `collectable_v1` · `high` · `safe`

NativeLink and Bazel command outcomes captured by the recorder.

**Metrics:**
- `unknown`: 1

**Evidence refs:** `artifact:bazel.stdout.txt`

### Cache Evidence

**Labels:** `derived_v1` · `medium` · `safe`

Cache hit/miss records extracted from available Bazel evidence.

**Metrics:**
- `hit_rate`: 1.0
- `hits`: 1
- `misses`: 0
- `unknown`: 0

**Evidence refs:** `execution-log:test`

### Remote Execution Boundary

**Labels:** `future` · `unknown` · `unknown`

No Bazel remote execution configuration was observed in recorded invocations.

**Metrics:**
- `queue_time_observed`: false
- `remote_executor_endpoints`: 0
- `remote_executor_invocations`: 0
- `remote_executor_overrides`: 0
- `scheduler_assignment_observed`: false
- `worker_identity_observed`: false

**Claims:**
- Remote execution configuration evidence requires a recorded invocation with --remote_executor. (`future` / `unknown`)
- Worker proof requires direct worker log or admin evidence. (`future` / `unknown`)

**Unsupported claims:** `worker_identity`, `action_placement`, `queue_time`, `scheduler_assignment`, `load_distribution`
_Boundary labels only — export continues; these are not validation failures._

### Validation Surface

**Labels:** `collectable_v1` · `high` · `safe`

Targets, actions, and failures visible to the recorder.

**Metrics:**
- `actions`: 0
- `failures`: 0
- `targets`: 1

**Evidence refs:** `bep:target-completed`

### Artifact Chain

**Labels:** `future` · `unknown` · `unknown`

Immutable files referenced by the proof packet.

**Metrics:**
- `artifacts`: 0

### Agent Provenance: demo-agent

**Labels:** `collectable_v1` · `high` · `safe`

Bounded agent provenance for PR markdown export.

**Agent provenance (hash-only):**
- name: `demo-agent`
- model: `composer-2.5`
- prompt_sha256: `aaaaaaaaaaaa…`

**Evidence refs:** `agent-provenance:record-proof`

_Projection export only. Claims carry `source_kind`, `confidence`, `evidence_refs`, and `redaction_state`. No raw prompts or private logs._
