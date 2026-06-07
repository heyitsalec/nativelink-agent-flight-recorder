# NLFR Canvas

Sparse TypeScript canvas that renders **projection JSON only**. The canvas is a
consumer of recorded facts — it must not invent backend state (worker queues,
scheduler assignment, or live agent sessions).

← [Docs index](../../docs/INDEX.md) · [MEDIA_CAPTURE.md](../../docs/MEDIA_CAPTURE.md)

## Quickstart

```bash
# Populate projections from the dogfood record path
./scripts/record-canvas-build.sh

# Dev server (default view: nlfr-default-v0)
npm --prefix apps/canvas ci
npm --prefix apps/canvas run dev

# Production build + truth-label guard (CI gate)
npm --prefix apps/canvas run build
npm --prefix apps/canvas run test:truth
```

Open `http://127.0.0.1:5173/` (Vite dev) or `http://127.0.0.1:5174/` after
`npm run preview`.

## Projection inputs

The canvas reads JSON under `public/projections/`:

| File | Purpose |
|------|---------|
| `action-graph.json` | Graph lens — nodes/edges with truth labels |
| `proof.json` | Proof packet blocks (cache, remote, agent) |
| `runway.json` | Runway timeline lens |
| `compare-projection.json` | Compare lens (`derived_v1` deltas between run groups) |

Regenerate with:

```bash
./scripts/record-canvas-build.sh          # canvas-dev run group
./scripts/record-proof.sh                 # record-proof run group (compare left)
./scripts/compare-proof.sh                # compare summary + compare-projection.json
```

Compare export (manual):

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/record-proof/nlfr.sqlite --left record-proof \
  --right-db data/canvas-dev/nlfr.sqlite --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json
```

## Views

View specs (`nlfr.view-spec.v1`) control layout, mode lenses, and panel bindings.
Load precedence:

1. Query `?view=<view_id>` — bundled template or `/views/<view_id>.json`
2. `localStorage` key `nlfr.view-spec` (composer overrides)
3. Bundled `nlfr-default-v0`

Bundled and committed views in `public/views/`:

| View ID | Use |
|---------|-----|
| `nlfr-default-v0` | Full layout — graph, proof, remote, compare lenses |
| `tier1-demo` | Tier1 agent demo tour (hero GIF capture default) |
| `proof-review` | Proof packet–focused rail |
| `graph-only` | Graph lens only |

Examples:

```bash
npm --prefix apps/canvas run dev
# http://127.0.0.1:5173/?view=tier1-demo
# http://127.0.0.1:5173/?view=graph-only
```

Default projection is `canvas-dev` (`collectable_v1`) when
`record-canvas-build.sh` has run; fixture fallback shows a banner via
`projection_notice`.

## Mode lenses

The default view exposes five mode lenses (top bar):

- **graph** — action graph from `action-graph.json`
- **runway** — runway timeline
- **proof** — proof packet inspector
- **remote** — remote-execution boundary labels (not live fleet state)
- **compare** — `compare-projection.json` only; requires export/compare proof

Remote and compare panels render unsupported claims as boundary labels, not
invented metrics.

## Truth guard (`test:truth`)

`npm run test:truth` runs `scripts/truth-guard.mjs`:

- Loads built/preview canvas and validates projection JSON on disk
- Asserts every node/edge/block carries `source_kind`, `confidence`,
  `evidence_refs`, `redaction_state`
- Validates `compare-projection.json` when present

Run after projection or canvas binding changes. CI runs this in the `unit` job of
[`.github/workflows/nlfr-proof.yml`](../../.github/workflows/nlfr-proof.yml).

## Capture scripts

Hero GIFs and screenshot diffs for docs:

| npm script | Output |
|------------|--------|
| `capture:tour` | `docs/media/nlfr-canvas-tour.gif` |
| `capture:evidence` | `docs/media/nlfr-evidence-loop.gif` |
| `capture:heroes` | both GIFs |
| `diff` | pixel diff vs committed baselines |

Typical regenerate flow:

```bash
./scripts/record-canvas-build.sh
./scripts/compare-agent-runs.sh      # optional tier1 compare lens
npm --prefix apps/canvas run build
CANVAS_URL='http://127.0.0.1:5174/?view=tier1-demo' npm --prefix apps/canvas run capture:heroes
npm --prefix apps/canvas run test:truth
```

See [MEDIA_CAPTURE.md](../../docs/MEDIA_CAPTURE.md) for ffmpeg/Playwright
prerequisites and privacy rules.

## Contributing

- Canvas changes must keep projection-only rendering; see
  [CONTRIBUTING.md](../../docs/CONTRIBUTING.md) truth-label rules.
- Do not add panels that imply live worker/scheduler state without
  `collectable_v1` evidence in projection JSON.
- Regenerate media and run `test:truth` before opening a PR.

← [Docs index](../../docs/INDEX.md)
