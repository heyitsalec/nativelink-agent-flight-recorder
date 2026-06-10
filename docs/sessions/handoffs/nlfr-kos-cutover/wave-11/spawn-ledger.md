# Spawn ledger — nlfr-kos-cutover wave 11 (`adoption-init-path`)

**DAG:** [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) § Wave 11  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-11 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| nlfr-init | coord-nlfr-init | worker | `src/nlfr/commands/init_cmd.py`, `tests/test_init_cmd.py`, `docs/ADOPTION_GUIDE.md` | `W11-NLFR-INIT` | DONE |
| adapter-pattern | coord-adapter-pattern | worker | `docs/wiki/how-to/adopt-existing-bazel-monorepo.md`, `docs/wiki/reference/cli.md` | `W11-ADAPTER-PATTERN` | DONE |
| one-command | coord-one-command | worker | `scripts/record-this-target.sh`, `scripts/record-proof.sh` | `W11-ONE-COMMAND` | DONE |
| w11-integrate | coord-w11-integrate | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-11/**` | `W11-INTEGRATE` | DONE |

**Dispatch order:** `nlfr-init` + `adapter-pattern` parallel after W10 close; `one-command` after init; integrate last.

**Proof gate:**

```bash
PYTHONPATH=src uv run python -m nlfr init --help
uv run pytest tests/test_init_cmd.py -q
./scripts/record-this-target.sh
```

**Stop condition:** No monorepo migration tooling; adapter pattern docs only.
