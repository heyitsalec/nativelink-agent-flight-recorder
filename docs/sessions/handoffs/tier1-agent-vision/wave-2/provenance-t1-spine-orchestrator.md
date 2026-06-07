# T1-SPINE Orchestrator — Provenance

**Worker:** `t1-spine-orchestrator`  
**Coordinator:** `coord-t1-spine`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Delivered Tier 1 orchestration packaging per wave 1.5 integration brief: three `nlfr.tier1.scenario.v1` recipes under `demo/scenarios/tier1/`, hashed prompt fixtures, operator README, and `scripts/tier1-agent-demo.sh` with `--dry-run`, `--act`, and `--json`. Dry-run validates scenarios, executes adapter `--dry-run` subprocesses for all change paths, and plans the Act 3 compare triple via `compare-agent-runs.sh --dry-run --json` without SQLite writes.

---

## Inputs read

| Artifact | Path |
|----------|------|
| Integration brief | `docs/sessions/handoffs/tier1-agent-vision/wave-1.5/integration-brief-t1-spine.md` |
| Adapter audit | `docs/sessions/handoffs/tier1-agent-vision/wave-1/provenance-t1-spine-audit-adapter-scenario.md` |
| M8 adapter | `scripts/record-agent-change.sh` |
| Simulate reference | `demo/scenarios/llm-bounded-patch.json`, `demo/scenarios/shared-module-change.json` |
| Compare rollup | `scripts/compare-agent-runs.sh` (landed by sibling worker; orchestrator calls it) |

---

## Deliverables written

| File | Description |
|------|-------------|
| `scripts/tier1-agent-demo.sh` | Three-act orchestrator; dry-run + live; env passthrough |
| `demo/scenarios/tier1/agent-bugfix-1.json` | Act 1 — `agent-bugfix-1` run group |
| `demo/scenarios/tier1/agent-feature-compare.json` | Act 2 — dual `change_paths` |
| `demo/scenarios/tier1/agent-change-meta.json` | Act 3 — meta dogfood + compare hook |
| `demo/scenarios/tier1/README.md` | Kind vocabulary + operator pre-edit contract |
| `demo/scenarios/tier1/fixtures/prompt-*.txt` | Three one-line stubs with precomputed SHA-256 |
| This file | Worker provenance |

---

## Scenario contract

- `schema_version`: `nlfr.tier1.scenario.v1`
- `record.agent.kind`: `cursor_adapter_v1` only (never `bounded_llm_v1`)
- `prompt_fixture` resolves under `demo/scenarios/tier1/`
- `prompt_sha256` matches fixture bytes at authoring time
- No `prompt` or `raw_prompt` fields in scenario JSON

### Run-group output dirs

| Act | `run_group` | `record.output_dir` |
|-----|-------------|---------------------|
| 1 | `agent-bugfix-1` | `data/agent-bugfix-1` |
| 2 | `agent-feature-compare` | `data/agent-feature-compare` |
| 3 | `agent-change` | `data/agent-change` |

Act 2 loops single-path `record-agent-change.sh` invocations per `change_paths` entry (v1 multi-path pattern).

---

## Orchestrator behavior

### CLI

`--dry-run`, `--act N` (1–3), `--json`, `-h`

### Dry-run

1. Load and validate tier1 scenario JSON for selected act(s).
2. For each `change_path`: print plan to stderr, run `record-agent-change.sh --dry-run` (stdout redirected to stderr when `--json`).
3. Call `compare-agent-runs.sh --dry-run --json` for compare triple plan.
4. Emit final JSON plan with `status: dry_run`, `acts[]`, `compare_plan`, `blockers`, `source_kind: derived_v1`.
5. No `nlfr.sqlite` writes; exit 0 on success.

### Live

- Substitutes `validation_fallback` when `NLFR_SKIP_BAZEL=1`.
- Requires change paths to exist before record.
- After Act 3: `compare-agent-runs.sh` (non-dry-run).
- Sets per-act env: `NLFR_AGENT_CHANGE_OUTPUT`, `NLFR_AGENT_CHANGE_RUN_GROUP`, `NLFR_AGENT_CHANGE_SCENARIO`, `NLFR_AGENT_CHANGE_WORKSPACE`.

---

## Proof commands

```bash
./scripts/tier1-agent-demo.sh --dry-run
./scripts/tier1-agent-demo.sh --dry-run --json
./scripts/tier1-agent-demo.sh --dry-run --act 1
```

All completed with exit 0 on 2026-06-06.

---

## Out of scope (other workers)

| Item | Owner |
|------|-------|
| `scripts/compare-agent-runs.sh` | `t1-spine-compare` (landed; orchestrator consumes) |
| `tests/test_tier1_agent_demo.py` | `t1-spine-tests` |
| Live DB population for run groups | `coord-t1-bugfix`, `coord-t1-feature` |

---

## Assumptions

- `compare-agent-runs.sh` remains on PATH at `$ROOT/scripts/` with `--dry-run --json` support.
- Operators pre-edit `change_paths` before live record; adapter does not invoke an LLM.

No raw prompts, credentials, or private paths exported in this handoff.
