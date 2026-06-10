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
committed projections with truth labels visible. If `docs/media/*.gif` is missing
locally, regenerate after building the canvas:

```bash
npm --prefix apps/canvas run capture:heroes
```

See [docs/MEDIA_CAPTURE.md](docs/MEDIA_CAPTURE.md) for tier1-demo view and scene design.

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
   re-running the workload. See [Compare runs (M9)](docs/wiki/compare-runs.md).

## What You Get

| Surface | What it shows |
| --- | --- |
| Python recorder CLI | `nlfr run`, `ingest`, `graph export`, `proof export`, `compare export`, `simulate`, and `doctor` over the evidence spine. |
| SQLite evidence spine | Immutable artifact manifest, idempotent ingest, Bazel/NativeLink parsers, and truth-labeled rows. |
| Projection JSON | Action Graph, proof packet, compare lens, and runway exports consumed by the canvas and proof scripts. |
| Sparse canvas | Vite/React app under `apps/canvas/` that renders projection JSON only — no invented scheduler or worker state. |
| Proof lane | `pytest`, `./scripts/verify-demo.sh`, Nix proof scripts, and local gates. |

Still frames from the same projection sources: [docs/media/README.md](docs/media/README.md).

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

Full fixture ingest, export, and simulated-agent commands:
[docs/ADOPTION_GUIDE.md](docs/ADOPTION_GUIDE.md) (5-minute path).

### Path B — Real NativeLink proof (Nix)

Outside `nix develop`, real-tool scripts record truth-labeled
`environment_blocker` evidence. Inside Nix (NativeLink 1.3.2, Bazel 9.1.1) the
recorder has proven cold/warm cache, one-process local-exec, live two-worker
endpoint readiness, worker admin stdout (M7), agent-loop closure, tier1 live
Bazel, and LRE readiness probes:

```bash
nix develop
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w \
  scripts/local-exec-proof.sh
scripts/worker-evidence-proof.sh
scripts/agent-loop-proof.sh
./scripts/tier1-live-bazel-proof.sh
./scripts/lre-proof.sh
./scripts/lre-cold-warm-proof.sh
./scripts/lre-nix-toolchain-proof.sh
```

These write `summary.json` evidence under `data/cold-warm-proof/`,
`data/local-exec-proof/`, `data/worker-evidence-proof/`, `data/agent-loop-proof/`,
`data/tier1-live-bazel/`, and `data/lre-proof/`. The two-worker run proves two
workers configured AND endpoints opened live (`worker_endpoints_ready`,
`expected_workers=2`) — not work distributed across two workers.

**M7 worker identity (conditional):** when admin stdout rows are attached and
match the parser, projections promote `worker_identity` as `collectable_v1` with
`high` confidence (`worker-evidence-proof.sh` → `worker_identity_observed:
true`). Without direct stdout evidence, worker identity is not claimed.

On hosts without Bazel or NativeLink, real-tool paths record durable
`environment_blocker` evidence. That is a valid host readiness result, not a
successful worker-execution claim.

Prerequisites (~82GB disk for first proof run): [docs/DEV_ENVIRONMENT.md](docs/DEV_ENVIRONMENT.md).

### Tier 1 canvas preview

After `promote-tier1-compare.sh` or committed tier1 projections:

```bash
npm --prefix apps/canvas run preview
```

Open `http://127.0.0.1:4173/?view=tier1-demo` for the Compare lens with
`collectable_v1` dogfood pairs.

### Full verifier (local proof gates)

```bash
scripts/verify-demo.sh
```

Runs backend tests, doctor, real-tool smoke (blocker or success), cold/warm,
local-exec, worker-evidence, simulated-agent provenance, fixture ingest,
projection exports, and canvas build. Optional Nix scripts above extend the
same spine.

Canonical spine:

```bash
python3 -m pytest
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

CI reproduction recipe: [docs/CI_RECIPE.md](docs/CI_RECIPE.md).

## Truth Labels

Every normalized evidence row and projection object carries:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, `future`, or
  `unknown`
- `confidence`: `high`, `medium`, `low`, or `unknown`
- `evidence_refs`: artifact or fixture references backing the claim
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`

Fixture-backed records use `simulated_v1`. Profile-derived cache observations
use `derived_v1`. Real local process outputs from `nlfr run` and Nix proof
scripts use `collectable_v1`.

V1 does **not** claim remote worker assignment, queue time, action placement,
scheduler assignment, load distribution, or full remote-execution fleet behavior.
Worker identity is **conditional** on M7 stdout capture — not a wholesale fleet
claim. Compare projections are `derived_v1` summaries across ingested run groups.

Privacy boundary, proof samples, and explicit unproven claims:
[docs/ONE_PAGER.md](docs/ONE_PAGER.md).

## Documentation

Start at the [documentation hub](docs/INDEX.md) for the two-hop review map
(tutorial, how-to, reference, explanation).

| Intent | Where to go |
| --- | --- |
| First guided tour | [Walkthrough](docs/WALKTHROUGH.md) |
| Adoption paths (fixture + Nix) | [Adoption guide](docs/ADOPTION_GUIDE.md) |
| Architecture + milestones | [Architecture track](docs/ARCHITECTURE_TRACK.md) |
| Compare lens + M9 proof | [Compare runs](docs/wiki/compare-runs.md) |
| Proof samples + tryout | [proof-samples/](docs/proof-samples/README.md) |
| Contributor rules | [Contributing](docs/CONTRIBUTING.md) |

Depth pages live under [`docs/wiki/`](docs/wiki/) (evidence loop, truth labels,
ADR-lite decisions). How this repo was built: [docs/METHOD.md](docs/METHOD.md).

## Status And Limits

NLFR v1 is an evidence-first recorder MVP, not a hosted SaaS, multi-tenant
control plane, or full remote-execution fleet dashboard.

**CI status:** GitHub Actions runs are restored with the public release. Until
the first sustained green public run, the canonical verification is local:
`uv run pytest -q` and `./scripts/verify-demo.sh`. The CI matrix is documented
in [docs/CI_RECIPE.md](docs/CI_RECIPE.md).

**M5–M9 (landed):**

| Milestone | Delivers |
| --- | --- |
| M5 | Linux CI workflow + adoption docs (`nlfr-proof.yml`; proof samples author-Nix until GHA promotes) |
| M6 | Real default projection (`canvas-dev` `collectable_v1`) + fixture fallback banner |
| M7 | `worker_admin_stdout` parser + `worker-evidence-proof.sh` (conditional `worker_identity`) |
| M8 | Agent adapter (`record-agent-change.sh`; model + `prompt_sha256` only) |
| M9 | `compare export` / `compare index`, compare lens, `compare-proof.sh` |

Out of scope for v1: SaaS/auth/billing/multi-tenancy, fleet scheduler dashboards,
OTLP/Jaeger clone, persistent worker security claims, and unsupported
worker/action/queue-time correlation beyond direct artifact evidence.

Implementation plan: [docs/IMPLEMENTATION_DAG.md](docs/IMPLEMENTATION_DAG.md).

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
