# NativeLink Agent Flight Recorder

**A local-first proof recorder for AI-agent validation loops with NativeLink and Bazel.**

NLFR captures immutable build evidence, normalizes it into SQLite, exports
truth-labeled projection JSON, and renders a sparse Action Graph canvas from
that projection only — never from invented backend state.

<p align="center">
  <img src="docs/media/nlfr-canvas-tour.gif" alt="NLFR canvas tour: Action Graph, Proof Packet, Compare Runs, and operator command" width="100%">
  <br>
  <sub><strong>Action Graph canvas:</strong> inspect the graph, proof packet, compare lens, and operator command from projection JSON.</sub>
  <br><br>
  <img src="docs/media/nlfr-evidence-loop.gif" alt="NLFR evidence loop: record, ingest, export, and project with truth labels" width="100%">
  <br>
  <sub><strong>Evidence loop:</strong> run Bazel through NativeLink, ingest artifacts, export projections, and inspect proof.</sub>
</p>

The public repo is credential-free and fixture-safe. Hero GIFs are generated from
committed projections; the Nix proof path produces `collectable_v1` evidence when
NativeLink and Bazel are available on the host.

## The Loop

Agent validation gets hard to trust when the truth is scattered across chat
threads, CI logs, cache hits, and half-remembered build outcomes. NLFR turns
that scattered work into one loop:

1. **Record.** Run a Bazel workload through a NativeLink cache or local-exec
   path; capture Bazel BEP, stdout, profile, execution log, and NativeLink
   config/log artifacts immutably with SHA-256 hashes.
2. **Ingest.** Normalize artifacts into SQLite with idempotent keys, stable
   run groups, and four truth labels on every row.
3. **Project.** Export versioned projection JSON and proof packets — Action
   Graph nodes, edges, metrics, and claims carry `source_kind`, `confidence`,
   `evidence_refs`, and `redaction_state`.
4. **Inspect.** The sparse canvas renders only from projection JSON: Action
   Graph, Proof Packet, Remote Boundary, failure focus, and agent-loop chain.
5. **Compare.** Export compare projections across run groups to contrast cold
   vs warm cache, fixture vs dogfood, or successive proof runs without
   re-running the workload.

## What You Get

| Surface | What it shows |
| --- | --- |
| Python recorder CLI | `nlfr run`, `ingest`, `graph export`, `proof export`, `compare export`, `simulate`, and `doctor` over the evidence spine. |
| SQLite evidence spine | Immutable artifact manifest, idempotent ingest, Bazel/NativeLink parsers, and truth-labeled rows. |
| Projection JSON | Action Graph, proof packet, compare lens, and runway exports consumed by the canvas and proof scripts. |
| Sparse canvas | Vite/React app under `apps/canvas/` that renders projection JSON only — no invented scheduler or worker state. |
| Public demo media | Hero GIFs and still frames under `docs/media/` and `docs/images/` generated from fixture or dogfood projections. |
| Unified docs | Architecture track, adoption paths, proof samples, CI recipe, media capture, and reviewer routes. |
| Proof lane | `pytest`, `./scripts/verify-demo.sh`, Nix proof scripts, and GitHub Actions on Linux/x86_64. |

Still frames from the same projection sources as the tour GIF:

- [Desktop Action Graph](docs/images/canvas-desktop.png)
- [Agent-loop focus](docs/images/canvas-agent-loop.png)
- [Proof Packet](docs/images/canvas-proof.png)
- [Failure focus](docs/images/canvas-failure-focus.png)
- [Remote boundary](docs/images/canvas-remote-boundary.png)
- [Mobile layout](docs/images/canvas-mobile.png)

See [docs/media/README.md](docs/media/README.md) for GIF and still-frame inventory.

## Run Locally

Requirements: `uv`, Python 3.11+, Node/npm for the canvas app. No environment
variables are required for the fixture path.

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

Fixture-backed ingest and export:

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

Simulated-agent provenance (no source workspace mutation):

```bash
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario safe-leaf-change \
  --output-dir data/agent-sim \
  --skip-run \
  --json
```

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

Real local cache-only smoke, when tools are installed:

```bash
PYTHONPATH=src uv run python -m nlfr run \
  --scenario local-tool-check \
  --run-group tool-check \
  --workspace demo/bazel-monorepo \
  --output-dir data/tool-check \
  //tasks:priority_test
```

On hosts without Bazel or NativeLink, real-tool paths record durable
`environment_blocker` evidence. That is a valid host readiness result, not a
successful worker-execution claim.

See [docs/DEV_ENVIRONMENT.md](docs/DEV_ENVIRONMENT.md) for prerequisites (~82GB
disk for first proof run, Nix with flakes).

### Canvas dev

Default dev projection is `canvas-dev` (`collectable_v1` dogfood). Fixture
fallback banner appears when projections are missing.

```bash
npm --prefix apps/canvas install
npm --prefix apps/canvas run dev -- --host 127.0.0.1
```

### Full verifier

```bash
scripts/verify-demo.sh
```

Runs backend tests, doctor, real-tool smoke (blocker or success), cold/warm,
local-exec, simulated-agent provenance, fixture ingest, projection exports, and
canvas build. Use after either path above.

Proof commands (canonical spine):

```bash
python3 -m pytest
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

Visual proof capture, with the canvas server running:

```bash
CANVAS_URL=http://127.0.0.1:5174/ npm --prefix apps/canvas run capture
```

Regenerate hero GIFs:

```bash
npm --prefix apps/canvas run capture:heroes
```

See [docs/MEDIA_CAPTURE.md](docs/MEDIA_CAPTURE.md) for capture prerequisites and
scene design.

## Architecture

NLFR ships as one repo because the evidence path only makes sense together:

- [`src/nlfr/`](src/nlfr/) is the Python recorder: artifact manifest, SQLite
  ingest, Bazel/NativeLink parsers, projectors, and CLI.
- [`apps/canvas/`](apps/canvas/) is the sparse Action Graph canvas. It consumes
  projection JSON only and must not invent backend state.
- [`docs/`](docs/) is the review spine: architecture track, adoption paths,
  proof samples, CI recipe, and reviewer routes.
- [`scripts/`](scripts/) are the proof lane: cold/warm, local-exec, agent-loop,
  verify-demo, and canvas build helpers.

See [docs/INDEX.md](docs/INDEX.md) for the two-hop review map and
[docs/ONE_PAGER.md](docs/ONE_PAGER.md) for thesis, proven claims, and explicit
unproven boundaries.

## Truth Labels And Public-Safe Guarantees

Every normalized evidence row and projection object carries:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, `future`, or
  `unknown`
- `confidence`: `high`, `medium`, `low`, or `unknown`
- `evidence_refs`: artifact or fixture references backing the claim
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`

Fixture-backed records use `simulated_v1`. Profile-derived cache observations
use `derived_v1` with medium or low confidence. Real local process outputs from
`nlfr run` and Nix proof scripts use `collectable_v1`.

Real:

- the Python recorder, SQLite schema, and projection projectors;
- the sparse canvas rendering projection JSON only;
- Nix proof scripts and redacted `summary.json` samples under `docs/proof-samples/`;
- truth-label enforcement on every exported node, edge, metric, and claim.

Fixture or simulated:

- committed canvas projections used for the 5-minute evaluator path;
- hero GIFs and still frames generated from fixture or dogfood projections;
- deterministic simulated-agent scenarios (`llm-bounded-patch` carries a model
  label and `prompt_sha256` only — raw prompts are never stored or exported).

Excluded from this repo:

- secrets, credentials, raw private logs, environment variables, raw prompts,
  customer data, and private legacy GUI/source material.

V1 does not claim remote worker assignment, queue time, action placement,
worker identity, scheduler assignment, load distribution, full remote execution
fleet behavior, opaque SaaS telemetry, or exact BEP action correlation when the
source artifact does not contain it.

## Review Path

1. Start with the [docs index](docs/INDEX.md) for the two-hop review map.
2. Read [docs/ONE_PAGER.md](docs/ONE_PAGER.md) for thesis, proven vs unproven
   claims, and evaluator paths.
3. Read [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) for the guided tour from
   commands to canvas and proof artifacts.
4. Read [docs/ADOPTION_GUIDE.md](docs/ADOPTION_GUIDE.md) for the 5-minute fixture
   path and 30-minute Nix proof path on an independent host.
5. Review [docs/ARCHITECTURE_TRACK.md](docs/ARCHITECTURE_TRACK.md) for milestone
   gates and the evidence-before-narrative rule.

## Status And Limits

NLFR v1 is an evidence-first recorder MVP, not a hosted SaaS, multi-tenant
control plane, or full remote-execution fleet dashboard.

In scope: Python recorder CLI, SQLite evidence spine, artifact manifest, Bazel
BEP/stdout/profile/execution-log ingestion, NativeLink config/log capture,
projection JSON, proof packet export, controlled simulated-agent provenance, and
sparse canvas consuming projection JSON.

Out of scope for v1: SaaS/auth/billing/multi-tenancy, full remote execution
fleet story, worker/scheduler dashboard, OTLP/Jaeger clone, persistent worker
security claims, production AI-agent identity/auth integrations, and unsupported
worker/action/queue-time correlation.

Implementation plan: [docs/IMPLEMENTATION_DAG.md](docs/IMPLEMENTATION_DAG.md).
Tryout narrative: [docs/TRYOUT_PACKET.md](docs/TRYOUT_PACKET.md).

## Contributing

NLFR is intentionally conservative:

- public artifacts must stay fixture-safe and credential-free;
- the recorder owns durable evidence and projection authority;
- the canvas must not invent backend state or write directly to SQLite;
- parser, projector, and truth-label changes need fixture-backed tests;
- user-visible UI changes should include screenshot or media proof.

Start with [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before changing code.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
