# Tier 1 orchestration scenarios (`nlfr.tier1.scenario.v1`)

Tier 1 scenarios are **orchestration recipes** for `scripts/tier1-agent-demo.sh` and
`scripts/record-agent-change.sh`. They are **not** `nlfr.demo.scenario.v1` simulate
fixtures — there are no embedded patch diffs.

## Kind vocabulary (do not conflate)

| Label | Surface | `source_kind` | Live LLM? |
|-------|---------|---------------|-----------|
| `bounded_llm_v1` | `demo/scenarios/llm-bounded-patch.json` (`nlfr simulate`) | `simulated_v1` | No — deterministic fixture |
| `cursor_adapter_v1` | `record-agent-change.sh` live record | `collectable_v1` | No — records after operator edit |

Privacy shape is identical (`model` + `prompt_sha256`, no raw prompt). Only the **kind
label** differs so simulate fixtures are not confused with live adapter metadata.

## Acts and run groups

| Act | Scenario file | `run_group` | Output dir |
|-----|---------------|-------------|------------|
| 1 | `agent-bugfix-1.json` | `agent-bugfix-1` | `data/agent-bugfix-1` |
| 2 | `agent-feature-compare.json` | `agent-feature-compare` | `data/agent-feature-compare` |
| 3 | `agent-change-meta.json` | `agent-change` | `data/agent-change` |

Act 1 aligns `change_paths` with `llm-bounded-patch` (`demo/bazel-monorepo/tasks/priority_test.py`).
Act 2 aligns with `shared-module-change` (`policy.py`, optional `priority.py`).
Act 3 is M8 meta dogfood; compare triple runs after Act 3 live.

## Operator contract

1. **Apply edits before live record** — the adapter does not invoke an LLM. Edit every path
   listed in `record.change_paths` in your workspace before running live.
2. **`patch_applied: true` is honest only when files differ** before/after the generic run.
3. **`validation_command` should fail on no-op edits** where possible so empty records are caught.

## Prompt fixtures

One-line task stubs live under `fixtures/prompt-*.txt`. Each scenario carries a
precomputed `prompt_sha256` of the fixture contents. Fixtures are hashed locally and
**never exported** in scenario JSON or NLFR artifacts.

## Blockers

| Env | Effect |
|-----|--------|
| `NLFR_SKIP_BAZEL=1` | Acts 1–2 use `validation_fallback` (pytest) instead of Bazel |
| `NLFR_TIER1_REQUIRE_DB=1` | Orchestrator exits non-zero if compare group DBs are missing (live) |

## Dry-run proof

```bash
./scripts/tier1-agent-demo.sh --dry-run
./scripts/tier1-agent-demo.sh --dry-run --act 1 --json
```

Dry-run validates scenarios, runs adapter `--dry-run` subprocesses, and plans the Act 3
compare triple (`record-proof`, `canvas-dev`, `agent-bugfix-1`) without SQLite writes.
