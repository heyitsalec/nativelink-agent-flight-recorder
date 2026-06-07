# Future fleet claims Wave 1 — Task Packet: ffc-w1-handoffs

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-future-fleet-claims` · Phase: integrate

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ffc-w1-handoffs` |
| coordinator_id | `coord-future-fleet-claims` |
| dag_ref | `future-fleet-claims` / wave-1 |
| objective | Broker handoff closure: spawn ledger, task packets, worker-results, integration brief |
| expected_output | `docs/sessions/handoffs/future-fleet-claims/wave-1/*`, updated handoffs README |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `docs/sessions/handoffs/future-fleet-claims/wave-1/**`, `docs/sessions/handoffs/README.md`, `docs/proof-samples/fleet-claims-matrix-sample.json` |
| no_touch | `scripts/**`, `tests/**`, `src/**`, canvas/** |
| proof_commands | `test -f tests/test_fleet_claims_audit.py`; `grep research_only docs/dags/future-fleet-claims.md`; `uv run pytest tests/test_fleet_claims_audit.py -q` |
| privacy_tier | `private_internal` |
| stop_conditions | Handoffs must preserve `research_only` ceiling — no fleet UI implement workers |
| return_status | DONE |

---

## Deliverables

- Wave-1 spawn ledger + task packets for all four workers
- `worker-results.json` aggregating upstream DONE status
- `integration-brief.md` for coordinator reflect gate
- Optional `docs/proof-samples/fleet-claims-matrix-sample.json` schema mirror
