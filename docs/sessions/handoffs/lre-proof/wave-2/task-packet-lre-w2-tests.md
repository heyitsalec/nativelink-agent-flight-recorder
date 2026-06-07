# LRE Wave 2 — Task Packet: lre-w2-tests

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-lre-proof` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `lre-w2-tests` |
| coordinator_id | `coord-lre-proof` |
| dag_ref | `lre-proof` / wave-2 |
| objective | Fixture-backed tests for LRE blocker, port validation, probe metadata, and summary shape |
| expected_output | Expanded `tests/test_lre_proof.py` (4 tests, no live NativeLink) |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `tests/test_lre_proof.py` |
| no_touch | `scripts/**`, `demo/nativelink/**`, `.github/**` |
| proof_commands | `uv run pytest tests/test_lre_proof.py -q` |
| privacy_tier | `private_internal` |
| stop_conditions | Tests must not claim end-to-end Nix LRE without toolchain |
| return_status | DONE |

---

## Test matrix

| Test | Validates |
|------|-----------|
| `test_lre_proof_records_blocker_without_config` | Missing config → `environment-blocker.json` + exit 2 |
| `test_lre_json5_port_validation` | `lre.json5` uses 50071/50081 |
| `test_lre_proof_probe_when_config_present` | Probe records `lre_config_present: true` |
| `test_lre_summary_shape_with_stubbed_delegation` | Summary schema matches proof sample |
