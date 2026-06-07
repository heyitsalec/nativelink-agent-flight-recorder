# Contributing to NLFR

NLFR is an evidence-first recorder. Contributions should preserve the proof
spine: capture artifacts, ingest SQLite, export truth-labeled projection JSON,
render canvas from projections only.

← [Docs index](INDEX.md) · [Architecture track](ARCHITECTURE_TRACK.md) ·
[Usefulness roadmap](USEFULNESS_ROADMAP.md) · [Implementation DAG (historical)](IMPLEMENTATION_DAG.md)

## Before you open a PR

1. Run the unit test suite:

   ```bash
   pip install uv
   uv sync
   uv run pytest -q
   ```

2. Run local proof gates (no Nix required):

   ```bash
   bash -n scripts/*.sh
   ./scripts/verify-demo.sh
   ./scripts/record-proof.sh
   npm --prefix apps/canvas ci && npm --prefix apps/canvas run build
   npm --prefix apps/canvas run test:truth
   ```

3. If your change touches parsers, projections, or canvas truth labels, add or
   update tests that exercise real files, SQLite schemas, or serializers — not
   mocks of the evidence path.

### GitHub Actions offline (2026-06-06)

Workflows in [`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml)
may be non-green. **Do not block** doc or code PRs on CI green while Actions are
offline. Use the local gates above instead.

See [GHA offline proof shift](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md)
for merge policy and revisit triggers. Do not claim CI passed until workflows
actually pass. Promote redacted samples to [`proof-samples/`](proof-samples/) only
after a sustained green `nlfr-proof.yml` run.

## Proof scripts

| Script | When to run | Output / claim |
|--------|-------------|----------------|
| `./scripts/verify-demo.sh` | Any UI or projection change; always safe locally | `data/demo-proof/summary.json` |
| `./scripts/record-proof.sh` | Recorder ingest or manifest changes | `data/record-proof/summary.json` |
| `./scripts/record-canvas-build.sh` | Canvas default projection or dogfood path | `data/canvas-dev/` + `public/projections/` |
| `./scripts/compare-proof.sh` | M9 compare projector, CLI, or canvas compare lens | `data/compare-proof/summary.json` |
| `./scripts/worker-evidence-proof.sh` | M7 worker admin stdout parser or graph worker nodes | `data/worker-evidence-proof/summary.json` |
| `./scripts/cold-warm-cache-proof.sh` | Cache parser or summary changes (requires Nix) | `data/cold-warm-proof/summary.json` |
| `./scripts/agent-loop-proof.sh` | Agent/change chain or adapter changes (requires Nix) | `data/agent-loop-proof/summary.json` |
| `./scripts/local-exec-proof.sh` | Worker endpoint readiness (requires Nix) | `data/local-exec-proof/summary.json` |
| `./scripts/compare-agent-runs.sh` | Tier1 compare lens / hero capture prep | tier1 compare projections |
| `./scripts/record-agent-change.sh` | M8 real agent adapter path | agent provenance artifacts |

M7 worker identity path (fixture replay by default; live when Nix + stdout attached):

```bash
./scripts/worker-evidence-proof.sh
# → data/worker-evidence-proof/summary.json
# worker_identity_observed: true when admin stdout rows match (collectable_v1, high)
```

M9 compare path (requires `record-proof` and `canvas-dev` DBs):

```bash
./scripts/record-proof.sh
./scripts/record-canvas-build.sh
./scripts/compare-proof.sh
# → data/compare-proof/projections/compare-projection.json
```

Full local spine (when NativeLink/Bazel available):

```bash
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

CI mirrors the Linux lanes in [CI_RECIPE.md](CI_RECIPE.md) when Actions are
green. If toolchain proof is unavailable on your host, keep changes
fixture-backed and document the blocker in the PR.

## Canvas development

See [apps/canvas/README.md](../apps/canvas/README.md) for dev server, view
specs (`?view=`), `test:truth`, and capture scripts.

## Media regeneration

Hero GIFs and canvas capture tests live under `apps/canvas/`. Regenerate after
UI or walkthrough changes:

```bash
npm --prefix apps/canvas run capture:tour
npm --prefix apps/canvas run capture:evidence
npm --prefix apps/canvas run test:truth
```

Output lands in `docs/media/`. See [MEDIA_CAPTURE.md](MEDIA_CAPTURE.md) for
scene requirements and privacy rules. Do not commit secrets, raw prompts, or
unredacted host paths.

## Truth labels

Every projected node, edge, metric, and proof claim must carry four labels:

| Field | Values |
|-------|--------|
| `source_kind` | `collectable_v1`, `derived_v1`, `simulated_v1`, `future` |
| `confidence` | `high`, `medium`, `low`, `unknown` |
| `evidence_refs` | artifact or fixture references backing the claim |
| `redaction_state` | `safe`, `redacted`, `blocked`, `unknown` |

Rules:

- **Worker identity (M7):** promote `worker_identity` only when admin stdout is
  attached pre-ingest and the `worker_admin_stdout` parser finds matching rows
  (`collectable_v1`, `high`). Default proof path is fixture replay.
- **Still unsupported:** scheduler assignment, queue time, action placement,
  load distribution — label as boundary/future, not failures.
- Use `simulated_v1` for deterministic fixtures and bounded-agent demos.
- Use `future` for planned surfaces without collectable proof.
- Never export raw prompts, credentials, environment variables, or private logs.
  Prefer SHA-256 hashes and redacted paths.

## Docs

- Start at [INDEX.md](INDEX.md) when adding or reorganizing documentation.
- Cross-link new guides back to the index at the top and bottom of the file.
- Keep proof samples in [proof-samples/](proof-samples/README.md) redacted;
  regenerate from real runs under ignored `data/` only.
- Current milestone status: [ARCHITECTURE_TRACK.md](ARCHITECTURE_TRACK.md) and
  [USEFULNESS_ROADMAP.md](USEFULNESS_ROADMAP.md).

## Scope boundaries (v1)

Out of scope unless explicitly approved: remote-execution dashboards, OTLP/Jaeger
clones, auth/billing, multi-tenancy, and SaaS product surfaces ahead of
collectable proof.

← [Docs index](INDEX.md)
