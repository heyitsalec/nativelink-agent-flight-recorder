# Unlock wave — final ship packet (all waves)

**Date:** 2026-06-06  
**Branch:** `feat/lre-fleet-unlocks`

## Waves closed

| Wave | DAG | Ceiling |
|------|-----|---------|
| wave-0 | lre-proof + future-fleet-claims | substrate + research matrix |
| wave-1 | unlock-ship + ladder-sync | PR-ready integration |
| wave-3 | lre-proof Nix toolchain | `lre_bazelrc_generated` |

## Parent proof gates (final)

```
95 passed, 1 skipped (uv run pytest -q)
7 passed (test_lre_proof.py)
4 passed (test_fleet_claims_audit.py)
```

## Remaining frontier (not brokered)

- `CACHE_HIT_PARITY` — container worker alignment
- `PLATFORM_DARWIN` — upstream cc LRE
- Fleet implement DAG — new parsers + SQLite proof blocks
