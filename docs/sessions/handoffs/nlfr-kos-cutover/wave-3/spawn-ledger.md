# Spawn ledger — nlfr-kos-cutover wave 3 (`lre-linux-manual-proof`)

**DAG:** `docs/dags/nlfr-kos-roadmap.md` § Wave 3  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-3 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| lre-linux-runbook | coord-lre-linux-runbook | worker | `docs/LRE_LINUX_PROOF.md`, `docs/DEV_ENVIRONMENT.md` | `W3-LINUX-RUNBOOK` | DONE |
| lre-sample-promote | coord-lre-sample-promote | worker | `docs/proof-samples/lre-cold-warm-proof-*` | `W3-SAMPLE-PROMOTE` | DONE |
| lre-ladder-sync | coord-lre-ladder-sync | worker | `docs/dags/lre-proof.md`, `docs/dags/future-execution-ladder.md` | `W3-LADDER-SYNC` | DONE |
| w3-integrate | waves-1-4-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-3/**` | `W3-INTEGRATE` | DONE |

**Dispatch order:** `lre-linux-runbook` + `lre-ladder-sync` parallel after W2 close; `lre-sample-promote` after runbook; integrate last.

**Proof gate (local — GHA offline; Darwin host):**

```bash
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
```

**Ceiling:** blocker sample on Darwin — do not claim Linux parity.
