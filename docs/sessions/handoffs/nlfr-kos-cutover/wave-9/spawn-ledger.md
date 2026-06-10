# Spawn ledger — nlfr-kos-cutover wave 9 (`kos-operator-bridge`)

**DAG:** `docs/dags/nlfr-kos-roadmap-waves-5-8.md` § Wave 9  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-9 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| kos-cutover-manifest | coord-kos-cutover-manifest | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-9/cutover-manifest.json`, `KOS-startup-routing.md` | `W9-CUTOVER-MANIFEST` | DONE |
| kos-handoff-bridge | coord-kos-handoff-bridge | worker | `docs/sessions/handoffs/nlfr-kos-cutover/README.md` | `W9-HANDOFF-BRIDGE` | DONE |
| kos-gap-honesty | coord-kos-gap-honesty | worker | `wave-9/gap-honesty-packet.md`, `docs/dags/future-execution-ladder.md`, `docs/dags/README.md` | `W9-GAP-HONESTY` | DONE |
| w9-integrate | coord-kos-umbrella-integrate | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-9/**`, `docs/dags/nlfr-kos-roadmap-waves-10-13.md` | `W9-INTEGRATE` | DONE |

**Dispatch order:** `kos-cutover-manifest`, `kos-handoff-bridge`, `kos-gap-honesty` parallel after W8 close; integrate last.

**Proof gate:**

```bash
python3 -m json.tool docs/sessions/handoffs/nlfr-kos-cutover/wave-9/cutover-manifest.json
uv run pytest -q
# When kos serve running:
curl -sS 'http://127.0.0.1:7423/v1/dag/dag%3Anlfr-flagship/frontier'
```

**Stop condition:** No Harmony/Electron code in NLFR repo; cross-repo coupling documented only.
