# Task packet — tier1-tests-handoffs

**Worker:** `tier1-tests-handoffs`  
**Coordinator:** `coord-tier1-live-bazel`  
**Wave:** 1

## Objective

Add fixture-backed tests for `tier1-live-bazel-proof.sh` and close wave-1 broker handoffs (DAG mirror, README, DEMO_SCRIPT).

## Write scope

- `tests/test_tier1_live_bazel.py`
- `docs/sessions/handoffs/tier1-live-bazel/wave-1/**`
- `docs/dags/tier1-live-bazel.md`
- `docs/dags/README.md` (entry only)
- `docs/DEMO_SCRIPT.md` (tier1 section only)

## Acceptance

1. Blocker smoke passes without Bazel on PATH.
2. Live test gated on `NLFR_RUN_TIER1_LIVE_BAZEL=1`.
3. `uv run pytest tests/test_tier1_live_bazel.py -q` green (blocker path).
4. Handoffs + DAG mirror land on disk.

## Return

Chat JSON envelope only (see KOS-startup-routing §3).
