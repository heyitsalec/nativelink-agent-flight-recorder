# Knowledge OS startup routing — Frontier wave

**Mandatory read** for every coordinator and worker.

| Order | Doc |
|-------|-----|
| 1 | `AGENTS.md` |
| 2 | `/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md` |
| 3 | `docs/ARCHITECTURE_TRACK.md` Phase 3 ladder |
| 4 | `broker-dispatch-manifest.md` |

## Active sub-DAGs (wave-1)

| Coordinator | DAG | Priority |
|-------------|-----|----------|
| `coord-tier1-live-bazel` | tier1-live-bazel | 1 — design-session narrative |
| `coord-fleet-evidence-v1` | fleet-evidence-v1 | 2 — stdout ingest breadth |
| `coord-lre-cache-parity` | lre-cache-parity | 3 — Linux-CI-gated research first |

**Branch:** `main` (post PR #7 merge) or feature branch from main.

## Broker rules

- Coordinators return `DispatchManifest` only — no Task spawn.
- Parent spawns workers; disjoint `write_scope`.
- LRE cache parity: research before implement; honest blocker if worker image alignment missing.
- Fleet: Remote Boundary lens only — no fleet dashboard UI.
- Truth labels on every new claim.
