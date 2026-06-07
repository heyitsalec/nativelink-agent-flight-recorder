# LRE Wave 2 — Task Packet: lre-w2-ci-probe

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-lre-proof` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `lre-w2-ci-probe` |
| coordinator_id | `coord-lre-proof` |
| dag_ref | `lre-proof` / wave-2 |
| objective | CI `lre-proof-probe` job proves substrate green (`summary.json`) or honest blocker |
| expected_output | Updated `.github/workflows/nlfr-proof.yml` `lre-proof-probe` job |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `.github/workflows/nlfr-proof.yml` |
| no_touch | `scripts/**`, `tests/**`, `demo/**` |
| proof_commands | YAML parse; grep `data/lre-proof/summary.json` in `lre-proof-probe` section |
| privacy_tier | `private_internal` |
| stop_conditions | Job must upload `summary.json` when green, `environment-blocker.json` when blocked |
| return_status | DONE |

---

## Deliverables

- Job name: **LRE substrate proof**
- Run: `nix develop --command ./scripts/lre-proof.sh`
- Artifacts: `summary.json`, `probe.json`, `environment-blocker.json` (when present)
