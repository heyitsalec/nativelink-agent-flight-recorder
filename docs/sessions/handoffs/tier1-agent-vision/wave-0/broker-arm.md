# Wave 0 — broker ARM complete

**Date:** 2026-06-06  
**Status:** DONE

## Parent actions (local-critical-path)

- Reverted inline Tier 1 implementation (uncommitted work backed out)
- Baseline: `feat/m5-m9-umbrella` @ f648db6, 61 pytest green
- Created DAG mirror: `docs/dags/tier1-agent-vision.md`
- Created handoff tree + coordinator charters + spawn ledger
- **KOS arming:** [`../KOS-startup-routing.md`](../KOS-startup-routing.md) · [`kos-arming.md`](kos-arming.md)

## North star (unchanged)

"AI wrote it; here's proof it was validated." Acts 1+2 demo-ready; Act 3 GUI substrate + meta dogfood.

## Wave 1 dispatch (next)

Parent spawns in parallel:

1. **coord-t1-spine** — phase R (audit spine) → return manifest for explore workers
2. **coord-t3-research** — phase R → return manifest for Harmony/canvas/view-system explorers

## Operator constraint

Parallel tracks: demo pack + GUI substrate from wave 1 onward.
