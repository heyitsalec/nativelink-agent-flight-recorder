# Future fleet claims audit tests — Wave 1 provenance

**Worker:** `ffc-w1-audit-tests`  
**Coordinator:** `coord-future-fleet-claims`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Added `tests/test_fleet_claims_audit.py` with four fixture-free tests that import `build_matrix()` from `scripts/fleet_claims_audit.py` and exercise the CLI subprocess path. Assertions lock the research-only claim-matrix schema, full `UNSUPPORTED_REMOTE_EXECUTION_CLAIMS` coverage, and the `worker_identity` parser documentation row.

---

## Inputs read

| Artifact | Path |
|----------|------|
| Fleet claims audit script | `scripts/fleet_claims_audit.py` |
| Fleet claims audit shell wrapper | `scripts/fleet-claims-audit.sh` |
| Unsupported claims source | `src/nlfr/projectors/remote_execution.py` |
| DAG charter | `docs/dags/future-fleet-claims.md` |
| Coordinator charter | `docs/sessions/handoffs/unlock-wave/wave-0/coordinator-charters.md` |

---

## Deliverables written

| File | Action |
|------|--------|
| `tests/test_fleet_claims_audit.py` | Created — 4 tests |
| This file | Created |

---

## Test matrix

| Test | Scope | Live NativeLink |
|------|-------|-----------------|
| `test_build_matrix_claim_schema` | Top-level truth labels + per-claim row keys | No |
| `test_build_matrix_includes_all_unsupported_claims` | Matrix rows match `UNSUPPORTED_REMOTE_EXECUTION_CLAIMS` exactly | No |
| `test_worker_identity_row_documents_parser` | `worker_identity` row names parser + proof block | No |
| `test_fleet_claims_audit_subprocess_writes_matrix` | CLI `--output` writes valid JSON matrix | No |

---

## Proof

```bash
uv run pytest tests/test_fleet_claims_audit.py -q
# 4 passed in 0.06s
```

---

## Honesty / claim boundary

- Tests validate the **research-only claim matrix contract**, not fleet dashboards or new collectable parsers.
- `worker_identity` is asserted as **conditional** with a documented parser path; other unsupported claims remain `out_of_scope` with blockers.

---

## Return

```json
{
  "worker_id": "ffc-w1-audit-tests",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/future-fleet-claims/wave-1/",
  "artifacts": {
    "provenance": "provenance-ffc-w1-audit-tests.md",
    "modified": ["tests/test_fleet_claims_audit.py"]
  },
  "proof": {
    "command": "uv run pytest tests/test_fleet_claims_audit.py -q",
    "exit_code": 0,
    "passed": 4
  },
  "claims_touched": [
    "worker_identity",
    "action_placement",
    "queue_time",
    "scheduler_assignment",
    "load_distribution"
  ],
  "blockers": []
}
```
