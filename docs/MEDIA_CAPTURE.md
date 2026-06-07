# NLFR Media Capture

Harmony-style GIF capture scripts for NLFR canvas hero media. Scripts frame screenshots with Playwright, encode with ffmpeg, and write public-safe artifacts under `docs/media/`.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **ffmpeg** | Required for GIF encoding. Install via Homebrew (`brew install ffmpeg`) or your package manager. Scripts fail fast if ffmpeg is missing. |
| **Node + npm** | Canvas devDependencies include Playwright. Run `npm --prefix apps/canvas install` if needed. |
| **Canvas build** | `npm --prefix apps/canvas run build` — dist must exist for preview. |
| **Projection JSON** | Run `./scripts/record-canvas-build.sh` to populate `apps/canvas/public/projections/`. |
| **Compare lens** | Optional but recommended for tour scene 3. Export when both run groups exist: |

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/record-proof/nlfr.sqlite --left record-proof \
  --right-db data/canvas-dev/nlfr.sqlite --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json
npm --prefix apps/canvas run build
```

## Scripts

| npm script | Script | Output |
|------------|--------|--------|
| `capture:tour` | `scripts/capture-demo-tour.mjs` | `docs/media/nlfr-canvas-tour.gif` |
| `capture:evidence` | `scripts/capture-evidence-loop.mjs` | `docs/media/nlfr-evidence-loop.gif` |
| `capture:heroes` | both tour + evidence | both GIFs above |

Shared helpers live in `apps/canvas/scripts/lib/gif-capture.mjs`:

- `hold` / `holdFrames` — timed screenshot sequences with story pacing
- `installTourChrome` / `setCaption` / `focus` — Harmony-style caption overlay and focus ring
- `makeGif` — ffmpeg palettegen/paletteuse encoding
- `ensurePreviewServer` — spawns `npm run preview` when canvas is not already up

## Quick regenerate

```bash
# 1. Ensure projections (once per host refresh)
./scripts/record-canvas-build.sh

# 2. Compare export if compare lens should appear in tour
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/record-proof/nlfr.sqlite --left record-proof \
  --right-db data/canvas-dev/nlfr.sqlite --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json

# 3. Build + capture both hero GIFs
npm --prefix apps/canvas run build
npm --prefix apps/canvas run capture:heroes
```

The tour script auto-starts preview on `http://127.0.0.1:5174/` unless it is already running. To manage preview yourself:

```bash
npm --prefix apps/canvas run preview &
NLFR_SKIP_PREVIEW_SPAWN=1 npm --prefix apps/canvas run capture:tour
```

## Environment variables

### Demo tour (`capture-demo-tour.mjs`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NLFR_DEMO_TOUR_DURATION_SECONDS` | `8` | Target GIF duration |
| `NLFR_DEMO_TOUR_FPS` | `8` | Frame rate |
| `NLFR_DEMO_TOUR_STORY_SECONDS` | `8` | Story pacing denominator for scene holds |
| `NLFR_DEMO_TOUR_WIDTH` / `HEIGHT` | `1280` / `800` | Viewport |
| `NLFR_DEMO_TOUR_OUTPUT_WIDTH` | `960` | GIF width (height scales) |
| `NLFR_DEMO_TOUR_GIF` | `docs/media/nlfr-canvas-tour.gif` | Output path |
| `NLFR_DEMO_TOUR_WORK_DIR` | temp dir | Keep frames for debugging |
| `CANVAS_URL` | `http://127.0.0.1:5174/` | Preview URL |
| `NLFR_SKIP_PREVIEW_SPAWN` | unset | Set `1` to require manual preview |

### Evidence loop (`capture-evidence-loop.mjs`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NLFR_EVIDENCE_LOOP_DURATION_SECONDS` | `8` | Target GIF duration |
| `NLFR_EVIDENCE_LOOP_FPS` | `8` | Frame rate |
| `NLFR_EVIDENCE_LOOP_WIDTH` / `HEIGHT` | `1280` / `720` | Viewport |
| `NLFR_EVIDENCE_LOOP_OUTPUT_WIDTH` | `960` | GIF width |
| `NLFR_EVIDENCE_LOOP_GIF` | `docs/media/nlfr-evidence-loop.gif` | Output path |
| `NLFR_EVIDENCE_LOOP_WORK_DIR` | temp dir | Keep frames for debugging |

## Scene design guidelines

1. **Evidence-first** — Tour scenes mirror the canonical NLFR flow: Action Graph → Proof Packet → Compare Runs → operator command. Do not invent UI state the canvas cannot render from projection JSON.

2. **Truth labels visible** — Prefer lenses and panels that show `source_kind`, `confidence`, `evidence_refs`, and `redaction_state`. Captions should describe what is *recorded*, not aspirational backend behavior.

3. **Public-safe terminal replay** — The evidence-loop GIF uses a curated HTML terminal with redacted paths (`${NLFR_DATA}`, `${HOME}` placeholders). Never embed secrets, raw logs, credentials, or customer paths.

4. **Stable selectors** — Use `data-testid` and accessible labels (`Proof Packet`, `Compare Runs`, `operator command`). Avoid brittle CSS or pixel coordinates.

5. **Pacing** — Default 8 s @ 8 fps = 64 frames. Tour uses four ~2 s scenes; evidence loop distributes events evenly across the timeline.

6. **Caption chrome** — Tour captions follow Harmony's `installTourChrome` pattern: fixed lower-left card + focus ring. Keep titles short (2–4 words) and bodies one sentence.

7. **Compare lens fallback** — If `compare-projection.json` is missing, the Compare Runs scene still captures but may show the unavailable placeholder. Regenerate compare export before publishing.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ffmpeg not found` | Install ffmpeg and ensure it is on `PATH` |
| Preview timeout | Run `npm --prefix apps/canvas run build` then start preview manually |
| Compare lens empty | Run compare export (see above) and rebuild |
| Fixture fallback banner | Preview cannot load `/projections/*.json` — rebuild canvas after publishing projections |
