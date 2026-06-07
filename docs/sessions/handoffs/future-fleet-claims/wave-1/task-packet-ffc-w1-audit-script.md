# Future fleet claims Wave 1 — Task Packet: ffc-w1-audit-script

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-future-fleet-claims` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ffc-w1-audit-script` |
| coordinator_id | `coord-future-fleet-claims` |
| dag_ref | `future-fleet-claims` / wave-1 |
| objective | Verify fleet claim matrix emitter and shell proof wrapper |
| expected_output | `scripts/fleet_claims_audit.py`, executable `scripts/fleet-claims-audit.sh`, generated `data/fleet-claims-audit/claim-matrix.json` |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `scripts/fleet_claims_audit.py`, `scripts/fleet-claims-audit.sh` |
| no_touch | `tests/**`, `docs/**`, `src/**` (read-only for claim source) |
| proof_commands | `./scripts/fleet-claims-audit.sh`; `python3 -c "import json; m=json.load(open('data/fleet-claims-audit/claim-matrix.json')); assert m['source_kind']=='derived_v1'"` |
| privacy_tier | `private_internal` |
| stop_conditions | Matrix must stay `research_only` — no fleet UI or invented backend state |
| return_status | DONE |

---

## Deliverables

- Python emitter: `build_matrix()` from `UNSUPPORTED_REMOTE_EXECUTION_CLAIMS` with truth labels
- Shell wrapper: `PYTHONPATH=src uv run python … --output data/fleet-claims-audit/claim-matrix.json`
- Matrix rows: 5 claims; `worker_identity` conditional; others `out_of_scope` with blockers
