# Wave 0 Integration Brief — Fleet evidence v1 (stdout attach)

**Date:** 2026-06-06  
**Coordinator:** `coord-fleet-evidence-v1`  
**Status:** DONE  
**Ceiling:** `stdout_ingest_local_exec` (`collectable_v1`, `high`)

---

## Landed

| Layer | Artifact | Claim |
|-------|----------|-------|
| Script | `scripts/local-exec-proof.sh` | Attach stdout/stderr via `write_artifact` before ingest |
| Script | `scripts/worker-evidence-proof.sh` | Live path relies on local-exec attach (removed `cp` workaround) |
| Research | `research-nativelink-stdout-formats.md` | Capture surfaces, parser contract, gap matrix |
| Parser | `src/nlfr/ingest/worker_admin_stdout.py` | Pre-existing M7 regex path (unchanged in wave-0) |
| DAG | `docs/dags/fleet-evidence-v1.md` | Broker mirror + proof commands + next-wave gaps |

---

## Proof

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
# 10 passed

bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh
```

Fixture replay when toolchain absent:

```bash
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh
# → data/worker-evidence-proof/summary.json mode: fixture-replay
```

---

## Honesty / claim boundary

**Supported after wave-0:**

- `nativelink.stdout.txt` and `nativelink.stderr.txt` in `artifact_root` before ingest on the local-exec proof path
- `worker_identity` promotion when M7 regex matches attached stdout (fixture-backed today)
- `worker_endpoints_ready` via existing readiness probe (unchanged)

**Still unsupported:**

- stdout pre-ingest on `agent-loop-proof.sh` and `cold-warm-cache-proof.sh`
- stderr-based fleet claims
- scheduler / queue / action placement / load distribution
- fleet ops canvas dashboards

Matrix sync: `./scripts/fleet-claims-audit.sh` · [future-fleet-claims.md](../../../dags/future-fleet-claims.md)

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-fel-w0-scripts-capture.md`, `provenance-fel-w0-handoffs.md`
- Research: `research-nativelink-stdout-formats.md`
- DAG mirror: `docs/dags/fleet-evidence-v1.md`
