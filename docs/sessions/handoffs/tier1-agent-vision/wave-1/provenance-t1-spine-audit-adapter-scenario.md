# T1-SPINE Audit — Adapter, Generic Run, Demo Scenarios

**Worker:** `t1-spine-r-adapter-scenario` (explore)  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

## Executive summary

The M8 bounded-agent spine is **landed and test-backed**: `record-agent-change.sh` hashes prompts locally, emits a `nlfr.agent_provenance.sidecar.v1` payload with `cursor_adapter_v1`, and invokes `nlfr run --mode generic` with `--provenance-sidecar`. `generic_run.py` materializes `agent-provenance.json`, upserts an `agent_provenance` proof block, and records before/after path hashes. Demo scenarios under `demo/scenarios/` model the same privacy contract at `simulated_v1` via `bounded_llm_v1`, not `cursor_adapter_v1`.

Tier 1 gaps are **orchestration and scenario packaging**, not core provenance mechanics: missing `demo/scenarios/tier1/`, `tier1-agent-demo.sh`, and a first-class tier-1 scenario JSON that bridges demo fixtures to live `record-agent-change.sh` run groups (`agent-bugfix-1`, `agent-feature-compare`, `agent-change`).

---

## Artifact inventory

| Path | Role | Truth posture |
|------|------|---------------|
| `scripts/record-agent-change.sh` | Cursor/CLI adapter shell | `collectable_v1` on dry-run and live summary |
| `src/nlfr/commands/generic_run.py` | Generic recorder + provenance ingest | `collectable_v1` for runs, changes, proof blocks |
| `tests/test_record_agent_change.py` | Adapter contract tests | Fixture-backed; no live agent |
| `adapters/cursor/README.md` | Operator guide | Documents privacy + workflow |
| `demo/scenarios/llm-bounded-patch.json` | Reference simulated scenario | `simulated_agent.kind` = `bounded_llm_v1` |
| `demo/scenarios/*.json` (4 total) | Deterministic simulate fixtures | All `nlfr.demo.scenario.v1` |
| `data/agent-change-proof/` | M8 dogfood output dir | Exists when operator runs adapter |
| `data/agent-bugfix-1/`, `data/agent-feature-compare/`, `data/agent-change/` | Tier 1 run-group dirs | Present on host; not yet wired to tier1 demo script |

---

## `record-agent-change.sh` — behavior audit

### Inputs and privacy

Required flags: `--change-path`, `--model`, `--prompt-file`. Optional: `--command` (default `true`), `--output-dir`, `--workspace`, `--scenario`, `--run-group`, `--dry-run`.

Privacy contract is enforced at three layers:

1. **Shell:** reads prompt file only to compute SHA-256 via embedded Python; never echoes prompt text in dry-run JSON.
2. **Sidecar:** schema `nlfr.agent_provenance.sidecar.v1`; `agent.input_signal` = `"redacted: prompt withheld, hash retained"`.
3. **Generic run:** `_load_provenance_sidecar` rejects sidecars containing `agent.prompt`.

Defaults align with Tier 1 Act 3 meta dogfood:

- `SCENARIO` / `RUN_GROUP` default to `agent-change`
- `OUT` defaults to `data/agent-change-proof`

### Sidecar shape (live adapter)

```json
{
  "schema_version": "nlfr.agent_provenance.sidecar.v1",
  "adapter": "record-agent-change.sh",
  "change_class": "bounded_agent_v1",
  "agent": {
    "kind": "cursor_adapter_v1",
    "name": "cursor-agent-change",
    "model": "<label>",
    "prompt_sha256": "<64-hex>",
    "input_signal": "redacted: prompt withheld, hash retained"
  }
}
```

### Post-run pipeline

On non-dry-run:

1. `uv run python -m nlfr run --mode generic ... --json` → `run.json`
2. `nlfr graph export` → `projections/action-graph.json`
3. `nlfr proof export` → `projections/proof.json`
4. Embedded Python builds `summary.json` with mixed but honest labels (`agent_source_kind` from provenance, `validation_source_kind` from run payload).

Evidence refs in summary: `run.json`, `agent-provenance.json`, both projection files.

---

## `generic_run.py` — provenance spine

### Generic run lifecycle

1. Resolve workspace, output dir, stable `run_id` from `scenario:generic:timestamp`.
2. Snapshot `before_hashes` for each `--change-path`.
3. Execute one or more `--command` strings via `ProcessRunner` (stdout/stderr artifacts).
4. Snapshot `after_hashes`; upsert `generic_path` change rows.
5. Write `run.json` manifest; optionally ingest provenance sidecar.

### Provenance sidecar → artifacts

When `--provenance-sidecar` is set:

- Loads and validates sidecar (model + prompt_sha256 required; raw prompt forbidden).
- Builds `nlfr.agent_provenance.v1` payload via `_agent_provenance_payload`.
- Writes `agent-provenance.json` to artifact root.
- Upserts `agent_provenance` proof block with title `Agent Provenance: {name}`.

Key fields in exported provenance:

| Field | Source |
|-------|--------|
| `agent.kind` | sidecar, default `cursor_adapter_v1` |
| `change.affected_paths` | `--change-path` list |
| `change.before_hashes` / `after_hashes` | workspace file SHA-256 |
| `change.patch_applied` | always `true` (honest only if operator edited before record) |
| `build.status` | terminal command status |

### Graph projection hook

Change rows and `agent_provenance` proof blocks feed action-graph and proof projectors. The adapter does **not** invent graph nodes; projection derives `agent` and `change` nodes from ingested SQLite facts.

---

## `tests/test_record_agent_change.py` — contract coverage

| Test | Asserts |
|------|---------|
| `test_record_agent_change_dry_run_emits_hashed_provenance` | Exit 0; dry_run JSON; sidecar schema; no `prompt` key; prompt text absent from stdout |
| `test_provenance_sidecar_shape_matches_bounded_patch_contract` | Sidecar agent fields ⊇ `{kind, name, model, prompt_sha256}`; 64-char hash; cross-checks `llm-bounded-patch.json` simulated_agent |
| `test_generic_run_records_agent_provenance_from_sidecar` | Full generic run with synthetic sidecar; `agent-provenance.json` shape; SQLite `agent_provenance` proof block |

**Not covered (Tier 1 should add):**

- End-to-end `record-agent-change.sh` without `--dry-run` in CI
- Bazel validation leg through adapter (`--command` with `bazel test`)
- Multi-path `--change-path` (generic run supports append; script exposes single path)
- Scenario/run-group overrides for `agent-bugfix-1` and `agent-feature-compare`

---

## Demo scenarios vs `cursor_adapter_v1`

### Scenario catalog (`demo/scenarios/`)

| File | `change_class` | Agent kind | Use |
|------|----------------|------------|-----|
| `safe-leaf-change.json` | safe_leaf | simulated (non-LLM) | Low-risk leaf assertion |
| `shared-module-change.json` | shared module | simulated | Broader blast radius |
| `nondeterministic-test-change.json` | flaky | simulated | Non-deterministic outcome |
| `llm-bounded-patch.json` | safe_leaf | **`bounded_llm_v1`** | Hashed-prompt reference pattern |

All scenarios are `nlfr.demo.scenario.v1`. They drive `nlfr simulate`, not `record-agent-change.sh`.

### Kind mismatch (intentional)

| Surface | `agent.kind` | `source_kind` | Live LLM? |
|---------|--------------|---------------|-----------|
| Demo `llm-bounded-patch` | `bounded_llm_v1` | `simulated_v1` | No — deterministic fixture |
| `record-agent-change.sh` | `cursor_adapter_v1` | `collectable_v1` | No — records after human/agent edit |
| Compare dimension `agent_provenance` | either | `derived_v1` | Detects proof blocks, not kind |

The **privacy shape** aligns (`model` + `prompt_sha256`, no raw prompt). The **kind label** differs to distinguish simulate fixtures from live adapter metadata. Tier 1 should document this in `demo/scenarios/tier1/` rather than conflating kinds.

### `llm-bounded-patch` cross-reference

Fixture `simulated_agent`:

- `model`: `demo-bounded-llm`
- `prompt_sha256`: `5f787e73...` (fixed)
- `affected_paths`: `tasks/priority_test.py` in `demo/bazel-monorepo`

`test_provenance_sidecar_shape_matches_bounded_patch_contract` uses this fixture as the bounded-patch contract reference. Adapter tests use `composer-2.5` or `demo-bounded-llm` labels interchangeably for shape checks only.

---

## Tier 1 DAG alignment (`docs/dags/tier1-agent-vision.md`)

| Act | Run group | Adapter/scenario hook |
|-----|-----------|----------------------|
| 1 Bounded bugfix | `agent-bugfix-1` | Needs tier1 scenario + `record-agent-change.sh` with overridden run group |
| 2 Feature slice | `agent-feature-compare` | Same adapter; compare narrative pairs with baseline |
| 3 Meta dogfood | `agent-change` | **Default** adapter run group today |

`data/agent-bugfix-1/`, `data/agent-feature-compare/`, and `data/agent-change/` exist on the development host, indicating partial dogfood. No `demo/scenarios/tier1/` directory yet.

---

## Gaps for Tier 1 / T1-SPINE wave 2

### P0 — orchestration

1. **`scripts/tier1-agent-demo.sh`** — referenced in DAG proof matrix; **missing**. Should dry-run all three acts, document env blockers (Bazel/NativeLink), and chain record + export steps.
2. **`demo/scenarios/tier1/`** — charter deliverable; **missing**. Need three scenario JSON files mapping acts to change paths, validation commands, and expected proof claims.
3. **`tests/test_tier1_agent_demo.py`** — charter deliverable; **missing**.

### P1 — adapter hardening

4. **Single `--change-path` in shell** — generic run supports multiple paths; tier1 bugfix may touch test + impl; extend script or document multi-invocation pattern.
5. **`patch_applied: true` semantics** — provenance always sets true; tier1 should require pre-edit + validation command that fails on no-op to avoid false claims.
6. **Bazel validation leg** — adapter README shows pytest; tier1 demo narrative expects Bazel/NativeLink cache proof where host allows.

### P2 — scenario bridge

7. **Unify kind vocabulary in docs** — `bounded_llm_v1` (simulate) vs `cursor_adapter_v1` (live); add `tier1/README.md` explaining when each applies.
8. **Agent node in graph** — verify `agent-bugfix-1` projection includes `agent → change` chain from `agent_provenance` block; add fixture test if not asserted.
9. **CI smoke** — add `record-agent-change.sh --dry-run` to tier1 proof matrix (already in M8; promote to `tier1-agent-demo.sh --dry-run`).

### Out of scope (correctly deferred)

- Live Cursor SDK integration (adapter is manual post-edit record)
- Raw prompt export or session transcript ingest
- Worker/scheduler correlation in agent provenance

---

## Proof commands (current state)

```bash
# Adapter contract (passes today)
uv run pytest tests/test_record_agent_change.py -q

# Dry-run smoke (no SQLite writes)
./scripts/record-agent-change.sh \
  --dry-run \
  --change-path README.md \
  --model composer-2.5 \
  --prompt-file README.md

# Full record (operator; writes data/agent-change-proof/)
./scripts/record-agent-change.sh \
  --change-path <edited-file> \
  --model composer-2.5 \
  --prompt-file /tmp/prompt.txt \
  --command "uv run pytest tests/test_record_agent_change.py -q"
```

---

## Source map

| Artifact | Path |
|----------|------|
| Adapter script | `scripts/record-agent-change.sh` |
| Generic run | `src/nlfr/commands/generic_run.py` |
| Tests | `tests/test_record_agent_change.py`, `tests/test_generic_run.py` |
| Cursor guide | `adapters/cursor/README.md` |
| Demo scenarios | `demo/scenarios/*.json`, `demo/scenarios/README.md` |
| M8 provenance | `docs/sessions/handoffs/m5-m9-umbrella/wave-2/provenance-m8-agent-adapter.md` |
| Tier 1 DAG | `docs/dags/tier1-agent-vision.md` |

No raw prompts, credentials, or private paths were exported in this handoff.
