# Provenance — lre-parity-tests (wave-4)

**Worker:** `lre-parity-tests`  
**Wave:** 4  
**Write scope:** `tests/test_lre_proof.py`  
**Coordinator:** `coord-lre-cache-parity`

---

## Summary

Extended `tests/test_lre_proof.py` with two LRE cold/warm contract tests: environment
blocker shape (Darwin full sample match; Linux structural match) and summary shape via
fixture-backed cold/warm run legs + `cache_economics` projection block.

---

## Changes

| File | Change |
|------|--------|
| `tests/test_lre_proof.py` | +2 tests, `COLD_WARM_SCRIPT` + summary writer helper |

---

## Test matrix

| Test | Scope | Live NativeLink |
|------|-------|-----------------|
| `test_lre_cold_warm_proof_records_environment_blocker` | Script → `environment-blocker.json`, exit 2 | No |
| `test_lre_cold_warm_summary_shape_with_fixture` | Summary writer merges stubbed cold/warm runs + proof export | No |

---

## Proof commands (worker run)

```bash
uv run pytest tests/test_lre_proof.py -q
# 9 passed

bash -n scripts/lre-cold-warm-proof.sh
```

---

## Honesty ceiling

| Claim | Status | Labels |
|-------|--------|--------|
| Blocker contract for `lre-cold-warm-proof.sh` | **Proven** (fixture-backed) | `collectable_v1`, `high` |
| Summary contract `lre_cache_parity_observed` | **Proven** (fixture-backed) | `collectable_v1`, `medium` |
| Live LRE cold/warm green path | **Not claimed** in tests | CI `lre-cold-warm-ci` |

---

## JSON envelope

```json
{
  "worker_id": "lre-parity-tests",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-4/",
  "artifacts": {
    "provenance": "provenance-lre-parity-tests.md",
    "updated": [
      "tests/test_lre_proof.py"
    ]
  },
  "proof": {
    "command": "uv run pytest tests/test_lre_proof.py -q",
    "exit_code": 0,
    "passed": 9
  },
  "claims_touched": ["lre_cache_parity_observed"],
  "claim_ceiling": "lre_cache_parity_observed",
  "blockers": []
}
```
