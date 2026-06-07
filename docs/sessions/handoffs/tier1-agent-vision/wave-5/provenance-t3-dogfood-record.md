# Wave 5 T3 dogfood record — Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/broker-wave5-and-polish`  
**When:** 2026-06-06  
**Worker:** wave-5 dogfood evidence (command execution)

## Proof matrix

| # | Command | Exit | Result |
|---|---------|------|--------|
| 1 | `./scripts/record-canvas-build.sh` | 0 | PASS — canvas-dev generic run recorded |
| 2 | `NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --act 3` | 0 | PASS — agent-change live + embedded compare triple |
| 3 | `./scripts/compare-agent-runs.sh` | 0 | PASS — compare projection refreshed |
| 4 | `uv run pytest -q` (tail -3) | 0 | PASS — `81 passed in 6.52s` |

## Commands (verbatim)

```bash
cd /Users/alecbot/Documents/nativelink-agent-flight-recorder
./scripts/record-canvas-build.sh
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --act 3
./scripts/compare-agent-runs.sh
uv run pytest -q 2>&1 | tail -3
```

## Paths created / updated

| Path | Purpose |
|------|---------|
| `data/canvas-dev/summary.json` | Latest canvas-dev run group summary |
| `data/canvas-dev/runs/run_5c9b5472e287aa101be5fb2f/` | Canvas build chain generic run (npm build + pytest generic_run) |
| `data/canvas-dev/runs/run_5c9b5472e287aa101be5fb2f/artifacts/run.json` | Run metadata |
| `data/canvas-dev/runs/run_5c9b5472e287aa101be5fb2f/artifacts/artifact_manifest.json` | SHA-256 artifact manifest |
| `apps/canvas/public/projections/action-graph.json` | Redacted default action-graph projection |
| `apps/canvas/public/projections/proof.json` | Redacted default proof projection |
| `apps/canvas/public/projections/runway.json` | Redacted default runway projection |
| `apps/canvas/dist/` | Production canvas build (vite) |
| `data/agent-change/summary.json` | Act 3 agent-change run group summary |
| `data/agent-change/runs/run_f31c4c555a88b76ba46ab15d/` | Live agent-change record (`adapters/cursor/README.md`) |
| `data/agent-change/runs/run_f31c4c555a88b76ba46ab15d/artifacts/agent-provenance.json` | Agent provenance collectable |
| `data/compare-agent-runs/summary.json` | Multi-run compare index |
| `data/compare-agent-runs/projections/compare-record-proof-vs-canvas-dev.json` | Pairwise compare |
| `data/compare-agent-runs/projections/compare-canvas-dev-vs-agent-bugfix-1.json` | Pairwise compare |
| `data/compare-agent-runs/projections/compare-record-proof-vs-agent-bugfix-1.json` | Pairwise compare |

## Run IDs

- **canvas-dev:** `run_5c9b5472e287aa101be5fb2f` (`source_kind`: `collectable_v1`, `redaction_state`: `safe`)
- **agent-change (act 3):** `run_f31c4c555a88b76ba46ab15d` (`source_kind`: `collectable_v1`, agent model `composer-2.5`)

## Notes

- Bazel not exercised: act 3 used `NLFR_SKIP_BAZEL=1` (validation via generic/pytest path).
- `compare-agent-runs.sh` compares `record-proof`, `canvas-dev`, and `agent-bugfix-1` (not `agent-change` from act 3); act 3 also ran an embedded compare with the same three groups.
- All `data/*` run trees are gitignored; this provenance doc is the committed handoff record.

## Status

`DONE` — host allowed full dogfood chain; all commands exit 0.
