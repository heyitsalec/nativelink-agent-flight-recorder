# Wave 3 M9 Canvas Compare Projection Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/m5-m9-umbrella`  
**When:** 2026-06-06  

## Inputs

| Side | Run group | SQLite |
|------|-----------|--------|
| Left | `record-proof` | `data/record-proof/nlfr.sqlite` |
| Right | `canvas-dev` | `data/canvas-dev/nlfr.sqlite` |

Compare inputs were already present (record-proof and canvas-build DBs from prior wave scripts); `record-proof.sh` / `record-canvas-build.sh` were not re-run.

## Export command

```bash
PYTHONPATH=src uv run python -m nlfr compare export \
  --left-db data/record-proof/nlfr.sqlite --left record-proof \
  --right-db data/canvas-dev/nlfr.sqlite --right canvas-dev \
  --output apps/canvas/public/projections/compare-projection.json
```

Cross-DB export uses `build_compare_projection` with proof packets from each database (same semantics as `scripts/compare-proof.sh`).

## Canvas artifact

| Path | Notes |
|------|-------|
| `apps/canvas/public/projections/compare-projection.json` | 5 compare dimensions, `derived_v1`, evidence refs `run_group:record-proof` + `run_group:canvas-dev` |

## Verification

| Command | Result |
|---------|--------|
| `npm --prefix apps/canvas run build` | PASS |
| `CANVAS_URL=http://127.0.0.1:5174/ npm --prefix apps/canvas run test:truth` | PASS — `compare.present: true`, `schema_ok: true`, `lens_visible: true` |
| `./scripts/compare-proof.sh` | PASS — 5 dimension ids, status ok |

## Truth labels

Compare projection root and each dimension carry `source_kind: derived_v1`, `confidence: medium`, `redaction_state: safe`, and bounded `evidence_refs`. No cross-run worker/queue correlation beyond proof summaries.

## Summary

Canvas compare lens is fed from exported cross-DB compare projection JSON; truth-guard confirms schema and compare lens visibility when the file is present.
