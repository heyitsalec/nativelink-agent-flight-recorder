# NLFR KOS cutover — wave 10 broker ARM (`gha-sustained-green`)

**Date:** 2026-06-07  
**Branch:** `feat/docs-wiki-wave2`  
**Worker:** `wave10-arm-handoffs`  
**Status:** ARMED

## Operator intent

ARM **waves 10–13** of the NLFR flagship KOS cutover on local KOS primary authority.
Wave 10 closes the **GHA offline** residual from waves 4, 7, and 9; waves 11–13 are
**planned stubs** — seed + ARM docs only until wave 10 integrates.

Authority is **local KOS primary** (`kos serve`, `dag:nlfr-flagship`, `linear_authority: false`).

## Prerequisite (waves 1–9)

| Artifact | Status |
|----------|--------|
| [`docs/dags/nlfr-kos-roadmap-waves-5-8.md`](../../../../dags/nlfr-kos-roadmap-waves-5-8.md) | SHIPPED (waves 5–9) |
| [`wave-9/integration-brief.md`](../wave-9/integration-brief.md) | SHIPPED — `W9-INTEGRATE` closed |
| [`wave-9/gap-honesty-packet.md`](../wave-9/gap-honesty-packet.md) | OPEN — GHA offline P0 |

Confirm `kos serve http://127.0.0.1:7423` healthy and `W9-INTEGRATE` `done` before coordinator
spawn (see [`KOS-startup-routing.md`](KOS-startup-routing.md)).

## Parent actions (ARM only)

- Canonical DAG: [`docs/dags/nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md)
- Created KOS routing: [`KOS-startup-routing.md`](KOS-startup-routing.md)
- Initialized spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Re-armed broker mode — **no implementer spawn in this ARM worker**

## Wave-10 dispatch (next)

Parent spawns coordinators on `feat/docs-wiki-wave2` with disjoint `write_scope`:

| # | coordinator_id | Sub-DAG | Notes |
|---|----------------|---------|-------|
| 1 | `coord-gha-restore` | Workflow fixes + sustained green | Owns `.github/workflows/*` only |
| 2 | `coord-ci-docs` | `GHA_RESTORE_RUNBOOK` + `CI_RECIPE` sync | Parallel with 1; no workflow YAML |
| 3 | `coord-ci-promote` | Promotion matrix execution | **After** restore or honest blocker |
| 4 | `coord-w10-integrate` | Integration brief + KOS close | Last |

KOS nodes: `W10-GHA-RESTORE` · `W10-CI-DOCS` · `W10-CI-PROMOTE` · `W10-INTEGRATE`

Seed script (operator-owned, Knowledge OS repo):

```bash
python3 tools/orchestrator/scripts/seed_nlfr_flagship_waves_10_13.py
```

## Waves 11–13 (stub — dispatch after W10 close)

| Wave | id | Integrate node | Handoff dir |
|------|----|----------------|-------------|
| 11 | `adoption-init-path` | `W11-INTEGRATE` | `wave-11/` *(planned)* |
| 12 | `multi-run-history-v1` | `W12-INTEGRATE` | `wave-12/` *(planned)* |
| 13 | `operator-console-ergonomics` | `W13-INTEGRATE` | `wave-13/` *(planned)* |

Nodes are seeded on KOS for frontier visibility; implementer spawn deferred per wave.

## Proof gates (parent at wave-10 close)

```bash
gh workflow run nlfr-proof.yml
gh workflow run nlfr-cache-only-gate.yml
uv run pytest -q
./scripts/cache-only-ci-gate.sh
```

GHA offline: local gates substitute per
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).

## Ceiling / stop conditions

| Claim | Label | Gate |
|-------|-------|------|
| Sustained GHA green | `collectable_v1` / `high` | ≥3 consecutive green runs |
| GHA still offline | `collectable_v1` / `high` (negative) | Updated blocker + local gates PASS |
| Bazel on all CI legs | **environment** | Doctor records blocker per leg |

**Stop wave** if workflow changes require fleet parsers or secrets in repo artifacts.

## Inherited residual (wave 9)

GHA offline (`C-W9-1`) is the primary wave-10 driver. Fleet parsers remain **blocked**;
M8/LRE live paths stay operator-host gated — do not conflate with CI restore.
