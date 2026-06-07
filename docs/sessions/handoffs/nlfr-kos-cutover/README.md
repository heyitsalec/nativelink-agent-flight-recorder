# NLFR KOS cutover — handoff index (`dag:nlfr-flagship`)

**Authority:** KOS local primary (`kos serve`, `linear_authority: false`)  
**DAG ref:** `dag:nlfr-flagship` · parent `NLFR-FLAGSHIP`  
**Manifest:** [`wave-9/cutover-manifest.json`](wave-9/cutover-manifest.json) (dag-gui DagPicker)  
**Gap honesty:** [`wave-9/gap-honesty-packet.md`](wave-9/gap-honesty-packet.md)

Operator GUI (Harmony DAG Ops) resolves KOS node clicks to these paths. Paths are relative to
the NLFR repo root unless noted.

---

## Wave summary

| Wave | `wave_id` | Handoff dir | Integration brief |
|------|-----------|-------------|-------------------|
| 0 | `four-wave-plan` | [`wave-0/`](wave-0/) | [`four-wave-plan.md`](wave-0/four-wave-plan.md) |
| 1 | `tier1-canvas-polish` | [`wave-1/`](wave-1/) | [`integration-brief.md`](wave-1/integration-brief.md) |
| 2 | `agent-provenance-live` | [`wave-2/`](wave-2/) | [`integration-brief.md`](wave-2/integration-brief.md) |
| 3 | `lre-linux-manual-proof` | [`wave-3/`](wave-3/) | [`integration-brief.md`](wave-3/integration-brief.md) |
| 4 | `ci-restore-verify` | [`wave-4/`](wave-4/) | [`integration-brief.md`](wave-4/integration-brief.md) |
| 5 | `live-proof-residual` | [`wave-5/`](wave-5/) | [`integration-brief.md`](wave-5/integration-brief.md) *(planned)* |
| 6 | `retention-policy-v1` | [`wave-6/`](wave-6/) | [`integration-brief.md`](wave-6/integration-brief.md) *(planned)* |
| 7 | `cache-only-ci-gate` | [`wave-7/`](wave-7/) | [`integration-brief.md`](wave-7/integration-brief.md) *(planned)* |
| 8 | `pr-proof-attachment` | [`wave-8/`](wave-8/) | [`integration-brief.md`](wave-8/integration-brief.md) *(planned)* |
| 9 | `kos-operator-bridge` | [`wave-9/`](wave-9/) | [`integration-brief.md`](wave-9/integration-brief.md) |
| 10 | `gha-sustained-green` | [`wave-10/`](wave-10/) | [`integration-brief.md`](wave-10/integration-brief.md) |
| 11 | `adoption-init-path` | [`wave-11/`](wave-11/) | [`integration-brief.md`](wave-11/integration-brief.md) |
| 12 | `multi-run-history-v1` | [`wave-12/`](wave-12/) | [`integration-brief.md`](wave-12/integration-brief.md) |
| 13 | `operator-console-ergonomics` | [`wave-13/`](wave-13/) | [`integration-brief.md`](wave-13/integration-brief.md) |
| 14 | `umbrella-1-13-close` | [`wave-14/`](wave-14/) | [`umbrella-close-packet.md`](wave-14/umbrella-close-packet.md) |

**DAG docs:** waves 1–4 → [`nlfr-kos-roadmap.md`](../../../dags/nlfr-kos-roadmap.md); waves 5–9 →
[`nlfr-kos-roadmap-waves-5-8.md`](../../../dags/nlfr-kos-roadmap-waves-5-8.md); waves 10–13 →
[`nlfr-kos-roadmap-waves-10-13.md`](../../../dags/nlfr-kos-roadmap-waves-10-13.md).

---

## KOS node id → handoff path

### Wave 1 — `tier1-canvas-polish`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W1-CANVAS-UX` | [`wave-1/integration-brief.md`](wave-1/integration-brief.md) | Canvas UX polish |
| `W1-RUN-SELECTOR` | [`wave-1/integration-brief.md`](wave-1/integration-brief.md) | Run-group selector |
| `W1-SCREENSHOTS` | [`wave-1/integration-brief.md`](wave-1/integration-brief.md) | Screenshot baselines |
| `W1-INTEGRATE` | [`wave-1/integration-brief.md`](wave-1/integration-brief.md) | [`worker-results.json`](wave-1/worker-results.json) |

### Wave 2 — `agent-provenance-live`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W2-AGENT-E2E` | [`wave-2/integration-brief.md`](wave-2/integration-brief.md) | `scripts/agent-live-proof.sh` |
| `W2-AGENT-PROOF` | [`wave-2/integration-brief.md`](wave-2/integration-brief.md) | Proof samples |
| `W2-ADAPTER-DOCS` | [`wave-2/integration-brief.md`](wave-2/integration-brief.md) | [`adapters/cursor/README.md`](../../../adapters/cursor/README.md) |
| `W2-INTEGRATE` | [`wave-2/integration-brief.md`](wave-2/integration-brief.md) | [`worker-results.json`](wave-2/worker-results.json) |

### Wave 3 — `lre-linux-manual-proof`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W3-LINUX-RUNBOOK` | [`wave-3/integration-brief.md`](wave-3/integration-brief.md) | [`docs/LRE_LINUX_PROOF.md`](../../../LRE_LINUX_PROOF.md) |
| `W3-SAMPLE-PROMOTE` | [`wave-3/integration-brief.md`](wave-3/integration-brief.md) | Linux manual sample |
| `W3-LADDER-SYNC` | [`wave-3/integration-brief.md`](wave-3/integration-brief.md) | Ladder sync |
| `W3-INTEGRATE` | [`wave-3/integration-brief.md`](wave-3/integration-brief.md) | [`worker-results.json`](wave-3/worker-results.json) |

### Wave 4 — `ci-restore-verify`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W4-GHA-RESTORE` | [`wave-4/integration-brief.md`](wave-4/integration-brief.md) | [`docs/GHA_RESTORE_RUNBOOK.md`](../../../GHA_RESTORE_RUNBOOK.md) |
| `W4-PROOF-PROMOTE` | [`wave-4/integration-brief.md`](wave-4/integration-brief.md) | CI promotion matrix |
| `W4-CI-DOCS` | [`wave-4/integration-brief.md`](wave-4/integration-brief.md) | CI recipe sync |
| `W4-INTEGRATE` | [`wave-4/integration-brief.md`](wave-4/integration-brief.md) | [`worker-results.json`](wave-4/worker-results.json) |

### Wave 5 — `live-proof-residual`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W5-M8-LIVE` | [`wave-5/integration-brief.md`](wave-5/integration-brief.md) | M8 live Cursor — **operator-host gated** |
| `W5-LRE-LINUX` | [`wave-5/integration-brief.md`](wave-5/integration-brief.md) | LRE Linux — **operator-host gated** |
| `W5-LIVE-DOCS` | [`wave-5/integration-brief.md`](wave-5/integration-brief.md) | M8/LRE runbooks |
| `W5-INTEGRATE` | [`wave-5/integration-brief.md`](wave-5/integration-brief.md) | Wave 5 close |

### Wave 6 — `retention-policy-v1`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W6-RETENTION-POLICY` | [`wave-6/integration-brief.md`](wave-6/integration-brief.md) | Policy module |
| `W6-RETENTION-CLI` | [`wave-6/integration-brief.md`](wave-6/integration-brief.md) | `compare index --limit` |
| `W6-RETENTION-WIKI` | [`wave-6/integration-brief.md`](wave-6/integration-brief.md) | Wiki retention docs |
| `W6-INTEGRATE` | [`wave-6/integration-brief.md`](wave-6/integration-brief.md) | Wave 6 close |

### Wave 7 — `cache-only-ci-gate`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W7-CACHE-GATE-SCRIPT` | [`wave-7/integration-brief.md`](wave-7/integration-brief.md) | `cache-only-ci-gate.sh` |
| `W7-CACHE-GATE-WF` | [`wave-7/integration-brief.md`](wave-7/integration-brief.md) | GHA job — **offline until restore** |
| `W7-CACHE-GATE-DOCS` | [`wave-7/integration-brief.md`](wave-7/integration-brief.md) | CI recipe |
| `W7-INTEGRATE` | [`wave-7/integration-brief.md`](wave-7/integration-brief.md) | Wave 7 close |

### Wave 8 — `pr-proof-attachment`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W8-PR-EXPORTER` | [`wave-8/integration-brief.md`](wave-8/integration-brief.md) | Markdown exporter |
| `W8-PR-SAMPLE` | [`wave-8/integration-brief.md`](wave-8/integration-brief.md) | PR comment sample |
| `W8-PR-RECIPE` | [`wave-8/integration-brief.md`](wave-8/integration-brief.md) | Wiki how-to |
| `W8-INTEGRATE` | [`wave-8/integration-brief.md`](wave-8/integration-brief.md) | Wave 8 close |

### Wave 9 — `kos-operator-bridge`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W9-CUTOVER-MANIFEST` | [`wave-9/cutover-manifest.json`](wave-9/cutover-manifest.json) | dag-gui DagPicker |
| `W9-HANDOFF-BRIDGE` | This file | Node → path index |
| `W9-GAP-HONESTY` | [`wave-9/gap-honesty-packet.md`](wave-9/gap-honesty-packet.md) | Residual gaps |
| `W9-INTEGRATE` | [`wave-9/integration-brief.md`](wave-9/integration-brief.md) | Umbrella 1–9 close |

### Wave 10 — `gha-sustained-green`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W10-GHA-RESTORE` | [`wave-10/integration-brief.md`](wave-10/integration-brief.md) | `verify-gha-readiness.sh` |
| `W10-CI-PROMOTE` | [`wave-10/integration-brief.md`](wave-10/integration-brief.md) | **BLOCKED** — GHA offline |
| `W10-CI-DOCS` | [`wave-10/integration-brief.md`](wave-10/integration-brief.md) | GHA restore runbook sync |
| `W10-INTEGRATE` | [`wave-10/integration-brief.md`](wave-10/integration-brief.md) | [`worker-results.json`](wave-10/worker-results.json) |

### Wave 11 — `adoption-init-path`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W11-NLFR-INIT` | [`wave-11/integration-brief.md`](wave-11/integration-brief.md) | `nlfr init` scaffold |
| `W11-ADAPTER-PATTERN` | [`wave-11/integration-brief.md`](wave-11/integration-brief.md) | Monorepo adapter wiki |
| `W11-ONE-COMMAND` | [`wave-11/integration-brief.md`](wave-11/integration-brief.md) | `record-this-target.sh` |
| `W11-INTEGRATE` | [`wave-11/integration-brief.md`](wave-11/integration-brief.md) | [`worker-results.json`](wave-11/worker-results.json) |

### Wave 12 — `multi-run-history-v1`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W12-HISTORY-INDEX` | [`wave-12/integration-brief.md`](wave-12/integration-brief.md) | `compare index --limit` |
| `W12-HISTORY-PROJECTION` | [`wave-12/integration-brief.md`](wave-12/integration-brief.md) | `compare history` exporter |
| `W12-HISTORY-WIKI` | [`wave-12/integration-brief.md`](wave-12/integration-brief.md) | Browse-run-history wiki |
| `W12-INTEGRATE` | [`wave-12/integration-brief.md`](wave-12/integration-brief.md) | [`worker-results.json`](wave-12/worker-results.json) |

### Wave 13 — `operator-console-ergonomics`

| Node | Primary handoff | Notes |
|------|-----------------|-------|
| `W13-CANVAS-8NODE-CAP` | [`wave-13/integration-brief.md`](wave-13/integration-brief.md) | 8-node default cap |
| `W13-LENS-ERGONOMICS` | [`wave-13/integration-brief.md`](wave-13/integration-brief.md) | Compare/table lens polish |
| `W13-FAILURE-MESSAGES` | [`wave-13/integration-brief.md`](wave-13/integration-brief.md) | Doctor + init hints |
| `W13-INTEGRATE` | [`wave-13/integration-brief.md`](wave-13/integration-brief.md) | [`worker-results.json`](wave-13/worker-results.json) |

---

## Cross-repo coupling

| Consumer | Artifact | Purpose |
|----------|----------|---------|
| dag-gui-v2 W5 (`W5-W4`) | `wave-9/cutover-manifest.json` | DagPicker + NodeInspector handoff correlation |
| knowledge-os seed | `tools/kos_mcp/fixtures/nlfr-flagship-waves-5-8.json` | KOS frontier parity |
| Harmony DAG Ops | `KOS_SERVE_URL=http://127.0.0.1:7423` | Live frontier reads |

---

## Residual gaps (honest)

See [`wave-9/gap-honesty-packet.md`](wave-9/gap-honesty-packet.md) for truth-labeled status on:

- **GHA offline** — full `nlfr-proof.yml` not exercised
- **Fleet parsers blocked** — no new collectable worker/scheduler parsers
- **M8/LRE live on operator host** — non-dry-run Cursor and x86_64-linux LRE remain host-gated
