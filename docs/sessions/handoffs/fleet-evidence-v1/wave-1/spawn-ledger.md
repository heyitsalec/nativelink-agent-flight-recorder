# Spawn ledger — fleet-evidence-v1 wave-1

**Coordinator:** `coord-fleet-evidence-v1`  
**DAG:** `docs/dags/fleet-evidence-v1.md`  
**Branch:** `feat/frontier-wave`  
**KOS:** `docs/sessions/handoffs/frontier-wave/wave-0/KOS-startup-routing.md`

| worker_id | type | write_scope | status | provenance |
|-----------|------|-------------|--------|------------|
| fel-w1-agent-coldwarm-attach | worker | `scripts/agent-loop-proof.sh`, `scripts/cold-warm-cache-proof.sh` | **PENDING** | (not landed — working-tree diff only at handoff close) |
| fel-w1-handoffs | worker | `docs/dags/fleet-evidence-v1.md`, `docs/dags/README.md` (fleet section), `docs/sessions/handoffs/fleet-evidence-v1/wave-1/**`, `docs/sessions/handoffs/README.md` (fleet row) | DONE | `provenance-fel-w1-handoffs.md` |

**Target ceiling:** `stdout_ingest_breadth` (`collectable_v1`, `high`) — attach admin stdout/stderr pre-ingest on local-exec, worker-evidence, agent-loop, and cold-warm proof paths; no fleet UI.

**Ceiling at handoff close:** wave-0 paths **landed** on branch; agent-loop + cold-warm attach **pending** until `fel-w1-agent-coldwarm-attach` merges.

**Proof gate (local — GHA offline):**

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh \
  scripts/agent-loop-proof.sh scripts/cold-warm-cache-proof.sh
```

CI green is **not** a ship gate. See [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).
