# Wave 5 — T1-INTEGRATE close-out

**Date:** 2026-06-06  
**Status:** DONE

## Delivered

| Item | Path |
|------|------|
| Compare promote script | `scripts/promote-tier1-compare.sh` |
| Canvas compare binding | `apps/canvas/public/projections/compare-projection.json` |
| Act 3 live record | `data/agent-change/` (gitignored) |
| Tier 1 demo view | `apps/canvas/public/views/tier1-demo.json` |
| DEMO_SCRIPT tier1 section | prior wave + wave 5 promote hook |

## Operator path

```bash
./scripts/compare-agent-runs.sh
./scripts/promote-tier1-compare.sh
npm --prefix apps/canvas run preview
# http://127.0.0.1:5174/?view=tier1-demo
```

## Narrative

Compare lens shows **derived_v1** deltas between `canvas-dev` and `agent-bugfix-1`. Say aloud: no worker/scheduler correlation.
