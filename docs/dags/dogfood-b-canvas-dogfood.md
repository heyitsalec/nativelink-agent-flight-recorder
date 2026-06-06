# DAG B — Canvas Dogfood + Screenshot Diff

Linear parent: [PER-1058](https://linear.app/gradschool/issue/PER-1058)  
Linear issue: PER-1064 (canvas dogfood + screenshot diff — default real projection)

## Objective

Make NLFR record building its own GUI: screenshot-diff harness, canvas-as-truth guard,
dogfood script, and committed real (redacted) projections as the canvas default view.

## Coordinator mode

Parallel workers; dogfood/commit legs blocked on DAG A generic command path.

| Worker | Scope | Deliverable |
|--------|-------|-------------|
| Diff harness | `apps/canvas/scripts/` | `npm run diff` with baselines |
| Truth guard | `apps/canvas/` | Playwright DOM vs projection JSON test |
| Dogfood | `scripts/record-canvas-build.sh` | `canvas-dev` run group + summary.json |
| Default view | `apps/canvas/public/projections/` | Redacted real projections |

## Handoff checklist

- [x] Collect gate: canvas build + diff + pytest recorded via generic run
- [x] Normalize gate: SQLite rows for canvas-dev run group
- [x] Project gate: exported JSON with truth labels; paths redacted
- [x] Consume gate: canvas loads real projection; truth guard passes
- [x] Ship gate: `npm --prefix apps/canvas run diff` green

## Proof commands

```bash
npm --prefix apps/canvas run build
npm --prefix apps/canvas run diff
npm --prefix apps/canvas run test:truth
scripts/record-canvas-build.sh
```

## Blocked by

DAG A (`nlfr run --mode generic`) for dogfood script only.

## Related

- DAG A: [dogfood-a-generic-recorder.md](dogfood-a-generic-recorder.md)
- Spec: [../USEFULNESS_ROADMAP.md](../USEFULNESS_ROADMAP.md)
