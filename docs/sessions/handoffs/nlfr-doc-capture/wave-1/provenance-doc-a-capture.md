# Wave 1 NLFR Doc Capture Provenance — PER-1072 (NLFR-DOC-A)

**Worker:** NLFR-DOC-A  
**Linear:** PER-1072  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/m5-m9-umbrella`  
**When:** 2026-06-06  

## Scope

Harmony-style media capture for NLFR canvas hero GIFs:

| Deliverable | Path |
|-------------|------|
| Shared GIF helpers | `apps/canvas/scripts/lib/gif-capture.mjs` |
| Canvas demo tour | `apps/canvas/scripts/capture-demo-tour.mjs` |
| Evidence loop terminal | `apps/canvas/scripts/capture-evidence-loop.mjs` |
| Regeneration docs | `docs/MEDIA_CAPTURE.md` |
| Canvas tour GIF | `docs/media/nlfr-canvas-tour.gif` |
| Evidence loop GIF | `docs/media/nlfr-evidence-loop.gif` |

## Inputs

| Prerequisite | Status |
|--------------|--------|
| `data/canvas-dev/nlfr.sqlite` | Present (prior `record-canvas-build.sh`) |
| `apps/canvas/public/projections/compare-projection.json` | Present (record-proof vs canvas-dev) |
| `apps/canvas/dist/` | Present |
| ffmpeg | `/opt/homebrew/bin/ffmpeg` 8.1.1 |

Compare export was not re-run; existing compare projection from wave 3 M9 provenance was used.

## Capture commands

```bash
npm --prefix apps/canvas run capture:heroes
```

Tour script auto-spawned `npm run preview` on `http://127.0.0.1:5174/`. Evidence loop used Playwright + local HTML terminal (no live shell recording).

## Outputs

| GIF | Bytes | Frames | FPS | Duration |
|-----|-------|--------|-----|----------|
| `docs/media/nlfr-canvas-tour.gif` | 707,778 | 64 | 8 | 8 s |
| `docs/media/nlfr-evidence-loop.gif` | 651,868 | 64 | 8 | 8 s |

## Tour scenes

1. **Action Graph** — focus `[data-testid="action-graph-svg"]`
2. **Proof Packet** — focus `[data-testid="proof-drawer"]`
3. **Compare Runs** — focus `[data-testid="compare-lens"]`
4. **Operator command** — `agent loop` → focus `[data-testid="operator-chat"]`

## Evidence loop events (public-safe)

Curated terminal replay: `nlfr run generic` → SQLite ingest → graph/proof/runway export → redact publish → compare export → canvas build → `summary.json` with `collectable_v1`. Paths use `${NLFR_DATA}` placeholders; no secrets or raw logs.

## npm scripts added

```json
"capture:tour": "node scripts/capture-demo-tour.mjs",
"capture:evidence": "node scripts/capture-evidence-loop.mjs",
"capture:heroes": "node scripts/capture-demo-tour.mjs && node scripts/capture-evidence-loop.mjs"
```

## Verification

| Check | Result |
|-------|--------|
| `npm --prefix apps/canvas run capture:heroes` | PASS — both GIFs written |
| ffmpeg used | true |
| Compare lens visible in tour | true (compare-projection.json loaded) |

## Summary

NLFR canvas hero media capture mirrors Harmony's hold/focus/caption/ffmpeg pattern. Tour GIF demonstrates projection-only canvas lenses; evidence-loop GIF shows the record→ingest→export→project pipeline with redacted, public-safe terminal events.
