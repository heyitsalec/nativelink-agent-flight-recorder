# Spawn ledger — nlfr-kos-cutover wave 2 (`agent-provenance-live`)

**DAG:** `docs/dags/nlfr-kos-roadmap.md` § Wave 2  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-2 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| agent-live-e2e | coord-agent-live-e2e | worker | `scripts/record-agent-change.sh`, `scripts/agent-live-proof.sh` | `W2-AGENT-E2E` | DONE |
| agent-proof-samples | coord-agent-proof-samples | worker | `docs/proof-samples/agent-live-*` | `W2-AGENT-PROOF` | DONE |
| agent-adapter-docs | coord-agent-adapter-docs | worker | `adapters/cursor/**` | `W2-ADAPTER-DOCS` | DONE |
| w2-integrate | waves-1-4-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-2/**` | `W2-INTEGRATE` | DONE |

**Dispatch order:** `agent-live-e2e` + `agent-adapter-docs` parallel after W1 close; `agent-proof-samples` after E2E; integrate last.

**Proof gate (local — GHA offline; Cursor CLI missing):**

```bash
./scripts/agent-live-proof.sh --dry-run
uv run pytest tests/test_agent_live_proof.py tests/test_agent_live_proof_samples.py -q
```

**Ceiling:** blocker sample when Cursor CLI unavailable — no fake collectable live run.
