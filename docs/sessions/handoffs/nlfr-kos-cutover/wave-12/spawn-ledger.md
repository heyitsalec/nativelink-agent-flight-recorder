# Spawn ledger — nlfr-kos-cutover wave 12 (`multi-run-history-v1`)

**DAG:** [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) § Wave 12  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-12 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| history-index | coord-history-index | worker | `src/nlfr/commands/compare_cmd.py`, `tests/test_compare.py` | `W12-HISTORY-INDEX` | DONE |
| history-projection | coord-history-projection | worker | `src/nlfr/projectors/compare.py`, `tests/test_compare_history.py`, `apps/canvas/public/projections/run-history.json` | `W12-HISTORY-PROJECTION` | DONE |
| history-wiki | coord-history-wiki | worker | `docs/wiki/how-to/browse-run-history.md`, `docs/USEFULNESS_ROADMAP.md` | `W12-HISTORY-WIKI` | DONE |
| w12-integrate | coord-w12-integrate | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-12/**` | `W12-INTEGRATE` | DONE |

**Dispatch order:** `history-index` first; `history-projection` after index; `history-wiki` parallel after W11 close; integrate last.

**Proof gate:**

```bash
uv run pytest tests/test_compare_history.py tests/test_compare.py tests/test_retention_policy.py -q
PYTHONPATH=src uv run python -m nlfr compare history --help
```

**Stop condition:** No auto-purge/TTL jobs; no trend dashboards.
