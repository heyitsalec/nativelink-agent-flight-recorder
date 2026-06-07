# Spawn ledger — nlfr-kos-cutover wave 13 (`operator-console-ergonomics`)

**DAG:** [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) § Wave 13  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship`

## Wave-13 workers

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| canvas-8node-cap | coord-canvas-8node-cap | worker | `apps/canvas/src/pageModel.ts`, `tests/test_canvas_node_cap.py` | `W13-CANVAS-8NODE-CAP` | DONE |
| lens-ergonomics | coord-lens-ergonomics | worker | `apps/canvas/src/panels/TablePanel.tsx`, `apps/canvas/src/styles.css`, `apps/canvas/scripts/truth-guard.mjs` | `W13-LENS-ERGONOMICS` | DONE |
| failure-messages | coord-failure-messages | worker | `src/nlfr/commands/doctor.py`, `src/nlfr/commands/init_cmd.py`, `tests/test_doctor.py` | `W13-FAILURE-MESSAGES` | DONE |
| w13-integrate | coord-w13-integrate | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-13/**`, `docs/dags/nlfr-kos-roadmap-waves-10-13.md` | `W13-INTEGRATE` | DONE |

**Dispatch order:** `canvas-8node-cap` + `lens-ergonomics` parallel after W12 close; `failure-messages` after W11 (doctor/init); integrate last.

**Proof gate:**

```bash
uv run pytest tests/test_canvas_node_cap.py tests/test_doctor.py -q
npm --prefix apps/canvas run test:truth
uv run pytest -q
```

**Stop condition:** No fleet parsers; ergonomics only; 8-node cap is product constraint.
