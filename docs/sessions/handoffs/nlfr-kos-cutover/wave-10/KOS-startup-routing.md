# Knowledge OS startup routing — NLFR KOS cutover waves 10–13

**Mandatory read** for `gha-sustained-green` and forward waves 11–13 coordinators.

## Control plane (local-primary)

| Field | Value |
|-------|-------|
| **Serve URL** | `http://127.0.0.1:7423` — start with `python3 -m tools.kos_mcp.serve` from knowledge-os |
| **`dag_ref`** | `dag:nlfr-flagship` |
| **`linear_authority`** | `false` |
| **Linear mirror** | **disabled** — PER-* tickets are reference only |
| **Frontier reads** | `GET /v1/dags`, `GET /v1/dag/dag%3Anlfr-flagship/frontier`, `GET /v1/cutover` |
| **Node status** | `apply_status_batch` via kos-mcp after worker close |

Verify before wave-10 coordinator spawn:

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
| **Manifest** | [`../wave-9/cutover-manifest.json`](../wave-9/cutover-manifest.json) |
| **Schema** | `nlfr.cutover_manifest.v1` |
| **Handoff root** | `docs/sessions/handoffs/nlfr-kos-cutover` |
| **Node index** | [`../README.md`](../README.md) |
| **Gap honesty** | [`../wave-9/gap-honesty-packet.md`](../wave-9/gap-honesty-packet.md) |

## Startup read order

| Order | Doc |
|-------|-----|
| 1 | `AGENTS.md` |
| 2 | [`knowledge-os/projects/nlfr/pack.md`](/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md) — § Orchestration |
| 3 | [`docs/dags/nlfr-kos-roadmap-waves-5-8.md`](../../../../dags/nlfr-kos-roadmap-waves-5-8.md) — waves 5–9 |
| 4 | [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) — waves 10–13 |
| 5 | [`../README.md`](../README.md) — node → handoff index |
| 6 | [`../wave-9/gap-honesty-packet.md`](../wave-9/gap-honesty-packet.md) — GHA residual |
| 7 | [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) |
| 8 | [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md) |

## Active sub-DAGs (wave 10)

| Coordinator | KOS node | write_scope |
|-------------|----------|-------------|
| `coord-gha-restore` | `W10-GHA-RESTORE` | `.github/workflows/nlfr-proof.yml`, `.github/workflows/nlfr-cache-only-gate.yml` |
| `coord-ci-docs` | `W10-CI-DOCS` | `docs/GHA_RESTORE_RUNBOOK.md`, `docs/CI_RECIPE.md` |
| `coord-ci-promote` | `W10-CI-PROMOTE` | `docs/proof-samples/CI_PROMOTION_MATRIX.md`, gap-honesty sync |
| `coord-w10-integrate` | `W10-INTEGRATE` | `wave-10/integration-brief.md`, KOS close |

**Disjoint scopes:** docs coordinator must not edit workflow YAML; restore coordinator must not
edit runbooks until integrate coordinates gap-honesty sync.

**Branch:** `feat/docs-wiki-wave2`

## Forward waves (seeded, not dispatched)

| Wave | Runnable after | Key nodes |
|------|--------------|-----------|
| 11 `adoption-init-path` | `W10-INTEGRATE` | `W11-NLFR-INIT`, `W11-ADAPTER-PATTERN`, `W11-ONE-COMMAND` |
| 12 `multi-run-history-v1` | `W11-INTEGRATE` | `W12-HISTORY-INDEX`, `W12-HISTORY-PROJECTION`, `W12-HISTORY-WIKI` |
| 13 `operator-console-ergonomics` | `W12-INTEGRATE` (+ `W11-INTEGRATE` for failure messages) | `W13-CANVAS-8NODE-CAP`, `W13-LENS-ERGONOMICS`, `W13-FAILURE-MESSAGES` |

## Broker rules

- Coordinators return `DispatchManifest` only — no Task spawn.
- Parent is sole spawn authority; disjoint `write_scope` enforced.
- Frontier and node closure from **`kos serve`** for `dag:nlfr-flagship`; Linear is not primary.
- **GHA offline:** local proof gates at close; honest blocker is valid ship path.
- **Fleet parsers blocked:** no new collectable parser workers in waves 10–13.
- **M8/LRE live:** operator-host gated; do not block wave 10 on live proof.
- Privacy: no secrets, credentials, raw private logs, or customer data in artifacts or docs.

## Proof posture

```bash
gh workflow run nlfr-proof.yml
gh workflow run nlfr-cache-only-gate.yml
uv run pytest -q
./scripts/cache-only-ci-gate.sh
```

## KOS node prerequisites

| Node | Runnable when |
|------|---------------|
| `W10-GHA-RESTORE` | `W9-INTEGRATE` done |
| `W10-CI-DOCS` | `W9-INTEGRATE` done |
| `W10-CI-PROMOTE` | `W10-GHA-RESTORE` done or honest blocker documented |
| `W10-INTEGRATE` | all W10 implementers closed |

Seed: `tools/orchestrator/scripts/seed_nlfr_flagship_waves_10_13.py` (Knowledge OS repo).
