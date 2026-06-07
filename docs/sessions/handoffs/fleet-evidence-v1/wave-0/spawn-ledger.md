# Spawn ledger — fleet-evidence-v1 wave-0

**Coordinator:** `coord-fleet-evidence-v1`  
**DAG:** `docs/dags/fleet-evidence-v1.md`  
**Branch:** `feat/frontier-wave`  
**KOS:** `docs/sessions/handoffs/frontier-wave/wave-0/KOS-startup-routing.md`

| worker_id | type | write_scope | status | provenance |
|-----------|------|-------------|--------|------------|
| fel-w0-scripts-capture | worker | `scripts/local-exec-proof.sh`, `scripts/worker-evidence-proof.sh`, `docs/sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md` | DONE | `provenance-fel-w0-scripts-capture.md` |
| fel-w0-handoffs | worker | `docs/dags/fleet-evidence-v1.md`, `docs/dags/README.md`, `docs/sessions/handoffs/fleet-evidence-v1/wave-0/**`, `docs/sessions/handoffs/README.md`, `docs/proof-samples/README.md` | DONE | `provenance-fel-w0-handoffs.md` |

**Ceiling:** `stdout_ingest_local_exec` (`collectable_v1`, `high`) — attach admin stdout on local-exec + worker-evidence paths; no fleet UI.

**Proof gate:**

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh
```
