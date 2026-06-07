# Future fleet claims Wave 1 — Task Packet: ffc-w1-one-pager-footnote

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-future-fleet-claims` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ffc-w1-one-pager-footnote` |
| coordinator_id | `coord-future-fleet-claims` |
| dag_ref | `future-fleet-claims` / wave-1 |
| objective | Sync ONE_PAGER explicitly-unproven section with fleet claim matrix DAG |
| expected_output | `docs/ONE_PAGER.md` footnote linking DAG + audit script |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `docs/ONE_PAGER.md` |
| no_touch | `scripts/**`, `tests/**`, canvas/** |
| proof_commands | `grep -n 'future-fleet-claims\|fleet-claims-audit' docs/ONE_PAGER.md` |
| privacy_tier | `private_internal` |
| stop_conditions | Footnote must not claim fleet/scheduler proof without new parsers |
| return_status | DONE |

---

## Deliverables

- **What is explicitly unproven:** worker identity, scheduler assignment, queue time, action placement, load distribution, multi-machine fleet, org-scale history
- **Research matrix footnote:** link to `docs/dags/future-fleet-claims.md` and `./scripts/fleet-claims-audit.sh` → `data/fleet-claims-audit/claim-matrix.json`
