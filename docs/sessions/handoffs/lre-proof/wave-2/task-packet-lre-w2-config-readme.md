# LRE Wave 2 — Task Packet: lre-w2-config-readme

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-lre-proof` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `lre-w2-config-readme` |
| coordinator_id | `coord-lre-proof` |
| dag_ref | `lre-proof` / wave-2 |
| objective | Land LRE substrate config and README honesty section for phase-1 `lre_substrate_ready` |
| expected_output | `demo/nativelink/lre.json5`, updated `demo/nativelink/README.md` |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `demo/nativelink/lre.json5`, `demo/nativelink/README.md` |
| no_touch | `scripts/**`, `tests/**`, `.github/**` |
| proof_commands | `grep -n '50071\|50081' demo/nativelink/lre.json5`; `grep -n 'lre_substrate_ready\|claim_boundary' demo/nativelink/README.md` |
| privacy_tier | `private_internal` |
| stop_conditions | Do not claim Nix `--config=lre` parity or fleet dashboards |
| return_status | DONE |

---

## Deliverables

- `lre.json5` with dedicated ports `50071` (public) / `50081` (worker API), one `local` worker
- README **LRE Substrate (phase 1)** with `lre_substrate_ready`, `claim_boundary`, truth labels, port collision notes
