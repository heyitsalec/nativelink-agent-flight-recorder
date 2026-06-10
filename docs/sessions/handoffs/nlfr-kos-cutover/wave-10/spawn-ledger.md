# Spawn ledger — nlfr-kos-cutover wave 10 (`gha-sustained-green`)

**DAG:** [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) § Wave 10  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-10 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| gha-restore | coord-gha-readiness | worker | `scripts/verify-gha-readiness.sh`, `data/verify-gha-readiness/` | `W10-GHA-RESTORE` | DONE |
| ci-docs | coord-gha-ci-docs | worker | `docs/GHA_RESTORE_RUNBOOK.md`, `docs/CI_RECIPE.md`, `docs/proof-samples/ci-offline-blocker-sample.json` | `W10-CI-DOCS` | DONE |
| ci-promote | coord-gha-readiness | worker | `docs/proof-samples/CI_PROMOTION_MATRIX.md`, `wave-9/gap-honesty-packet.md` | `W10-CI-PROMOTE` | BLOCKED |
| w10-integrate | coord-w10-integrate | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-10/**` | `W10-INTEGRATE` | DONE |

**Dispatch order:** `gha-restore` + `ci-docs` parallel after W9 close; `ci-promote` blocked on sustained GHA green; integrate last.

**Proof gate:**

```bash
./scripts/verify-gha-readiness.sh
./scripts/cache-only-ci-gate.sh
uv run pytest -q
# When GHA returns:
gh workflow run nlfr-proof.yml
gh workflow run nlfr-cache-only-gate.yml
```

**Stop condition:** GHA offline documented honestly; no secrets in runbooks; local gates substitute per gha-offline-proof-shift policy.
