# LRE Wave 2 — Task Packet: lre-w2-proof-script

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-lre-proof` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `lre-w2-proof-script` |
| coordinator_id | `coord-lre-proof` |
| dag_ref | `lre-proof` / wave-2 |
| objective | Verify `lre-proof.sh` probe → blocker or delegate → `summary.json` with `lre_substrate_ready` |
| expected_output | Verified `scripts/lre-proof.sh`, synced `docs/proof-samples/lre-proof-*-sample.json` |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `scripts/lre-proof.sh`, `docs/proof-samples/**` |
| no_touch | `demo/nativelink/lre.json5` (config-readme worker), `tests/**` |
| proof_commands | `bash -n scripts/lre-proof.sh`; blocker smoke with stub bins; `uv run pytest tests/test_lre_proof.py -q` |
| privacy_tier | `private_internal` |
| stop_conditions | Do not invent LRE claims beyond `claim_boundary` |
| return_status | DONE |

---

## Deliverables

- Script: probe → `environment-blocker.json` (exit 2) or delegate to `local-exec-proof.sh` on LRE ports
- Summary: `status: lre_substrate_ready`, `claim_boundary.unsupported_until_nix_lre_toolchain`
- Proof samples aligned with script output schema
