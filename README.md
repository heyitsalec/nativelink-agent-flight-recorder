# NativeLink Agent Flight Recorder

A local-first proof recorder for AI/simulated-agent code validation with
NativeLink and Bazel.

The MVP records real build/test/cache evidence, stores it in SQLite, exports
truth-labeled projection JSON, and renders a sparse Action Graph canvas from
that projection.

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

Requirements:

- `uv`
- Python 3.11+
- Node/npm for the canvas app
- Optional for real cache-only smoke: `bazel`/`bazelisk` and `nativelink`/`native-link`

```bash
uv run pytest tests -q
scripts/verify-demo.sh
```

`scripts/verify-demo.sh` runs the available proof path:

1. backend tests;
2. `nlfr doctor --mode cache-only`;
3. a real-tool `nlfr run` smoke that records an `environment_blocker` if Bazel or NativeLink is missing;
4. cold/warm NativeLink cache proof when tools are available, or a recorded blocker otherwise;
5. simulated-agent provenance in a copied demo workspace;
6. fixture-backed Bazel ingest;
7. Action Graph, Validation Runway, and Proof Packet exports;
8. canvas build.

On this machine the real cache-only smoke is blocked because Bazel and
NativeLink are not on PATH. That is recorded as evidence, not treated as a
success.

For the reproducible environment that installs Bazel/Bazelisk and NativeLink,
use [docs/DEV_ENVIRONMENT.md](docs/DEV_ENVIRONMENT.md).

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
agent and patch provenance.

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
mobile, and WebM operator-flow artifacts under ignored `output/playwright/`.

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
