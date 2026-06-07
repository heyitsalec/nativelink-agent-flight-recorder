# Unlock wave — broker ARM

**Date:** 2026-06-06  
**Branch:** `feat/lre-fleet-unlocks`  
**Status:** ARMED

## Operator intent

Broker next unlocks per `docs/dags/future-execution-ladder.md`:

1. **LRE substrate** — `demo/nativelink/lre.json5` + green `lre-proof.sh` path
2. **Fleet claims research** — `future-fleet-claims` DAG (no UI)

## Parent actions (ARM only)

- Created KOS routing: [`../KOS-startup-routing.md`](../KOS-startup-routing.md)
- Re-armed broker mode — **no further inline DAG implementation**
- Partial pre-ARM files on branch; coordinators treat as draft for worker verification

## Wave 1 dispatch

Parent spawns in parallel:

1. **coord-lre-proof** — wave-2 implement manifest
2. **coord-future-fleet-claims** — wave-1 research manifest

## Proof gates (parent at ship)

`uv run pytest -q` · `fleet-claims-audit.sh` · CI workflow sanity for `lre-proof-probe`
