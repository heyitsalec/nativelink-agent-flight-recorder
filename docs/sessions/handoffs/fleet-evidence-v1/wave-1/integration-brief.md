# Wave 1 Integration Brief — Fleet evidence v1 (stdout breadth)

**Date:** 2026-06-06  
**Coordinator:** `coord-fleet-evidence-v1`  
**Status:** DONE_WITH_CONCERNS (handoffs closed; script attach worker pending)  
**Target ceiling:** `stdout_ingest_breadth` (`collectable_v1`, `high`)

---

## Landed (committed on branch)

| Layer | Artifact | Claim |
|-------|----------|-------|
| Script | `scripts/local-exec-proof.sh` | Attach stdout/stderr via `write_artifact` before ingest (wave-0) |
| Script | `scripts/worker-evidence-proof.sh` | Live path relies on local-exec attach (wave-0) |
| Parser | `src/nlfr/ingest/worker_admin_stdout.py` | M7 regex path — `worker_identity` when stdout matches |
| DAG | `docs/dags/fleet-evidence-v1.md` | Broker mirror + proof commands + wave-1 ceiling |
| Handoffs | `wave-1/spawn-ledger.md`, this brief, provenance | Broker closure for wave-1 |

---

## Pending (`fel-w1-agent-coldwarm-attach`)

| Script | Intended change | Status |
|--------|-----------------|--------|
| `scripts/agent-loop-proof.sh` | Split simulate/ingest; `write_artifact` for stdout/stderr pre-ingest | **PENDING** — diff in working tree, not on `HEAD` |
| `scripts/cold-warm-cache-proof.sh` | `attach_nativelink_logs` per cold/warm leg pre-ingest | **PENDING** — diff in working tree, not on `HEAD` |

Until that worker lands, wave-1 **does not** claim stdout pre-ingest on agent-loop or cold-warm paths in committed code. Summaries may still list `nativelink.stdout.txt` in `evidence_refs` without ingestible attachment.

---

## Proof (local parent gates — GHA offline)

```bash
uv run pytest tests/test_worker_admin_stdout.py tests/test_worker_readiness.py -q
# 10 passed

bash -n scripts/local-exec-proof.sh scripts/worker-evidence-proof.sh \
  scripts/agent-loop-proof.sh scripts/cold-warm-cache-proof.sh
```

**Not required for ship:** GitHub Actions green (`nlfr-proof.yml` cold-warm/agent-loop jobs). Parent records pass/fail locally per [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).

Fixture replay when toolchain absent:

```bash
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh
```

---

## Honesty / claim boundary

**Supported on committed branch (wave-0 paths):**

- `nativelink.stdout.txt` and `nativelink.stderr.txt` in `artifact_root` before ingest on local-exec + worker-evidence
- `worker_identity` promotion when M7 regex matches attached stdout (fixture-backed today)
- `worker_endpoints_ready` via existing readiness probe (unchanged)

**Target after `fel-w1-agent-coldwarm-attach` lands:**

- Same stdout/stderr attach pattern on `agent-loop-proof.sh` and `cold-warm-cache-proof.sh`
- Conditional `worker_identity` on those proof paths when admin lines appear in attached stdout

**Still unsupported (any wave):**

- stderr-based fleet claims
- scheduler / queue / action placement / load distribution
- fleet ops canvas dashboards

Matrix sync: `./scripts/fleet-claims-audit.sh` · [future-fleet-claims.md](../../../dags/future-fleet-claims.md)

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-fel-w1-handoffs.md`
- Wave-0 research: `../wave-0/research-nativelink-stdout-formats.md`
- DAG mirror: `docs/dags/fleet-evidence-v1.md`
- GHA offline policy: `docs/sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md`
