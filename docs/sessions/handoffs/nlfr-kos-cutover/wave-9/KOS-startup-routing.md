# Knowledge OS startup routing — NLFR KOS cutover wave 9

**Mandatory read** for dag-gui coupling and `kos-operator-bridge` workers.

## Control plane (local-primary)

| Field | Value |
|-------|-------|
| **Serve URL** | `http://127.0.0.1:7423` — start with `python3 -m tools.kos_mcp.serve` from knowledge-os |
| **`dag_ref`** | `dag:nlfr-flagship` |
| **`linear_authority`** | `false` |
| **Linear mirror** | **disabled** — PER-* tickets are reference only |
| **Frontier reads** | `GET /v1/dags`, `GET /v1/dag/dag%3Anlfr-flagship/frontier`, `GET /v1/cutover` |
| **Node status** | `apply_status_batch` via kos-mcp after worker close |

Verify before dag-gui NLFR coupling:

```bash
curl -sS http://127.0.0.1:7423/health
curl -sS http://127.0.0.1:7423/v1/cutover
curl -sS 'http://127.0.0.1:7423/v1/dags' | head -c 2000
curl -sS 'http://127.0.0.1:7423/v1/dag/dag%3Anlfr-flagship/frontier'
```

Harmony / operator GUI: `export KOS_SERVE_URL=http://127.0.0.1:7423`

## NLFR cutover manifest (dag-gui)

| Field | Path |
|-------|------|
| **Manifest** | [`cutover-manifest.json`](cutover-manifest.json) |
| **Schema** | `nlfr.cutover_manifest.v1` |
| **Handoff root** | `docs/sessions/handoffs/nlfr-kos-cutover` |
| **Node index** | [`../README.md`](../README.md) |
| **Gap honesty** | [`gap-honesty-packet.md`](gap-honesty-packet.md) |

dag-gui-v2 W5 (`W5-W4`) consumes the manifest for DagPicker and NodeInspector handoff
correlation. NLFR does not ship Harmony code.

Validate manifest JSON:

```bash
python3 -m json.tool docs/sessions/handoffs/nlfr-kos-cutover/wave-9/cutover-manifest.json
```

## Startup read order

| Order | Doc |
|-------|-----|
| 1 | `AGENTS.md` |
| 2 | [`knowledge-os/projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) — § Orchestration |
| 3 | [`docs/dags/nlfr-kos-roadmap.md`](../../../dags/nlfr-kos-roadmap.md) — waves 1–4 |
| 4 | [`docs/dags/nlfr-kos-roadmap-waves-5-8.md`](../../../dags/nlfr-kos-roadmap-waves-5-8.md) — waves 5–9 |
| 5 | [`../README.md`](../README.md) — node → handoff index |
| 6 | [`gap-honesty-packet.md`](gap-honesty-packet.md) — residual gaps |
| 7 | [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) |
| 8 | [dag-gui wave-plan-2-5](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/dag-gui-research/wave-plan-2-5.md) — W5 broker-native loop |

## Active sub-DAGs (wave 9)

| Coordinator | KOS node | write_scope |
|-------------|----------|-------------|
| `coord-kos-cutover-manifest` | `W9-CUTOVER-MANIFEST` | `wave-9/cutover-manifest.json`, this file |
| `coord-kos-handoff-bridge` | `W9-HANDOFF-BRIDGE` | `../README.md` |
| `coord-kos-gap-honesty` | `W9-GAP-HONESTY` | `gap-honesty-packet.md` |
| `coord-kos-umbrella-integrate` | `W9-INTEGRATE` | `integration-brief.md`, roadmap forward links |

**Branch:** `feat/docs-wiki-wave2` (bridge lands on docs-wiki-wave2 umbrella)

## Broker rules

- Coordinators return `DispatchManifest` only — no Task spawn.
- Parent is sole spawn authority; disjoint `write_scope` enforced.
- Frontier and node closure from **`kos serve`** for `dag:nlfr-flagship`; Linear is not primary.
- **GHA offline:** local proof gates at close; do not block bridge ship on CI green.
- **Fleet parsers blocked:** honesty packet only — no new collectable parser workers.
- **M8/LRE live:** operator-host gated; blocker samples are honest `collectable_v1`.
- Privacy: no secrets, credentials, raw private logs, or customer data in artifacts or docs.

## Proof posture

```bash
python3 -m json.tool docs/sessions/handoffs/nlfr-kos-cutover/wave-9/cutover-manifest.json
uv run pytest -q
```

## KOS node prerequisites

| Node | Runnable when |
|------|---------------|
| `W9-CUTOVER-MANIFEST` | `W8-INTEGRATE` closed or bridge-only ARM waived |
| `W9-HANDOFF-BRIDGE` | `W8-INTEGRATE` closed or bridge-only ARM waived |
| `W9-GAP-HONESTY` | `W8-INTEGRATE` closed or bridge-only ARM waived |
| `W9-INTEGRATE` | all W9 implementers closed |
