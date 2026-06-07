# Wave 1.5 Integration Brief — T1-SPINE Design+Implement

**From:** Wave 1 research (`coord-t1-spine` + broker integration)  
**For:** Wave 2 workers (`t1-spine-orchestrator`, `t1-spine-compare`, `t1-spine-tests`)  
**Date:** 2026-06-06

## Purpose

Lock orchestration contracts before implementation. M8 adapter (`record-agent-change.sh`) and M9 compare projector are **landed**; Tier 1 gaps are demo packaging, compare rollup script, and fixture-backed tests.

---

## Research synthesis

| Surface | Status | Gap |
|---------|--------|-----|
| `record-agent-change.sh` + `generic_run.py` | Landed, tested | Single `--change-path`; tier1 acts need scenario-driven overrides |
| `nlfr compare export/index` | Landed | No tier1 rollup script |
| `compare-proof.sh` | Landed (2-group) | Pattern for `compare-agent-runs.sh` (3-group triple) |
| `demo/scenarios/*.json` | 4 simulate fixtures | No `tier1/` orchestration recipes |
| `data/compare-agent-runs/` | Partial host output | Missing script + 3rd pairwise pair |

**Kind vocabulary (do not conflate):**

| Label | Surface | `source_kind` |
|-------|---------|---------------|
| `bounded_llm_v1` | `demo/scenarios/llm-bounded-patch.json` simulate | `simulated_v1` |
| `cursor_adapter_v1` | `record-agent-change.sh` live record | `collectable_v1` |

Privacy shape is identical (`model` + `prompt_sha256`, no raw prompt). Tier1 docs must explain the kind split.

---

## Locked decision 1 — `demo/scenarios/tier1/` contract shape

### Schema: `nlfr.tier1.scenario.v1`

Tier1 scenarios are **orchestration recipes** for `tier1-agent-demo.sh` and `record-agent-change.sh`. They are **not** `nlfr.demo.scenario.v1` simulate fixtures (no embedded patch diffs).

```json
{
  "schema_version": "nlfr.tier1.scenario.v1",
  "scenario_id": "agent-bugfix-1",
  "act": 1,
  "title": "Bounded agent bugfix with validation proof",
  "run_group": "agent-bugfix-1",
  "narrative": "One-line demo story for operators.",
  "record": {
    "adapter": "record-agent-change.sh",
    "output_dir": "data/agent-bugfix-1",
    "workspace": ".",
    "change_paths": ["demo/bazel-monorepo/tasks/priority_test.py"],
    "validation_command": "cd demo/bazel-monorepo && bazel test //tasks:priority_test",
    "validation_fallback": "uv run pytest demo/bazel-monorepo/tasks/priority_test.py -q",
    "agent": {
      "kind": "cursor_adapter_v1",
      "name": "tier1-bugfix-agent",
      "model": "composer-2.5",
      "prompt_fixture": "fixtures/prompt-bugfix.txt",
      "prompt_sha256": "<64-hex precomputed at authoring time>"
    }
  },
  "related_simulate_scenario": "llm-bounded-patch",
  "proof_claims": [
    {
      "claim_id": "tier1.bugfix.provenance.hashed",
      "statement": "Agent provenance carries model + prompt_sha256; raw prompt withheld.",
      "source_kind": "collectable_v1",
      "confidence": "high",
      "evidence_refs": ["artifact:agent-provenance.json"],
      "redaction_state": "redacted"
    }
  ],
  "blockers": {
    "bazel": "Set NLFR_SKIP_BAZEL=1 to use validation_fallback on hosts without Bazel.",
    "nativelink": "Cache proof requires NativeLink; orchestrator documents skip."
  }
}
```

### Required files

| File | Act | `run_group` | Notes |
|------|-----|-------------|-------|
| `agent-bugfix-1.json` | 1 | `agent-bugfix-1` | Aligns change path with `llm-bounded-patch` workload |
| `agent-feature-compare.json` | 2 | `agent-feature-compare` | Feature slice; `change_paths` may list 2 paths |
| `agent-change-meta.json` | 3 | `agent-change` | Meta dogfood; validation via repo pytest smoke |
| `README.md` | — | — | Kind vocabulary + operator pre-edit requirement |
| `fixtures/prompt-*.txt` | — | — | One-line task stubs; hashed locally, never exported |

### Operator contract

1. Operator applies edit to `change_paths` **before** live record (adapter does not invoke an LLM).
2. `patch_applied: true` in provenance is honest only when files differ before/after generic run.
3. `validation_command` must fail on no-op edits where possible.

### Validation rules (tests enforce)

- `schema_version` must be `nlfr.tier1.scenario.v1`
- `record.agent.kind` must be `cursor_adapter_v1` (never `bounded_llm_v1`)
- `prompt_fixture` must resolve under `demo/scenarios/tier1/`
- `prompt_sha256` must match SHA-256 of fixture file contents
- No `prompt` or raw prompt fields anywhere in scenario JSON

---

## Locked decision 2 — `tier1-agent-demo.sh` orchestrator behavior

### CLI

```text
Usage: tier1-agent-demo.sh [--dry-run] [--act N] [--json]

Options:
  --dry-run   Plan only; no SQLite writes; exit 0
  --act N     Run single act (1, 2, or 3); default all
  --json      Emit machine-readable plan on stdout (dry-run and live summary)
  -h, --help  Usage
```

### Act sequence

| Act | Scenario file | Invokes | Post-record exports |
|-----|---------------|---------|---------------------|
| 1 | `agent-bugfix-1.json` | `record-agent-change.sh` with act env overrides | `nlfr graph export`, `nlfr proof export` |
| 2 | `agent-feature-compare.json` | same | same |
| 3 | `agent-change-meta.json` | same | same + `compare-agent-runs.sh` |

### `--dry-run` behavior (required for proof matrix)

1. Load all three tier1 scenario JSON files; validate schema fields.
2. For each act (or selected `--act`):
   - Print planned `record-agent-change.sh --dry-run` invocation (change path, model, prompt fixture, output dir, run group).
   - Actually execute adapter `--dry-run` subprocess; assert exit 0.
3. Invoke `compare-agent-runs.sh --dry-run` (or inline equivalent plan if compare script not yet on PATH during partial rollout — final state must call script).
4. Emit JSON plan:

```json
{
  "status": "dry_run",
  "acts": [{"act": 1, "run_group": "agent-bugfix-1", "commands": ["..."]}],
  "compare_plan": {"run_groups": ["record-proof", "canvas-dev", "agent-bugfix-1"], "pair_count": 3},
  "blockers": [],
  "source_kind": "derived_v1"
}
```

5. **Never** write `nlfr.sqlite` or mutate `data/*/runs/` in dry-run.
6. Exit 0 always when scenarios parse and adapter dry-runs succeed.

### Live behavior

1. Check blockers: if `NLFR_SKIP_BAZEL=1`, substitute `validation_fallback` from scenario.
2. For each act: require change paths exist; run `record-agent-change.sh` (non-dry-run) with scenario-derived flags.
3. After Act 3: run `compare-agent-runs.sh` (non-dry-run).
4. Exit non-zero with stderr blocker message when:
   - Scenario file missing or invalid
   - Required output dir DB missing **and** `NLFR_TIER1_REQUIRE_DB=1`
   - Adapter or compare subprocess fails

### Env passthrough (orchestrator sets per act)

| Env | Set from scenario field |
|-----|-------------------------|
| `NLFR_AGENT_CHANGE_OUTPUT` | `record.output_dir` |
| `NLFR_AGENT_CHANGE_RUN_GROUP` | `run_group` |
| `NLFR_AGENT_CHANGE_SCENARIO` | `scenario_id` |
| `NLFR_AGENT_CHANGE_WORKSPACE` | `record.workspace` |

### Out of scope for wave 2

- Live Cursor SDK / automatic patch application
- Multi-path `--change-path` in shell (orchestrator may loop single-path invocations if act has >1 path, or document single-path for v1)

---

## Locked decision 3 — `compare-agent-runs.sh` env vars and default triple

### Default compare triple (Act 3 narrative)

```text
record-proof  ↔  canvas-dev  ↔  agent-bugfix-1
```

Three pairwise projections (3 choose 2 = 3):

1. `record-proof` vs `canvas-dev`
2. `canvas-dev` vs `agent-bugfix-1`
3. `record-proof` vs `agent-bugfix-1` ← **missing today; must add**

`agent-feature-compare` is **not** in the default triple; reserved for Act 2 pairwise when `NLFR_TIER1_GROUPS` overridden.

### Env contract

| Env var | Default | Purpose |
|---------|---------|---------|
| `NLFR_COMPARE_AGENT_OUTPUT` | `data/compare-agent-runs` | Rollup output root |
| `NLFR_TIER1_GROUPS` | `record-proof,canvas-dev,agent-bugfix-1` | Comma-separated compare triple |
| `NLFR_RECORD_PROOF_OUTPUT` | `data/record-proof` | DB root for `record-proof` |
| `NLFR_CANVAS_DEV_OUTPUT` | `data/canvas-dev` | DB root for `canvas-dev` |
| `NLFR_AGENT_BUGFIX_OUTPUT` | `data/agent-bugfix-1` | DB root for `agent-bugfix-1` |
| `NLFR_AGENT_FEATURE_OUTPUT` | `data/agent-feature-compare` | DB root for Act 2 (optional override) |
| `NLFR_TIER1_REQUIRE_DB` | `0` | `1` → exit non-zero if any group DB/run missing |

### CLI

```text
Usage: compare-agent-runs.sh [--dry-run] [--json]

  --dry-run   Emit planned pairs + DB paths; no writes; exit 0
  --json      Machine-readable summary on stdout
```

### Script behavior

1. Parse `NLFR_TIER1_GROUPS` into ordered group list (≥2 groups).
2. Map each group → output dir via fixed lookup table (env overrides above).
3. **`--dry-run`:** print 3 planned cross-DB exports; do not require `nlfr.sqlite`; exit 0.
4. **Live:** for each adjacent pair in canonical order **and** closing pair (record-proof vs agent-bugfix-1):
   - Verify `{output}/nlfr.sqlite` exists
   - Call `nlfr compare index` — fail loudly if run group absent from index
   - Reuse `build_compare_projection` exactly as `compare-proof.sh` (embedded Python pattern)
   - Write `compare-{left}-vs-{right}.json` under `$NLFR_COMPARE_AGENT_OUTPUT/projections/`
5. Write rollup `summary.json`:

```json
{
  "status": "ok",
  "compare_count": 3,
  "run_groups": ["record-proof", "canvas-dev", "agent-bugfix-1"],
  "pairwise_compares": [".../compare-record-proof-vs-canvas-dev.json", "..."],
  "dimension_ids": ["run_counts", "cache_metrics", "worker_identity", "agent_provenance", "status_deltas"],
  "source_kind": "derived_v1",
  "confidence": "medium",
  "redaction_state": "safe",
  "evidence_refs": ["run_group:record-proof", "run_group:canvas-dev", "run_group:agent-bugfix-1"]
}
```

6. Do **not** invent new compare dimensions; five-dimension M9 projector only.

### Canvas promotion (document only; T1-INTEGRATE owns copy)

Recommended demo pairwise for `apps/canvas/public/projections/compare-projection.json`:

`compare-canvas-dev-vs-agent-bugfix-1.json` (agent_provenance dimension visible)

---

## Locked decision 4 — Run-group output directories

| Run group | Output dir (`record.output_dir`) | Act | Notes |
|-----------|----------------------------------|-----|-------|
| `agent-bugfix-1` | `data/agent-bugfix-1` | 1 | Tier1 bounded bugfix record |
| `agent-feature-compare` | `data/agent-feature-compare` | 2 | Feature slice; pairs with bugfix in narrative |
| `agent-change` | `data/agent-change` | 3 | Meta dogfood (Act 3) |

**Not** `data/agent-change-proof` — that remains the M8 adapter **default** when operators run `record-agent-change.sh` without tier1 orchestration. Tier1 Act 3 explicitly targets `data/agent-change`.

### Artifact layout (all three)

```text
data/{run-group}/
  nlfr.sqlite
  runs/{run_id}/artifacts/...
  agent-provenance.json          # when sidecar ingested
  projections/action-graph.json  # after export
  projections/proof.json
  summary.json                   # adapter or orchestrator rollup
```

### Cross-DAG dependencies

| Consumer | Expects |
|----------|---------|
| `compare-agent-runs.sh` default triple | `data/record-proof`, `data/canvas-dev`, `data/agent-bugfix-1` populated |
| `coord-t1-bugfix` wave 2 | `agent-bugfix-1` scenario + OUT dir contract |
| `coord-t1-feature` wave 2 | `agent-feature-compare` OUT dir contract |
| `coord-t1-integrate` wave 3 | `tier1-agent-demo.sh --dry-run` in proof matrix |

Wave 2 spine workers deliver **scripts + scenarios + tests** only. Live DB population is `coord-t1-bugfix` / `coord-t1-feature` responsibility.

---

## Wave 2 worker scopes (disjoint)

| worker_id | write_scope | deliverable |
|-----------|-------------|-------------|
| `t1-spine-orchestrator` | `scripts/tier1-agent-demo.sh`, `demo/scenarios/tier1/` | Orchestrator + 3 scenarios + README + fixtures |
| `t1-spine-compare` | `scripts/compare-agent-runs.sh` | Triple compare rollup script |
| `t1-spine-tests` | `tests/test_tier1_agent_demo.py` | Dry-run contract tests; optional fixture DB test |

---

## Proof gates (wave 2 completion)

```bash
uv run pytest tests/test_tier1_agent_demo.py -q
./scripts/tier1-agent-demo.sh --dry-run
./scripts/compare-agent-runs.sh --dry-run
```

Parent umbrella matrix (after integrate):

```bash
uv run pytest -q
./scripts/tier1-agent-demo.sh --dry-run
./scripts/compare-agent-runs.sh
```

---

## Handoff artifact index

| Worker (wave 1) | Provenance |
|-----------------|------------|
| t1-spine-r-adapter-scenario | `wave-1/provenance-t1-spine-audit-adapter-scenario.md` |
| t1-spine-r-compare-retention | `wave-1/provenance-t1-spine-audit-compare-retention.md` |
| broker integrate | `wave-1/worker-results.json` |
| coord-t1-spine reflect | this brief |

---

## Open questions (deferred — not blockers for wave 2)

1. Extend `record-agent-change.sh` with multi `--change-path` vs orchestrator loop — prefer loop in v1.
2. Bazel validation on CI hosts — `NLFR_SKIP_BAZEL=1` fallback is acceptable for pytest-only CI.
3. `agent-feature-compare` inclusion in extended compare groups — env override only; default triple unchanged.
