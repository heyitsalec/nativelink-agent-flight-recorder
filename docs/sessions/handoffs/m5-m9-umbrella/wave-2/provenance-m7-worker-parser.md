# Wave 2 M7 Worker Parser Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Agent:** M7 worker evidence parser

## Deliverables

| Path | Purpose |
|------|---------|
| `src/nlfr/ingest/worker_admin_stdout.py` | Conservative regex parser for `Worker <name> started` and `worker_name=` lines |
| `src/nlfr/commands/ingest_cmd.py` | Ingest `nativelink.stdout.txt` → `worker_admin_identity_v1` proof block when direct rows exist |
| `src/nlfr/projectors/graph.py` | Worker nodes + `observed_worker_identity` edges from `remote_execution_config` |
| `src/nlfr/projectors/remote_execution.py` | Per-run unsupported-claim filtering and `worker_identity_observed` metric |
| `src/nlfr/projectors/proof.py` | Promote `worker_identity` in remote execution block when direct rows exist |
| `tests/fixtures/worker-admin/nativelink.stdout.txt` | Redacted 4-line sample with fake worker names |
| `tests/test_worker_admin_stdout.py` | Parser, ingest, and projection tests |
| `scripts/worker-evidence-proof.sh` | Fixture replay (default) or local-exec when nix PATH available |

## Truth labels

- Parsed worker identity rows: `collectable_v1`, confidence `high`, `redaction_state` `safe`
- Worker graph nodes carry the same labels from direct log evidence
- `worker_identity` removed from `unsupported_claims` only when SQLite has direct parsed rows for that run
- Other four unsupported claims remain explicit: `action_placement`, `queue_time`, `scheduler_assignment`, `load_distribution`

## Proof matrix

| # | Command | Exit | Result | Key artifacts |
|---|---------|------|--------|---------------|
| 1 | `uv run pytest -q` | 0 | PASS | 55 passed |
| 2 | `./scripts/worker-evidence-proof.sh` | 0 | PASS (fixture-replay) | `data/worker-evidence-proof/summary.json`, `worker_identity_observed: true`, `worker_nodes: 2` |

## Summary

M7 promotes `worker_identity` from NativeLink admin stdout when conservative regex matches produce direct rows in SQLite. Graph and proof projectors add worker nodes and drop `worker_identity` from unsupported claims for runs with evidence; queue time and scheduler assignment remain unproven.
