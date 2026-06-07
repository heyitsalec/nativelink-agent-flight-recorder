# Knowledge OS startup routing — Docs wiki wave 2

**Mandatory read** for every coordinator and worker in the docs-wiki-wave2 DAG.

## Control plane (local-primary)

| Field | Value |
|-------|-------|
| **Serve URL** | `http://127.0.0.1:7423` — start with `python3 -m tools.kos_mcp.serve` from knowledge-os |
| **`dag_ref`** | `dag:nlfr-flagship` |
| **`linear_authority`** | `false` |
| **Linear mirror** | optional / **disabled** for this DAG — do not block on Linear MCP |
| **Frontier reads** | `GET /v1/dags`, `GET /v1/dag/dag%3Anlfr-flagship/frontier`, `GET /v1/cutover` |

Verify before wave-1 spawn:

```bash
curl -sS http://127.0.0.1:7423/health
curl -sS http://127.0.0.1:7423/v1/cutover
curl -sS 'http://127.0.0.1:7423/v1/dags' | head -c 2000
```

Harmony / operator GUI: `export KOS_SERVE_URL=http://127.0.0.1:7423`

## Startup read order

| Order | Doc |
|-------|-----|
| 1 | `AGENTS.md` |
| 2 | [`/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) — § Orchestration |
| 3 | [`docs-excellence/wave-0/excellence-bar.md`](../../docs-excellence/wave-0/excellence-bar.md) |
| 4 | [`docs/dags/docs-wiki-wave2.md`](../../../dags/docs-wiki-wave2.md) |
| 5 | [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) |
| 6 | [nlfr-kos-cutover integration brief](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/nlfr-kos-cutover/wave-0/integration-brief.md) |

## Active sub-DAGs (wave-1)

| Coordinator | DAG slice | write_scope |
|-------------|-----------|-------------|
| `coord-historical-banners` | Historical doc hygiene | 7 legacy docs + `demo/nativelink/README.md` — banners only |
| `coord-broker-diagram` | Broker orchestration diagram | `docs/diagrams/broker-orchestration.md`, `docs/diagrams/README.md` |
| `coord-wiki-adrs` | ADR-lite decisions | `docs/wiki/decisions/**`, INDEX + wiki hub cross-links |
| `coord-compare-sample` | M9 compare proof sample | `docs/proof-samples/compare-projection.json` or hub deferral note |
| `coord-link-audit` | Integrative link audit | `docs/INDEX.md`, `docs/wiki/**`, `docs/CONTRIBUTING.md` — links only |

**Branch:** `feat/docs-wiki-wave2`

## Broker rules

- Coordinators return `DispatchManifest` only — no Task spawn.
- Parent spawns workers; disjoint `write_scope` enforced.
- Frontier and node status come from **`kos serve`** for `dag:nlfr-flagship`; Linear is not primary authority (`linear_authority: false`).
- Every new claim in docs carries truth-label vocabulary (`source_kind`, `confidence`, `evidence_refs`, `redaction_state`).
- Canvas and README must not imply live backend state absent from projection JSON.
- GHA offline: document local proof substitutes; do not block ship on CI green.
- Privacy: no secrets, credentials, raw private logs, or customer data in docs.

## Proof posture

```bash
bash -n scripts/*.sh                # when script examples cited
npm --prefix apps/canvas run test:truth   # only if canvas/projection docs touched
```

No `src/nlfr/**` writes in this DAG.
