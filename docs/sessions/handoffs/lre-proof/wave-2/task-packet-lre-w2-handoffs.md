# LRE Wave 2 — Task Packet: lre-w2-handoffs

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-lre-proof` · Phase: integrate

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `lre-w2-handoffs` |
| coordinator_id | `coord-lre-proof` |
| dag_ref | `lre-proof` / wave-2 |
| objective | Broker handoff closure: spawn ledger, task packets, worker-results, integration brief, DAG sync |
| expected_output | `docs/sessions/handoffs/lre-proof/wave-2/*`, updated `docs/dags/lre-proof.md`, parent spawn ledger |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `docs/sessions/handoffs/lre-proof/wave-2/**`, `docs/sessions/handoffs/lre-proof/spawn-ledger.md`, `docs/dags/lre-proof.md`, `docs/dags/README.md` |
| no_touch | `scripts/**`, `tests/**`, `demo/**`, `.github/**` |
| proof_commands | `test -f tests/test_lre_proof.py`; `grep lre_substrate_ready docs/dags/lre-proof.md` |
| privacy_tier | `private_internal` |
| stop_conditions | DAG ceiling must match `lre_substrate_ready` honesty — not Nix LRE or fleet UI |
| return_status | DONE |

---

## Deliverables

- Wave-2 spawn ledger + task packets for all workers
- `worker-results.json` aggregating upstream DONE status
- `integration-brief.md` for coordinator reflect gate
- `docs/dags/lre-proof.md` synced to `lre_substrate_ready` ceiling
