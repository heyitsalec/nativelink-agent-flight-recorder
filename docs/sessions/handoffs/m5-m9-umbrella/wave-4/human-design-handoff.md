# Wave 4 — Human design handoff packet

**Date:** 2026-06-06  
**Umbrella:** M5–M9 broker orchestration  
**North star:** Reproducible backend + GUI substrate for AI agent runs before human design pass

## Milestone status

| Milestone | Status | Proof |
|-----------|--------|-------|
| M5 CI credibility | Landed | `.github/workflows/nlfr-proof.yml` (3 jobs) |
| M6 real default | Done | `canvas-dev` collectable_v1 + fixture banner |
| M7 worker parser | Landed | `worker_identity` from admin stdout; `worker-evidence-proof.sh` |
| M8 agent adapter | Landed | `record-agent-change.sh` + `adapters/cursor/README.md` |
| M9 compare | Landed | `nlfr compare export|index`, canvas compare lens, `compare-proof.sh` |

## Proof matrix (local, 2026-06-06)

| Command | Result |
|---------|--------|
| `uv run pytest -q` | 61 passed |
| `./scripts/record-proof.sh` | PASS |
| `./scripts/record-canvas-build.sh` | PASS |
| `./scripts/worker-evidence-proof.sh` | PASS (`worker_identity_observed: true`) |
| `./scripts/record-agent-change.sh --dry-run ...` | PASS |
| `./scripts/compare-proof.sh` | PASS |
| `npm --prefix apps/canvas run test:truth` | PASS (15/15 nodes) |

## File-based handoff system

Canonical tree documented in knowledge-os `broker-dispatch-manifest.md` and
`docs/sessions/handoffs/README.md`. Workers return paths; parent reads
`worker-results.json` + `integration-brief.md` between waves.

## Remaining honest blockers

1. **First green GHA run** — promote redacted CI summaries to `docs/proof-samples/`
2. **Compare projection in canvas** — optional `compare-projection.json` not committed by default; generate via `compare export`
3. **Real agent E2E** — M8 dry-run proven; full non-dry run left to operator
4. **M9 retention policy** — index only; no automatic purge yet

## Agent accounting

| Role | Count |
|------|-------|
| Parent broker | 1 |
| Wave 1.5 reviewers | 3 |
| Wave 2 workers (M7, M8) | 2 |
| Wave 3 worker (M9) | 1 |
| **Total subagents** | **6** |
| **Total agents (incl. parent)** | **7** |

## Recommended human design pass

1. Visual polish on compare lens and worker nodes in Action Graph
2. Run selector UX (read `nlfr compare index` data, no invented backend)
3. Typography / density pass on Proof Drawer and Remote Boundary lens
4. Screenshot baselines after design changes (`record-canvas-build.sh` + diff)

## Key entry points

- Adoption: `docs/ADOPTION_GUIDE.md`
- CI: `docs/CI_RECIPE.md`
- Wave briefs: `docs/sessions/handoffs/m5-m9-umbrella/wave-1.5/integration-brief.md`
