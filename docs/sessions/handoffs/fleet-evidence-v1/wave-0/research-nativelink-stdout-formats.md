# Research — NativeLink stdout/stderr formats (fleet-evidence-v1 wave-0)

**Worker:** `fleet-exec-scripts-capture`  
**Date:** 2026-06-06  
**Status:** research_only  
**Source kind:** `derived_v1` · **Confidence:** `high` · **Redaction:** `safe`

## Objective

Document what NativeLink admin process output NLFR can collect today, what the M7
parser recognizes, and where proof-script capture still leaves gaps before a
broader fleet-evidence rollout.

## Capture surfaces today

| Surface | stdout path | stderr path | Attached to `artifact_root` before ingest? |
|---------|-------------|-------------|---------------------------------------------|
| `NativeLinkRunner` (cache-only `nlfr run`) | `artifact_dir/nativelink.stdout.txt` | `artifact_dir/nativelink.stderr.txt` | Yes (runner writes into artifact dir) |
| `scripts/local-exec-proof.sh` | `$OUT/nativelink.stdout.txt` | `$OUT/nativelink.stderr.txt` | **Yes** (wave-0 fix: `write_artifact` before ingest) |
| `scripts/worker-evidence-proof.sh` (fixture) | copied from fixture | — | Yes (manual `cp` of fixture stdout) |
| `scripts/worker-evidence-proof.sh` (live) | via `local-exec-proof.sh` | via `local-exec-proof.sh` | Yes (no post-run `cp` workaround) |
| `scripts/agent-loop-proof.sh` | `$OUT/nativelink.stdout.txt` | `$OUT/nativelink.stderr.txt` | **No** — listed in `summary.json` only |
| `scripts/cold-warm-cache-proof.sh` | `$OUT/nativelink.stdout.txt` | `$OUT/nativelink.stderr.txt` | **No** — listed in `summary.json` only |

**Wave-0 scope:** `local-exec-proof.sh` + `worker-evidence-proof.sh` live path.  
**Remaining breadth gap:** `agent-loop-proof.sh` and `cold-warm-cache-proof.sh`
still capture stdout beside the run output tree but do not call `write_artifact`
before ingest.

## Parser contract (`worker_admin_stdout.py`)

Conservative regex extraction only; no structured log schema assumption.

| Pattern | Regex | Example (fixture) | Promoted claim |
|---------|-------|-------------------|----------------|
| Worker started | `Worker\s+(\S+)\s+started` (case-insensitive) | `INFO Worker worker-demo-alpha started` | `worker_identity` |
| Worker name KV | `worker_name=(\S+)` (case-insensitive) | `INFO Registering worker_name=worker-demo-beta` | `worker_identity` |

Ingest path: `artifact_root/nativelink.stdout.txt` → SQLite proof block
`worker_admin_identity_v1` when ≥1 event row parses. Stderr is **never** parsed
for fleet claims.

Fixture reference: `tests/fixtures/worker-admin/nativelink.stdout.txt`

## Observed format families (inferred / fixture-backed)

### A. Timestamped INFO lines (fixture + proof samples)

```
2026-06-06T12:00:01Z INFO NativeLink server starting on grpc://127.0.0.1:50051
2026-06-06T12:00:02Z INFO Worker worker-demo-alpha started
2026-06-06T12:00:03Z INFO Registering worker_name=worker-demo-beta
2026-06-06T12:00:04Z INFO Ready to accept remote execution connections
```

**Parser coverage:** lines 2–3 only. Server bind and readiness lines are
ignored (correct — no over-claim).

### B. Unstructured / alternate admin wording (gap)

Real NativeLink builds may emit variants not covered by M7 regex, for example:

- `worker "name" connected` or `Registered worker: name`
- JSON-per-line structured logging (`{"worker":"..."}`)
- Rust `tracing` spans without literal `Worker … started` text
- Multi-process supervisor logs merged into one stream

**Gap:** parser returns `[]` → ingest skips `worker_admin_identity_v1` →
`worker_identity` stays in `unsupported_claims`. No partial/fuzzy promotion.

### C. Stderr-only diagnostics (gap)

Port bind failures, config parse errors, and TLS handshake errors often land on
stderr (`local-exec-proof.sh` already dumps stderr tail on port-timeout).

**Gap:** no `worker_admin_stderr` parser; stderr attachment is provenance-only
for human triage, not SQLite proof blocks.

## Claim matrix vs stdout evidence

| `claim_id` | Collectable from stdout today? | Blocker |
|------------|-------------------------------|---------|
| `worker_identity` | Conditional — M7 regex on stdout | Alternate log formats; stdout not in all proof scripts' artifact roots |
| `scheduler_assignment` | No | No scheduler stdout / admin API parser |
| `queue_time` | No | No queue timestamp in stdout contract |
| `action_placement` | No | No per-action worker correlation in stdout |
| `load_distribution` | No | Identity lines ≠ work distribution |

Fleet audit ceiling unchanged: `scripts/fleet_claims_audit.py` ·
`docs/dags/future-fleet-claims.md`.

## Wave-0 script changes (implemented)

1. **`local-exec-proof.sh`** — extended `write_artifact` block to mirror
   `worker-readiness.json` attachment for `nativelink.stdout.txt` and
   `nativelink.stderr.txt` into `ARTIFACT_ROOT` before `nlfr ingest`.
2. **`worker-evidence-proof.sh`** — removed live-path `cp` of stdout into
   artifact root; relies on local-exec attachment.

## Recommended next waves

| Priority | Work | Rationale |
|----------|------|-----------|
| P1 | Attach stdout/stderr in `agent-loop-proof.sh` + `cold-warm-cache-proof.sh` | Same ingest gap as local-exec had; summaries already reference files |
| P2 | Capture one **redacted** real NativeLink stdout sample from `nix develop` smoke | Validate regex against production wording; extend fixture if needed |
| P3 | Document stderr triage keys (port bind, config path) | Operator playbook; still no claim promotion |
| P4 | New parser only with direct evidence spec | Scheduler / queue / placement require new proof block kinds |

## Evidence refs

- `src/nlfr/ingest/worker_admin_stdout.py`
- `src/nlfr/commands/ingest_cmd.py` (`_worker_admin_stdout_path`)
- `scripts/local-exec-proof.sh`
- `scripts/worker-evidence-proof.sh`
- `tests/fixtures/worker-admin/nativelink.stdout.txt`
- `tests/test_worker_admin_stdout.py`
- `docs/dags/future-fleet-claims.md`
