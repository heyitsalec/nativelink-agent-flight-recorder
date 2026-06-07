# Wave 1.5 E2E Verifier Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Agent:** Wave 1.5 E2E verifier

## Proof matrix

| # | Command | Exit | Result | Key artifacts |
|---|---------|------|--------|---------------|
| 1 | `uv run pytest -q` | 0 | PASS | (no persistent artifact; 50 passed in ~1.55s) |
| 2 | `./scripts/record-proof.sh` | 0 | PASS | `data/record-proof/summary.json`, run `run_0db0fac6cb2a478ead5fcd0b`, artifacts under `data/record-proof/runs/run_0db0fac6cb2a478ead5fcd0b/artifacts/` |
| 3 | `./scripts/record-canvas-build.sh` | 0 | PASS | `data/canvas-dev/summary.json`, run `run_79565ee53498a70158fcb2a6`, `apps/canvas/public/projections/`, `apps/canvas/dist/` |
| 4 | `npm ci --prefix apps/canvas && npm --prefix apps/canvas run build && npm --prefix apps/canvas run test:truth` | 0 | PASS | `apps/canvas/dist/`, truth-guard ok (15/15 nodes) |
| 5 | `./scripts/verify-demo.sh` | 0 | PASS (with recorded blockers) | `data/demo-proof/nlfr.sqlite`, `data/demo-proof/projections/`, `apps/canvas/public/projections/action-graph.json` |

## Optional: nix + cold/warm cache proof

| Command | Exit | Result | Key artifacts |
|---------|------|--------|---------------|
| `nix develop -c echo ok` (smoke) | 0 | Available (~12s cold shell) | Nix dev shell provides `bazel`, `nativelink` |
| `nix develop -c ./scripts/cold-warm-cache-proof.sh` | 0 | PASS | `data/cold-warm-proof/summary.json`, cold run `run_2d25d594aed1907051013b9d`, warm run `run_d2d68ccc62df16b6fb13c837`, cache economics warm hit_rate 1.0 vs cold 0.0 |

**Note:** `verify-demo.sh` runs outside `nix develop`. It records environment blockers where host PATH lacks Bazel/NativeLink:

- `data/demo-proof/doctor.json` — `ok: false` (missing bazel/nativelink on PATH)
- `data/demo-proof/cold-warm.log` → `data/demo-proof/cold-warm/environment-blocker.json`
- Similar blocker logs: `tool-check-run.json`, `local-exec.log`, `agent-loop.log`

Fixture-backed and projection export legs inside verify-demo still completed; script exit code 0.

## Summary

- Full matrix commands: all exit 0.
- Host cache-only doctor / in-demo cold-warm: blocked without nix PATH; superseded by successful `cold-warm-cache-proof.sh` under `nix develop`.
