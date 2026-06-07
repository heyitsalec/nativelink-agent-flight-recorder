# Unlock wave Wave 1 — Task Packet: ship-integration-brief

## KOS arming (mandatory)

Read before acting: [`../KOS-startup-routing.md`](../KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-unlock-ship` · Phase: integrate

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ship-integration-brief` |
| coordinator_id | `coord-unlock-ship` |
| dag_ref | `unlock-wave` / wave-1 |
| objective | Consolidate `lre-proof` wave-2 + `future-fleet-claims` wave-1 into unlock-wave integration brief; advance ship packet to wave-1 ship-ready |
| expected_output | `docs/sessions/handoffs/unlock-wave/wave-1/integration-brief.md`, updated `docs/sessions/handoffs/unlock-wave/wave-0/ship-packet.md` |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `docs/sessions/handoffs/unlock-wave/wave-1/integration-brief.md`, `docs/sessions/handoffs/unlock-wave/wave-1/task-packet-ship-integration-brief.md`, `docs/sessions/handoffs/unlock-wave/wave-0/ship-packet.md` |
| no_touch | `scripts/**`, `tests/**`, `demo/**`, `.github/**`, `src/**`, canvas/** |
| proof_commands | `test -f docs/sessions/handoffs/unlock-wave/wave-1/integration-brief.md`; `grep lre_substrate_ready docs/sessions/handoffs/unlock-wave/wave-1/integration-brief.md`; `grep research_only docs/sessions/handoffs/unlock-wave/wave-1/integration-brief.md`; `grep wave-1 ship-ready docs/sessions/handoffs/unlock-wave/wave-0/ship-packet.md` |
| privacy_tier | `private_internal` |
| stop_conditions | Must preserve dual honesty ceilings — no fleet UI or Nix LRE toolchain overclaim |
| return_status | DONE |

---

## Inputs (read-only)

| Source | Path |
|--------|------|
| LRE integration brief | `docs/sessions/handoffs/lre-proof/wave-2/integration-brief.md` |
| Fleet integration brief | `docs/sessions/handoffs/future-fleet-claims/wave-1/integration-brief.md` |
| Wave-0 ship packet | `docs/sessions/handoffs/unlock-wave/wave-0/ship-packet.md` |
| Wave-1 broker ARM | `docs/sessions/handoffs/unlock-wave/wave-1/broker-arm.md` |

---

## Deliverables

- `integration-brief.md` — unified LRE + fleet synthesis with proof gates and broker rules
- `task-packet-ship-integration-brief.md` — this packet
- `../wave-0/ship-packet.md` — updated to wave-1 ship-ready with PR gate checklist
