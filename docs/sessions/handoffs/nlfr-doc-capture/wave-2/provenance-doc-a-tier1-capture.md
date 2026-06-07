# Wave 2 NLFR Doc Capture Provenance — tier1 refresh (NLFR-DOC-A)

**Worker:** NLFR-DOC-A (tier1-capture)  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/broker-three-tracks` (created from `main` at capture time)  
**Git HEAD:** `d34802f11def37e1dcffb17affcb19e27966e2fc`  
**When:** 2026-06-06  

## Scope

Re-capture canvas hero GIFs after tier1 compare promotion and `?view=tier1-demo` canvas URL.

| Deliverable | Path |
|-------------|------|
| Compare projection (promoted) | `apps/canvas/public/projections/compare-projection.json` |
| Canvas tour GIF | `docs/media/nlfr-canvas-tour.gif` |
| Evidence loop GIF | `docs/media/nlfr-evidence-loop.gif` |

## Inputs

| Prerequisite | Status |
|--------------|--------|
| `data/compare-agent-runs/projections/compare-canvas-dev-vs-agent-bugfix-1.json` | Present |
| `./scripts/promote-tier1-compare.sh` | PASS — copied to `compare-projection.json` |
| `apps/canvas/dist/` | Built (`npm --prefix apps/canvas run build`) |
| ffmpeg | `/opt/homebrew/bin/ffmpeg` — used (`ffmpeg: true` in capture JSON) |
| Playwright | `apps/canvas` devDependency — Chromium launched via `capture:heroes` |

Compare export was not re-run; existing pairwise projection from `data/compare-agent-runs/` was promoted.

## Commands

```bash
./scripts/promote-tier1-compare.sh
npm --prefix apps/canvas run build
CANVAS_URL='http://127.0.0.1:5174/?view=tier1-demo' npm --prefix apps/canvas run capture:heroes
```

Tour and evidence scripts auto-spawned `npm run preview` on `http://127.0.0.1:5174/` with the tier1-demo query view.

## Outputs

| Artifact | Bytes | SHA-256 |
|----------|-------|---------|
| `docs/media/nlfr-canvas-tour.gif` | 1,035,055 | `2f418fb8aa205861af20e9711a1dedb4aa4c548e0ac5eeda4fa7c3891d914695` |
| `docs/media/nlfr-evidence-loop.gif` | 651,868 | `8647c263edfa8fa7feb60d3b05b56a478a45cf76a493dff3abf8ca498651a820` |
| `compare-projection.json` | — | `3b5a8eeca059ec64f0202f422a53772e76132c6e3c9841326bb18974f77f4282` |

| GIF | Frames | FPS | Duration |
|-----|--------|-----|----------|
| `nlfr-canvas-tour.gif` | 64 | 8 | 8 s |
| `nlfr-evidence-loop.gif` | 64 | 8 | 8 s |

Both GIFs exceed 500 KiB (non-trivial size).

## Verification

| Check | Result |
|-------|--------|
| Promote tier1 compare | PASS |
| `npm --prefix apps/canvas run build` | PASS |
| `capture:heroes` with `CANVAS_URL=...tier1-demo` | PASS — both GIFs written |
| `docs/media/*.gif` present | PASS (2 files) |
| ffmpeg | available and used |
| Playwright | available (local package) |

## Summary

Wave 2 refreshed hero media with tier1-demo view and promoted pairwise compare (`canvas-dev-vs-agent-bugfix-1`). Tour GIF size increased vs wave 1 (~708 KiB → ~1.01 MiB), consistent with tier1 compare lens content; evidence-loop GIF unchanged in byte size.
