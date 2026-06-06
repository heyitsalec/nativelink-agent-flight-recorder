# NativeLink Agent Flight Recorder

A local-first proof recorder for AI/simulated-agent code validation with
NativeLink and Bazel.

The MVP records real build/test/cache evidence, stores it in SQLite, exports
truth-labeled projection JSON, and renders a sparse Action Graph canvas from
that projection.

![Action Graph canvas rendered from fixture-backed projection JSON (simulated_v1)](docs/images/canvas-desktop.png)

The canvas is not a dashboard over invented state. It renders only projection
JSON produced from the recorder's SQLite evidence spine. Screenshots below are
fixture-backed (`simulated_v1`) canvas renders; see Truth Labels. The same run
can be inspected through the agent-loop focus and Proof Packet:

![Agent-loop focus rendered from fixture projection JSON (simulated_v1)](docs/images/canvas-agent-loop.png)

![Proof Packet view rendered from fixture projection JSON (simulated_v1)](docs/images/canvas-proof.png)

## V1 Thesis

NativeLink is strongest in this tryout when the demo proves a real loop:

1. run a small Bazel workload through a NativeLink cache path;
2. capture Bazel and NativeLink artifacts immutably;
3. normalize the evidence into SQLite;
4. generate a proof packet explaining what happened and what can be trusted;
5. visualize the same evidence as an Action Graph.

## Scope

In scope:

- Python recorder CLI
- SQLite evidence spine
- immutable artifact manifest
- Bazel BEP/stdout/profile/execution-log ingestion
- NativeLink config/log capture
- projection JSON
- proof packet export
- controlled simulated-agent provenance
- sparse canvas consuming projection JSON

Out of scope for v1:

- SaaS/auth/billing/multi-tenancy
- full remote execution fleet story
- worker/scheduler dashboard
- OTLP/Jaeger clone
- persistent worker security claims
- production AI-agent identity/auth integrations
- unsupported worker/action/queue-time correlation

## Implementation Plan

See [docs/IMPLEMENTATION_DAG.md](docs/IMPLEMENTATION_DAG.md).
For the tryout-facing summary of the current worker-first proof, see
[docs/TRYOUT_PACKET.md](docs/TRYOUT_PACKET.md).

## Quick Start

Requirements: `uv`, Python 3.11+, Node/npm for the canvas app.

Bootstrap once:

```bash
uv sync
npm --prefix apps/canvas install
```

### Path A — 5-minute evaluator (no Nix)

Fixture-backed canvas demo without Bazel or NativeLink on PATH:

```bash
uv run pytest tests -q
npm --prefix apps/canvas run dev -- --host 127.0.0.1
```

Open the dev server and inspect Action Graph / Proof Packet from committed
fixture projections under `apps/canvas/public/projections/`. This path uses
`simulated_v1` evidence — not real NativeLink execution.

### Path B — Real NativeLink proof (Nix)

Outside `nix develop`, real-tool scripts record truth-labeled
`environment_blocker` evidence. Inside Nix (NativeLink 1.3.2, Bazel 9.1.1) the
recorder has proven cold/warm cache, one-process local-exec, live two-worker
endpoint readiness, and agent-loop closure:

```bash
nix develop
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w \
  scripts/local-exec-proof.sh
scripts/agent-loop-proof.sh
```

These write `summary.json` evidence under `data/cold-warm-proof/`,
`data/local-exec-proof/`, `data/local-exec-proof-2w/`, and
`data/agent-loop-proof/`. The two-worker run proves two workers configured AND
endpoints opened live (`worker_endpoints_ready`, `expected_workers=2`) — not
work distributed across two workers.

See [docs/DEV_ENVIRONMENT.md](docs/DEV_ENVIRONMENT.md) for prerequisites (~82GB
disk for first proof run, Nix with flakes).

### Full verifier

```bash
scripts/verify-demo.sh
```

Runs backend tests, doctor, real-tool smoke (blocker or success), cold/warm,
local-exec, simulated-agent provenance, fixture ingest, projection exports, and
canvas build. Use after either path above.

Tryout narrative: [docs/TRYOUT_PACKET.md](docs/TRYOUT_PACKET.md) · One-pager:
[docs/ONE_PAGER.md](docs/ONE_PAGER.md) · Demo script:
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · Redacted proof samples:
[docs/proof-samples/](docs/proof-samples/)

## CLI Flow

Fixture-backed proof path:

```bash
PYTHONPATH=src uv run python -m nlfr ingest \
  --database data/demo-proof/nlfr.sqlite \
  --run-key fixture-run:cache-only \
  --run-group latest \
  --bep tests/fixtures/bazel/bep.jsonl \
  --execution-log tests/fixtures/bazel/execution-log.json \
  --profile tests/fixtures/bazel/profile.json \
  --source-kind simulated_v1 \
  --json

PYTHONPATH=src uv run python -m nlfr graph export \
  --db data/demo-proof/nlfr.sqlite \
  --run-group latest \
  --output apps/canvas/public/projections/action-graph.json
```

Real local cache-only smoke, when tools are installed:

```bash
PYTHONPATH=src uv run python -m nlfr run \
  --scenario local-tool-check \
  --run-group tool-check \
  --workspace demo/bazel-monorepo \
  --output-dir data/tool-check \
  //tasks:priority_test
```

Cold/warm NativeLink cache proof, inside `nix develop` or the devcontainer:

```bash
scripts/cold-warm-cache-proof.sh
```

This starts a NativeLink cache-only server, runs the demo Bazel target twice
with separate Bazel output bases, and exports `run_group=cold-warm` projections.

Local remote execution proof, inside a Linux-like environment with Bazel and
NativeLink installed:

```bash
scripts/local-exec-proof.sh
```

This starts the experimental NativeLink local worker config, runs Bazel with
`--remote_executor`, ingests the resulting artifacts, and exports
`run_group=local-exec` projections. See
[docs/REMOTE_EXECUTION_PLAN.md](docs/REMOTE_EXECUTION_PLAN.md).

On hosts without Bazel or NativeLink, this path records durable
`environment_blocker` and `worker-readiness.json` evidence. That is a valid host
readiness result, not a successful worker-execution claim.

Simulated-agent provenance, without touching the source demo workspace:

```bash
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario safe-leaf-change \
  --output-dir data/agent-sim \
  --skip-run \
  --json
```

Remove `--skip-run` to invoke `nlfr run` after applying each copied-workspace
patch. Failed or blocked builds are recorded as outcomes tied to the simulated
agent and patch provenance. Add `--ingest` to auto-ingest a real run's Bazel
artifacts so validation and cache evidence join the same chain. The
`llm-bounded-patch` scenario carries bounded-LLM provenance fields — a `model`
label and a `prompt_sha256` (SHA-256 hash of the prompt). The raw prompt is
never stored or exported; only the hash. This is the reference pattern for real
agent provenance under the `AGENTS.md` privacy rule. As a fixture
(`simulated_v1`), it makes no live LLM call.

Agent-loop closure proof, inside `nix develop` or the devcontainer:

```bash
scripts/agent-loop-proof.sh
```

This applies the bounded `llm-bounded-patch` scenario to a copied workspace
(never the source), runs Bazel through the NativeLink cache, ingests
validation+cache evidence via `simulate --ingest`, and exports projections. The
Action Graph then shows the chain `agent → (authored_change) → change →
(validated_by) → run → evaluated_target → target → produced_action → action →
observed_cache_event → cache_event`. It writes `data/agent-loop-proof/summary.json`
with `chain_complete=true` and `source_kind: collectable_v1`. The graph
projector derives the `agent` node from the `agent_provenance` proof block and
the `changes` table, with edge kinds `authored_change` and `validated_by`. The
fixture (no-Nix) canvas shows the same chain as `simulated_v1`:
`scripts/verify-demo.sh` simulates `llm-bounded-patch` into `run_group=latest`,
then attaches fixture Bazel evidence to the same run, so the committed
`apps/canvas/public/projections/action-graph.json` includes the agent and change
nodes.

Canvas:

```bash
npm --prefix apps/canvas install
npm --prefix apps/canvas run dev -- --host 127.0.0.1
```

Visual proof capture, with the canvas server running:

```bash
CANVAS_URL=http://127.0.0.1:5174/ npm --prefix apps/canvas run capture
```

The capture script writes desktop, proof, remote-boundary, failure-focus,
agent-loop, mobile, and WebM operator-flow artifacts under ignored
`output/playwright/`.

## Truth Labels

Every normalized evidence row and projection object carries:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, `future`, or `unknown`
- `confidence`: `high`, `medium`, `low`, or `unknown`
- `evidence_refs`: artifact or fixture references backing the claim
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`

Fixture-backed records use `simulated_v1`. Profile-derived cache observations
use `derived_v1` with medium or low confidence. Real local process outputs from
`nlfr run` use `collectable_v1`.

## Unsupported Claims

V1 does not claim:

- remote worker assignment;
- queue time;
- action placement;
- worker identity;
- scheduler assignment;
- load distribution;
- full remote execution fleet behavior;
- opaque SaaS telemetry;
- exact BEP action correlation when the source artifact does not contain it;
- production AI-agent identity or auth.

This is intentional. The MVP proves the evidence path first: collect, label,
normalize, project, and inspect.

## Test Plan

Per `STD-real-backends`, real-tool paths are exercised when installed and report
explicit environment blockers otherwise. Per `STD-test-assertions`, tests assert
observable rows, labels, and exported fields instead of only checking that
commands run. Per `STD-e2e-ui` and `STD-screenshots`, Playwright captures the
canvas desktop, proof, failure-focus, mobile, and WebM operator flow.
