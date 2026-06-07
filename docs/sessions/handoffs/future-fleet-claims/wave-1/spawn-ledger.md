# Spawn ledger — future-fleet-claims wave-1 (research only)

**Coordinator:** `coord-future-fleet-claims`  
**DAG:** `docs/dags/future-fleet-claims.md`  
**Branch:** `feat/lre-fleet-unlocks`  
**KOS:** `docs/sessions/handoffs/unlock-wave/KOS-startup-routing.md`

| worker_id | type | write_scope | status | provenance |
|-----------|------|-------------|--------|------------|
| ffc-w1-audit-script | worker | `scripts/fleet_claims_audit.py`, `scripts/fleet-claims-audit.sh` | DONE | `provenance-ffc-w1-audit-script.md` |
| ffc-w1-audit-tests | worker | `tests/test_fleet_claims_audit.py` | DONE | `provenance-ffc-w1-audit-tests.md` |
| ffc-w1-one-pager-footnote | worker | `docs/ONE_PAGER.md` | DONE | — |
| ffc-w1-handoffs | worker | `docs/sessions/handoffs/future-fleet-claims/wave-1/**`, `docs/sessions/handoffs/README.md` | DONE | `provenance-ffc-w1-handoffs.md` |

**Ceiling:** `research_only` (`derived_v1`, `high`) — honesty matrix sync; no fleet UI implement workers.

**Proof gate:**

```bash
./scripts/fleet-claims-audit.sh
uv run pytest tests/test_fleet_claims_audit.py -q
```
