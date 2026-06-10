# Spawn ledger — nlfr-kos-cutover wave 6 (`retention-policy-v1`)

**DAG:** `docs/dags/nlfr-kos-roadmap-waves-5-8.md` § Wave 6  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-6 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| retention-policy-core | coord-retention-policy-core | worker | `src/nlfr/retention_policy.py`, `src/nlfr/projectors/proof_packet.py`, `tests/test_retention_policy.py` | `W6-RETENTION-POLICY` | DONE |
| retention-cli | coord-retention-cli | worker | `src/nlfr/commands/compare_cmd.py`, `tests/test_compare.py` | `W6-RETENTION-CLI` | DONE |
| retention-wiki | coord-retention-wiki | worker | `docs/wiki/how-to/export-and-compare-run-groups.md`, `docs/wiki/reference/contracts/compare-projection-v1.md`, `docs/USEFULNESS_ROADMAP.md` | `W6-RETENTION-WIKI` | DONE |
| w6-integrate | waves-5-8-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-6/**` | `W6-INTEGRATE` | DONE |

**Dispatch order:** all implementers parallel after W5 close; integrate last.

**Proof gate:**

```bash
uv run pytest tests/test_retention_policy.py tests/test_compare.py -q
```

**Stop condition:** No destructive purge CLI — index-only semantics only.
