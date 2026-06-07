# Knowledge OS startup routing — NLFR KOS cutover wave 1

**Mandatory read** for every coordinator and worker in the `tier1-canvas-polish` sub-DAG.

## Control plane (local-primary)

| Field | Value |
|-------|-------|
| **Serve URL** | `http://127.0.0.1:7423` — start with `python3 -m tools.kos_mcp.serve` from knowledge-os |
| **`dag_ref`** | `dag:nlfr-flagship` |
| **`linear_authority`** | `false` |
| **Linear mirror** | **disabled** — PER-* tickets are reference only; do not block on Linear MCP |
| **Frontier reads** | `GET /v1/dags`, `GET /v1/dag/dag%3Anlfr-flagship/frontier`, `GET /v1/cutover` |
| **Node status** | `apply_status_batch` via kos-mcp after worker close |

Verify before wave-1 coordinator spawn:

```bash
curl -sS http://127.0.0.1:7423/health
curl -sS http://127.0.0.1:7423/v1/cutover
curl -sS 'http://127.0.0.1:7423/v1/dags' | head -c 2000
curl -sS 'http://127.0.0.1:7423/v1/dag/dag%3Anlfr-flagship/frontier'
```

Harmony / operator GUI: `export KOS_SERVE_URL=http://127.0.0.1:7423`

## Startup read order

| Order | Doc |
|-------|-----|
| 1 | `AGENTS.md` |
| 2 | [`/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) — § Orchestration |
| 3 | [`docs/dags/nlfr-kos-roadmap.md`](../../../dags/nlfr-kos-roadmap.md) — wave 1 section |
| 4 | [`docs/dags/tier1-canvas-polish.md`](../../../dags/tier1-canvas-polish.md) |
| 5 | [`human-design-handoff.md`](../../m5-m9-umbrella/wave-4/human-design-handoff.md) — items 1–4 |
| 6 | [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) |
| 7 | [nlfr-kos-cutover integration brief](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/nlfr-kos-cutover/wave-0/integration-brief.md) |

## Active sub-DAGs (wave 1)

| Coordinator | KOS node | write_scope |
|-------------|----------|-------------|
| `coord-canvas-ux-polish` | `W1-CANVAS-UX` | `apps/canvas/src/components/**`, `apps/canvas/src/styles/**` |
| `coord-run-group-selector` | `W1-RUN-SELECTOR` | `apps/canvas/src/**/RunSelector*`, `apps/canvas/public/views/**` |
| `coord-canvas-screenshots` | `W1-SCREENSHOTS` | `scripts/record-canvas-build.sh`, `apps/canvas/tests/**`, `docs/images/canvas/**` |
| `coord-canvas-readme` | *(docs parallel)* | `apps/canvas/README.md` |

**Disjoint scopes:** UX polish must not touch `RunSelector*` files; selector coordinator owns
selector component tree only. Screenshots coordinator runs after UX + selector merge.

**Branch:** `feat/nlfr-kos-cutover` (spawn from merged `feat/docs-wiki-wave2`)

## Broker rules

- Coordinators return `DispatchManifest` only — no Task spawn.
- Parent is sole spawn authority; disjoint `write_scope` enforced.
- Frontier and node closure from **`kos serve`** for `dag:nlfr-flagship`; Linear is not primary.
- Canvas renders **projection JSON only** — no invented backend state, fleet, or scheduler claims.
- Every new UI claim carries truth-label vocabulary (`source_kind`, `confidence`, `evidence_refs`, `redaction_state`).
- Run selector reads compare index fixture or `nlfr compare index` export shape — `derived_v1` at best.
- GHA offline: local proof gates at close; do not block ship on CI green.
- Privacy: no secrets, credentials, raw private logs, or customer data in artifacts or docs.

## Proof posture

```bash
npm --prefix apps/canvas run test:truth
npm --prefix apps/canvas run build
./scripts/record-canvas-build.sh
uv run pytest -q   # when canvas test helpers touched
```

## KOS node prerequisites

| Node | Runnable when |
|------|---------------|
| `W1-CANVAS-UX` | wave-0 ARM complete |
| `W1-RUN-SELECTOR` | wave-0 ARM complete |
| `W1-SCREENSHOTS` | `W1-CANVAS-UX` + `W1-RUN-SELECTOR` closed |
| `W1-INTEGRATE` | all W1 implementers closed |
