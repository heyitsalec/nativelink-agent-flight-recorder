# Future fleet claims Wave 1 — Task Packet: ffc-w1-audit-tests

## KOS arming (mandatory)

Read before acting: [`../../unlock-wave/KOS-startup-routing.md`](../../unlock-wave/KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-future-fleet-claims` · Phase: implement

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ffc-w1-audit-tests` |
| coordinator_id | `coord-future-fleet-claims` |
| dag_ref | `future-fleet-claims` / wave-1 |
| objective | Fixture-free pytest contract for fleet claim matrix schema and CLI path |
| expected_output | `tests/test_fleet_claims_audit.py` (4 tests, no live NativeLink) |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `tests/test_fleet_claims_audit.py` |
| no_touch | `scripts/**` (read-only import), `docs/**` |
| proof_commands | `uv run pytest tests/test_fleet_claims_audit.py -q` |
| privacy_tier | `private_internal` |
| stop_conditions | Tests lock research matrix contract only — not fleet dashboards |
| return_status | DONE |

---

## Test matrix

| Test | Validates |
|------|-----------|
| `test_build_matrix_claim_schema` | Top-level truth labels + per-claim row keys |
| `test_build_matrix_includes_all_unsupported_claims` | Rows match `UNSUPPORTED_REMOTE_EXECUTION_CLAIMS` exactly |
| `test_worker_identity_row_documents_parser` | `worker_identity` names parser + proof block |
| `test_fleet_claims_audit_subprocess_writes_matrix` | CLI `--output` writes valid JSON matrix |
