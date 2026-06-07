# Wave 3 Integration Brief — T3-I1/I2

**Date:** 2026-06-06  
**Status:** DONE

## Landed

- View specs: `apps/canvas/public/views/{nlfr-default-v0,graph-only,proof-review}.json`
- Shell: GridShell, ViewContext, binding resolver, routing hooks
- Panels: ChartPanel, TablePanel, OperatorPanel; thin App.tsx
- Composer MVP (wave 4): `apps/canvas/src/composer/`

## Proof

```bash
npm --prefix apps/canvas run build
npm --prefix apps/canvas run test:truth  # ok: true, 40/40 nodes
```

## Truth guard

All `data-testid` contracts preserved. Compare lens visible when binding present.
