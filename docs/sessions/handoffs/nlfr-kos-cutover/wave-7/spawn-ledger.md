# Spawn ledger — nlfr-kos-cutover wave 7 (`cache-only-ci-gate`)

**DAG:** `docs/dags/nlfr-kos-roadmap-waves-5-8.md` § Wave 7  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-7 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| cache-gate-script | coord-cache-gate-script | worker | `scripts/cache-only-ci-gate.sh`, `tests/test_doctor_cache_only_gate.py` | `W7-CACHE-GATE-SCRIPT` | DONE |
| cache-gate-workflow | coord-cache-gate-workflow | worker | `.github/workflows/nlfr-cache-only-gate.yml` | `W7-CACHE-GATE-WF` | DONE (docs-only) |
| cache-gate-docs | coord-cache-gate-docs | worker | `docs/CI_RECIPE.md`, `docs/ADOPTION_GUIDE.md`, `docs/GHA_RESTORE_RUNBOOK.md` | `W7-CACHE-GATE-DOCS` | DONE |
| w7-integrate | waves-5-8-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-7/**` | `W7-INTEGRATE` | DONE |

**Dispatch order:** `cache-gate-script` first; `cache-gate-workflow` after script; `cache-gate-docs` parallel after W6 close; integrate last.

**Proof gate (local — GHA offline):**

```bash
./scripts/cache-only-ci-gate.sh
uv run pytest tests/test_doctor_cache_only_gate.py -q
bash -n scripts/cache-only-ci-gate.sh
```

**Stop condition:** GHA offline — workflow lands but is not green-claimed.
