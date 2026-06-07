# Contributing to NLFR

NLFR is an evidence-first recorder. Contributions should preserve the proof
spine: capture artifacts, ingest SQLite, export truth-labeled projection JSON,
render canvas from projections only.

← [Docs index](INDEX.md)

## Before you open a PR

1. Run the unit test suite:

   ```bash
   pip install uv
   uv sync
   uv run pytest -q
   ```

2. Run the fixture proof path (no Nix required):

   ```bash
   ./scripts/verify-demo.sh
   npm --prefix apps/canvas ci && npm --prefix apps/canvas run build
   ```

3. If your change touches parsers, projections, or canvas truth labels, add or
   update tests that exercise real files, SQLite schemas, or serializers — not
   mocks of the evidence path.

## Proof scripts

| Script | When to run |
|--------|-------------|
| `./scripts/verify-demo.sh` | Any UI or projection change; always safe locally |
| `./scripts/record-proof.sh` | Recorder ingest or manifest changes |
| `./scripts/cold-warm-cache-proof.sh` | Cache parser or summary changes (requires Nix) |
| `./scripts/agent-loop-proof.sh` | Agent/change chain or adapter changes (requires Nix) |

Full local spine (when NativeLink/Bazel available):

```bash
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

CI mirrors the Linux lanes in [CI_RECIPE.md](CI_RECIPE.md). If toolchain proof
is unavailable on your host, keep changes fixture-backed and document the
blocker in the PR.

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

- Do not claim worker identity, scheduler assignment, queue time, or action
  placement unless direct evidence is captured and labeled `collectable_v1`.
- Use `simulated_v1` for deterministic fixtures and bounded-agent demos.
- Use `future` for planned surfaces without collectable proof.
- Never export raw prompts, credentials, environment variables, or private logs.
  Prefer SHA-256 hashes and redacted paths.

## Docs

- Start at [INDEX.md](INDEX.md) when adding or reorganizing documentation.
- Cross-link new guides back to the index at the top and bottom of the file.
- Keep proof samples in [proof-samples/](proof-samples/README.md) redacted;
  regenerate from real runs under ignored `data/` only.

## Scope boundaries (v1)

Out of scope unless explicitly approved: remote-execution dashboards, OTLP/Jaeger
clones, auth/billing, multi-tenancy, and SaaS product surfaces ahead of
collectable proof.

← [Docs index](INDEX.md)
