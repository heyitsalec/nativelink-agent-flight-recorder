# Tier 1 Agent Vision — Wave 6 Ship Packet

**Date:** 2026-06-06  
**Broker:** parent  
**Status:** DONE (wave 5 close-out 2026-06-06)

## North star delivered

"AI wrote it; here's proof it was validated."

| Act | Run group | Status |
|-----|-----------|--------|
| 1 Bugfix | `agent-bugfix-1` | live record + proof sample |
| 2 Feature | `agent-feature-compare` | live record + proof sample |
| 3 Compare triple | `record-proof` / `canvas-dev` / `agent-bugfix-1` | live compare JSON |
| GUI substrate | view-spec + GridShell + composer | test:truth green |

## Parent proof gates

| Gate | Result |
|------|--------|
| `uv run pytest -q` | 81 passed |
| `./scripts/tier1-agent-demo.sh --dry-run` | exit 0 |
| `./scripts/compare-agent-runs.sh` | 3 pairwise compares ok |
| `npm --prefix apps/canvas run build` | pass |
| `npm --prefix apps/canvas run test:truth` | ok: true |

## Coordinator completion

| Coordinator | Sub-DAG | Status |
|-------------|---------|--------|
| coord-t1-spine | T1-SPINE | DONE |
| coord-t1-bugfix | T1-BUGFIX | DONE |
| coord-t1-feature | T1-FEATURE | DONE |
| coord-t3-research | T3-R | DONE |
| coord-t3-design | T3-D | DONE |
| coord-t3-implement | T3-I1–I4 | DONE (composer wave 4) |
| coord-t1-integrate | T1-INTEGRATE | DONE — promote-tier1-compare, tier1-demo view, act 3 record |
| coord-t3-dogfood | T3-INTEGRATE | DONE — record-canvas-build refresh + wave-5 provenance |

## Operator quick path

```bash
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --dry-run
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state broken --check  # fails
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state fixed
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --act 1
./scripts/compare-agent-runs.sh
npm --prefix apps/canvas run preview
```

## Known caveats

- Bazel validation uses pytest fallback when `NLFR_SKIP_BAZEL=1`
- `data/` run dirs gitignored; proof samples committed for evaluators
- Act 3 meta `agent-change` record exists from prior M8 work; tier1 `--act 3` optional
