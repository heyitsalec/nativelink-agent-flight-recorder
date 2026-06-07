# Spawn ledger — nlfr-kos-cutover waves 10–13 (`gha-sustained-green` ARM)

**DAG:** [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md)  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-10 ARM

| agent | type | write_scope | status |
|-------|------|-------------|--------|
| broker-parent | parent | — | ARMED |
| wave10-arm-handoffs | worker | `docs/dags/nlfr-kos-roadmap-waves-10-13.md`, `docs/sessions/handoffs/nlfr-kos-cutover/wave-10/**` | DONE |

**Wave-10 ARM ceiling:** roadmap authority, KOS routing, spawn ledger, seed invocation — no
implementer spawn in ARM worker.

## Wave-10 coordinators → workers (planned)

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| gha-restore | coord-gha-restore | worker | `.github/workflows/nlfr-proof.yml`, `.github/workflows/nlfr-cache-only-gate.yml` | `W10-GHA-RESTORE` | PLANNED |
| ci-docs | coord-ci-docs | worker | `docs/GHA_RESTORE_RUNBOOK.md`, `docs/CI_RECIPE.md` | `W10-CI-DOCS` | PLANNED |
| ci-promote | coord-ci-promote | worker | `docs/proof-samples/CI_PROMOTION_MATRIX.md`, `wave-9/gap-honesty-packet.md` | `W10-CI-PROMOTE` | PLANNED |
| w10-integrate | coord-w10-integrate | worker | `wave-10/**`, KOS `W10-INTEGRATE` close | `W10-INTEGRATE` | PLANNED |

**Dispatch order:** spawn `gha-restore` and `ci-docs` in parallel after seed; spawn `ci-promote`
after restore closes or documents honest blocker; parent runs `w10-integrate` last.

## Waves 11–13 (KOS seeded, spawn deferred)

| Wave | id | Integrate | Seed nodes | status |
|------|----|-----------|------------|--------|
| 11 | `adoption-init-path` | `W11-INTEGRATE` | `W11-NLFR-INIT`, `W11-ADAPTER-PATTERN`, `W11-ONE-COMMAND` | STUB |
| 12 | `multi-run-history-v1` | `W12-INTEGRATE` | `W12-HISTORY-INDEX`, `W12-HISTORY-PROJECTION`, `W12-HISTORY-WIKI` | STUB |
| 13 | `operator-console-ergonomics` | `W13-INTEGRATE` | `W13-CANVAS-8NODE-CAP`, `W13-LENS-ERGONOMICS`, `W13-FAILURE-MESSAGES` | STUB |

Handoff dirs `wave-11/` … `wave-13/` created at integrate time.

**Proof gate (wave 10):**

```bash
gh workflow run nlfr-proof.yml
gh workflow run nlfr-cache-only-gate.yml
uv run pytest -q
./scripts/cache-only-ci-gate.sh
# When kos serve running:
python3 tools/orchestrator/scripts/seed_nlfr_flagship_waves_10_13.py   # knowledge-os
curl -sS 'http://127.0.0.1:7423/v1/dag/dag%3Anlfr-flagship/frontier'
```

**Stop condition:** No fleet parsers, no Harmony code in NLFR repo; GHA secrets stay out of docs.
