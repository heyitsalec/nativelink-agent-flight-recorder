# Spawn ledger — nlfr-kos-cutover wave 5 (`live-proof-residual`)

**DAG:** `docs/dags/nlfr-kos-roadmap-waves-5-8.md` § Wave 5  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-5 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| m8-live-residual | coord-m8-live-residual | worker | `scripts/agent-live-proof.sh`, `scripts/record-agent-change.sh`, `tests/test_agent_live_proof.py` | `W5-M8-LIVE` | DONE |
| lre-linux-residual | coord-lre-linux-residual | worker | `scripts/lre-cold-warm-proof.sh`, `docs/proof-samples/lre-cold-warm-proof-*`, `tests/test_lre_proof.py` | `W5-LRE-LINUX` | DONE |
| live-proof-docs | coord-live-proof-docs | worker | `adapters/cursor/README.md`, `docs/LRE_LINUX_PROOF.md`, `docs/proof-samples/README.md` | `W5-LIVE-DOCS` | DONE |
| w5-integrate | waves-5-8-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-5/**` | `W5-INTEGRATE` | DONE |

**Dispatch order:** `m8-live-residual` + `lre-linux-residual` + `live-proof-docs` parallel after W4 close; integrate last.

**Proof gate (local — GHA offline):**

```bash
uv run pytest tests/test_agent_live_proof.py tests/test_lre_proof.py -q
bash -n scripts/agent-live-proof.sh scripts/lre-cold-warm-proof.sh
```

**Stop condition:** Honest environment blockers accepted; do not block waves 6–8.
