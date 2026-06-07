# Provenance / ticket drift — M5–M9 umbrella (Wave 2.5)

**Audit date:** 2026-06-06  
**Scope:** PER-1065–PER-1069 as documented in repo DAG mirrors ([`docs/dags/m5-m9-umbrella.md`](../../../dags/m5-m9-umbrella.md)); Linear not queried live  
**Baseline:** Wave 1.5 ticket drift (pre–Wave 2)

## Matrix

| Milestone | Linear | Claimed (DAG README) | Actual (repo) | Gap |
|-----------|--------|----------------------|---------------|-----|
| M5 | PER-1065 | Linux CI + adoption docs + proof samples | `.github/workflows/nlfr-proof.yml` (3 jobs), `ADOPTION_GUIDE.md`, `CI_RECIPE.md`; proof-samples from author Nix | **medium** — CI promotion checklist item still open |
| M6 | PER-1066 | Real default projection + banner | `canvas-dev` `collectable_v1` in committed projections; fixture banner in `App.tsx` | **low** — polish only |
| M7 | PER-1067 | One worker stdout parser + promoted claim | `worker_admin_stdout.py`, graph/proof promotion, `worker-evidence-proof.sh`, fixture + optional live path | **low** — default proof is fixture-replay |
| M8 | PER-1068 | Real agent adapter | `record-agent-change.sh`, `adapters/cursor/README.md`, `--provenance-sidecar`; dry-run + pytest proven | **medium** — no live Cursor→Bazel E2E in proof artifacts |
| M9 | PER-1069 | compare + retention + canvas lens | Landed in Wave 3 (post–2.5 gate); see wave-3 provenance | **n/a at 2.5 gate** — was Wave 3 scope at 1.5; now done |

## Requirement gaps by ticket

### PER-1065 (M5)

| Requirement | Status |
|-------------|--------|
| `nlfr-proof.yml` on Linux/x86_64 | Present — unit, Nix toolchain, verify-demo-fixture jobs |
| Redacted CI summaries → `docs/proof-samples/` | **Open** — samples exist but sourced from author Nix runs |
| Skeptic adoption path | `ADOPTION_GUIDE.md`, `CI_RECIPE.md` present |
| Handoff checklist “CI promotion” | Unchecked in [`m5-ci-proof.md`](../../../dags/m5-ci-proof.md) |

**CI verification:** **DEFERRED** — GHA offline in this review environment; cannot confirm first green run or artifact promotion.

### PER-1066 (M6)

| Requirement | Status |
|-------------|--------|
| Evaluator sees `collectable_v1` first | Met — `record-canvas-build.sh` + `verify-demo.sh` refresh committed projections |
| Docs distinguish real vs simulated | Met in WALKTHROUGH / ADOPTION_GUIDE |
| Non-blocking rule | Honored — did not gate M7/M8 |

### PER-1067 (M7)

| Requirement | Status |
|-------------|--------|
| Parser under `src/nlfr/ingest/` | `worker_admin_stdout.py` |
| Projector nodes only with SQLite rows | `graph.py`, `remote_execution.py`, `proof.py` |
| `worker-evidence-proof.sh` + `summary.json` | PASS locally — `worker_identity_observed: true`, `worker_nodes: 2` |
| Other four UNSUPPORTED claims explicit | `action_placement`, `queue_time`, `scheduler_assignment`, `load_distribution` remain |
| Fixture tests | `tests/fixtures/worker-admin/`, `tests/test_worker_admin_stdout.py` |

### PER-1068 (M8)

| Requirement | Status |
|-------------|--------|
| Thin adapter + privacy contract | `record-agent-change.sh` — `model` + `prompt_sha256` only |
| Wire to generic run / ingest | `--provenance-sidecar` in `generic_run.py` |
| One real change recorded E2E | **Partial** — dry-run and pytest validation leg; not full Bazel/NativeLink via live agent |
| `summary.json` | Dry-run emits JSON; `data/agent-change-proof/` from tests |

### PER-1069 (M9) — forward reference for 2.5 gate

At Wave 2.5 review time this ticket was **Wave 3 blocked**. Repo now includes compare CLI, projector, canvas lens, and `compare-proof.sh` (see wave-3 provenance). Drift vs ticket at 2.5 boundary: **none** — implementation matches DAG spec when measured today.

## Wave 1.5 → 2.5 delta

| Item | Wave 1.5 | Wave 2.5 |
|------|----------|----------|
| M7 | Not started | Landed |
| M8 | Not started | Landed (dry-run proven) |
| M9 | CLI shell only (claimed) | Full compare stack (Wave 3) |
| CI canvas dogfood in unit job | Flagged missing | Present in workflow (lines 46–51) |
| Committed projection `source_kind` | Mixed concern | `collectable_v1` |

## Wave 3 unblock (per review-gates.md)

1. This file + sibling provenance artifacts in `wave-2.5/`
2. `integration-brief.md` — M9 compare + retention + canvas lens contract
3. `worker-results.json` aggregate

No code blockers from ticket drift for M9 start. Remaining gaps are documentation honesty (ONE_PAGER worker identity) and CI promotion (DEFERRED).
