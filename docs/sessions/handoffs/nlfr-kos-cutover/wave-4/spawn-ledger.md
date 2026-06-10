# Spawn ledger — nlfr-kos-cutover wave 4 (`ci-restore-verify`)

**DAG:** `docs/dags/nlfr-kos-roadmap.md` § Wave 4  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-4 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| gha-restore | coord-gha-restore | worker | `.github/workflows/nlfr-proof.yml`, `scripts/*-ci-proof.sh`, `docs/GHA_RESTORE_RUNBOOK.md` | `W4-GHA-RESTORE` | DONE (docs-only) |
| ci-proof-promote | coord-ci-proof-promote | worker | `docs/proof-samples/**` | `W4-PROOF-PROMOTE` | DONE (docs-only) |
| ci-docs-sync | coord-ci-docs-sync | worker | `docs/CI_RECIPE.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/dags/README.md` | `W4-CI-DOCS` | DONE |
| w4-integrate | waves-1-4-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-4/**` | `W4-INTEGRATE` | DONE |

**Dispatch order:** `gha-restore` + `ci-docs-sync` parallel after W3 close; `ci-proof-promote` after gha-restore docs; integrate last.

**Proof gate (local — GHA offline):**

```bash
uv run pytest -q
bash -n scripts/*.sh
```

**Stop condition:** GHA offline — wave closes docs-only per gha-offline-proof-shift; no CI green claims.
