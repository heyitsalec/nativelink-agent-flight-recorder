# Spawn ledger — nlfr-kos-cutover wave 1 (`tier1-canvas-polish`)

**DAG:** `docs/dags/tier1-canvas-polish.md`  
**Umbrella:** `docs/dags/nlfr-kos-roadmap.md`  
**Branch:** `feat/docs-wiki-wave2` → `feat/nlfr-kos-cutover`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship` · `linear_authority: false`  
**KOS:** `docs/sessions/handoffs/nlfr-kos-cutover/wave-1/KOS-startup-routing.md`

## Wave-1 ARM

| agent | type | write_scope | status |
|-------|------|-------------|--------|
| broker-parent | parent | — | ARMED |
| wave1-arm-handoffs | worker | `docs/dags/tier1-canvas-polish.md`, `docs/sessions/handoffs/nlfr-kos-cutover/wave-1/**` | DONE |

**Wave-1 ARM ceiling:** DAG mirror, KOS routing, spawn ledger — no implementer spawn in ARM worker.

## Wave-1 coordinators → workers (closed 2026-06-06)

| worker_id | coordinator | type | write_scope | KOS node | status |
|-----------|-------------|------|-------------|----------|--------|
| canvas-ux-polish | coord-canvas-ux-polish | worker | `apps/canvas/src/components/**`, `apps/canvas/src/styles/**` | `W1-CANVAS-UX` | DONE |
| run-group-selector | coord-run-group-selector | worker | `apps/canvas/src/**/RunSelector*`, `apps/canvas/public/views/**` | `W1-RUN-SELECTOR` | DONE |
| canvas-readme | coord-canvas-readme | worker | `apps/canvas/README.md` | — | DONE |
| canvas-screenshots | coord-canvas-screenshots | worker | `scripts/record-canvas-build.sh`, `apps/canvas/tests/**`, `docs/images/canvas/**` | `W1-SCREENSHOTS` | DONE (partial — GIF refresh; full baseline deferred) |
| w1-integrate | waves-1-4-integrate-close | worker | `docs/sessions/handoffs/nlfr-kos-cutover/wave-1/integration-brief.md`, `worker-results.json`, KOS `W1-INTEGRATE` close | `W1-INTEGRATE` | DONE |

**Dispatch order:** spawn `canvas-ux-polish`, `run-group-selector`, and `canvas-readme` in parallel;
spawn `canvas-screenshots` after UX + selector workers close; parent runs `w1-integrate` last.

**Proof gate (local — GHA offline):**

```bash
npm --prefix apps/canvas run test:truth
npm --prefix apps/canvas run build
./scripts/record-canvas-build.sh
uv run pytest -q
```
