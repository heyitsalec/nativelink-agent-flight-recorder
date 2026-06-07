# Unlock wave 1 — Task Packet: ship-pr-body

## KOS arming (mandatory)

Read before acting: [`../KOS-startup-routing.md`](../KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-unlock-ship` · Phase: ship

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ship-pr-body` |
| coordinator_id | `coord-unlock-ship` |
| dag_ref | `unlock-wave` / wave-1 |
| objective | Write GitHub PR body for `feat/lre-fleet-unlocks` with honest LRE + fleet claim ceilings |
| expected_output | `docs/sessions/handoffs/unlock-wave/wave-1/pr-body.md`, this task packet |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `docs/sessions/handoffs/unlock-wave/wave-1/pr-body.md`, `docs/sessions/handoffs/unlock-wave/wave-1/task-packet-ship-pr-body.md` |
| no_touch | `scripts/**`, `tests/**`, `src/**`, `canvas/**`, `.github/**`, `demo/**` |
| proof_commands | `test -f docs/sessions/handoffs/unlock-wave/wave-1/pr-body.md`; `grep -q 'lre_substrate_ready\|Honesty boundaries' docs/sessions/handoffs/unlock-wave/wave-1/pr-body.md`; `grep -q 'hermetic Nix' docs/sessions/handoffs/unlock-wave/wave-1/pr-body.md` |
| privacy_tier | `private_internal` |
| source_refs | `docs/sessions/handoffs/unlock-wave/wave-0/ship-packet.md`, `docs/sessions/handoffs/lre-proof/wave-2/integration-brief.md`, `docs/sessions/handoffs/future-fleet-claims/wave-1/integration-brief.md` |
| stop_conditions | PR body must not claim hermetic Nix LRE or fleet canvas UI; ceilings stay `lre_substrate_ready` and research-only `derived_v1` |
| return_status | DONE |

---

## Deliverables

- `pr-body.md` — title, summary bullets, test plan checkboxes, explicit honesty boundaries
- This task packet
- Chat JSON envelope (provenance return)

## Claims touched

- `lre_substrate_ready` — documentation only
- `derived_v1_fleet_claim_matrix` — documentation only
- `claim_boundary` — PR honesty section
