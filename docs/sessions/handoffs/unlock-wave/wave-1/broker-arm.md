# Unlock wave — wave-1 ARM (ship + phase-3 frontier)

**Date:** 2026-06-06  
**Branch:** `feat/lre-fleet-unlocks`  
**Status:** ARMED

## Completed (wave-0)

- `lre-proof` wave-2 → `lre_substrate_ready`
- `future-fleet-claims` wave-1 → research matrix
- Parent proof gates passed (92 pytest)

## Wave-1 objectives

| Coordinator | Sub-DAG | Goal |
|-------------|---------|------|
| `coord-unlock-ship` | unlock-ship | PR-ready ship: docs sync, ship packet, integration close |
| `coord-lre-nix-phase3` | lre-proof wave-3 | Research + implement Nix LRE toolchain OR honest blocker |
| `coord-ladder-docs-sync` | ladder-sync | Fix stale `future-execution-ladder.md` + `docs/dags/README.md` |

## Wave-2 (after ship)

- `lre-proof` wave-3 implement (if research unblocks)
- CI verify post-merge

**KOS:** [`../KOS-startup-routing.md`](../KOS-startup-routing.md)
