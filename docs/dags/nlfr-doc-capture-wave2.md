# NLFR doc capture — wave 2 (tier1 heroes)

**Parent:** PER-1071  
**Handoffs:** `docs/sessions/handoffs/nlfr-doc-capture/wave-2/`

## Objective

Re-capture hero GIFs after tier1 canvas (`?view=tier1-demo`, Compare lens populated).

## Proof

```bash
./scripts/promote-tier1-compare.sh
npm --prefix apps/canvas run build
CANVAS_URL='http://127.0.0.1:5174/?view=tier1-demo' npm --prefix apps/canvas run capture:heroes
```

Outputs: `docs/media/nlfr-canvas-tour.gif`, `docs/media/nlfr-evidence-loop.gif`
