# Provenance — fel-w1-handoffs

**Worker:** `fel-w1-handoffs`  
**Wave:** 1  
**Coordinator:** `coord-fleet-evidence-v1`  
**Write scope:** `docs/dags/fleet-evidence-v1.md`, `docs/dags/README.md` (fleet-evidence section), `docs/sessions/handoffs/fleet-evidence-v1/wave-1/**`, `docs/sessions/handoffs/README.md` (fleet row)  
**Status:** `DONE`

---

## Executive summary

Closed wave-1 broker handoffs for fleet-evidence-v1: updated DAG mirror to wave-1
`stdout_ingest_breadth` ceiling, spawn ledger, integration brief, and
`worker-results.json`. Documented `fel-w1-agent-coldwarm-attach` as **PENDING**
— agent-loop and cold-warm stdout attach exists only in uncommitted working-tree
diffs at handoff close, not on `HEAD`.

---

## Inputs read

| Artifact | Path |
|----------|------|
| Wave-0 handoffs | `docs/sessions/handoffs/fleet-evidence-v1/wave-0/` |
| Capture research | `docs/sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md` |
| GHA offline policy | `docs/sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md` |
| Frontier ship packet | `docs/sessions/handoffs/frontier-wave/wave-0/ship-packet.md` |
| Pending script diffs | `git diff HEAD -- scripts/agent-loop-proof.sh scripts/cold-warm-cache-proof.sh` |

---

## Deliverables written

| File | Action |
|------|--------|
| `docs/dags/fleet-evidence-v1.md` | Updated — wave-1 status, ceiling, handoffs path |
| `docs/dags/README.md` | Updated — fleet-evidence section (wave-1 ceiling) |
| `docs/sessions/handoffs/fleet-evidence-v1/wave-1/spawn-ledger.md` | Created |
| `docs/sessions/handoffs/fleet-evidence-v1/wave-1/integration-brief.md` | Created |
| `docs/sessions/handoffs/fleet-evidence-v1/wave-1/worker-results.json` | Created |
| `docs/sessions/handoffs/README.md` | Updated — fleet-evidence-v1 wave-1 row |
| This file | Created |

---

## Proof (local — GHA offline substitute)

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
# 10 passed

bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh \
  scripts/agent-loop-proof.sh scripts/cold-warm-cache-proof.sh

test -f docs/sessions/handoffs/fleet-evidence-v1/wave-1/spawn-ledger.md && echo OK
grep -n 'stdout_ingest_breadth\|wave-1' docs/dags/fleet-evidence-v1.md
```

CI deferral: per `gha-offline-proof-shift.md`, parent does not block on Actions green.

---

## Claims touched

- Documentation sync for wave-1 target ceiling (`stdout_ingest_breadth`)
- Honest `PENDING` on agent-loop + cold-warm attach until `fel-w1-agent-coldwarm-attach` merges

## Blockers

- `fel-w1-agent-coldwarm-attach` not merged at handoff close — wave-1 integration brief status `DONE_WITH_CONCERNS`
