# Demo Scenarios

Each scenario is a deterministic `nlfr.demo.scenario.v1` JSON file describing a
simulated-agent change to `demo/bazel-monorepo`. `nlfr simulate` applies the
patch to a copied workspace (never the source) and records simulated-agent and
patch provenance. No scenario makes a live LLM call.

| Scenario | Change class | Models |
|----------|--------------|--------|
| `safe-leaf-change` | safe_leaf | low-risk leaf assertion that passes |
| `shared-module-change` | shared module | edit with broader blast radius |
| `nondeterministic-test-change` | flaky | non-deterministic test outcome |
| `llm-bounded-patch` | safe_leaf | bounded LLM patch with hashed-prompt provenance |

## Bounded LLM patch (`llm-bounded-patch`)

This is the reference pattern for real agent provenance under the `AGENTS.md`
privacy rule. The scenario's `simulated_agent` carries a `model` label and a
`prompt_sha256` — the SHA-256 hash of the prompt. The raw prompt is never stored
or exported; only the hash. As a fixture it is `simulated_v1` and remains
deterministic.

It drives the M4 agent-loop closure proof:

```bash
scripts/agent-loop-proof.sh
```

Inside `nix develop`, that script applies the patch, runs Bazel through the
NativeLink cache, ingests validation+cache evidence (`simulate --ingest`), and
exports projections. The Action Graph shows `agent → (authored_change) → change
→ (validated_by) → run → target → action → cache_event`, with
`data/agent-loop-proof/summary.json` carrying `chain_complete=true` and
`source_kind: collectable_v1`.

Without Nix, `./scripts/verify-demo.sh` exports a **simulated_v1** agent-loop chain
to `data/demo-proof/projections/` only. The committed canvas default is
**canvas-dev `collectable_v1`** from `./scripts/record-canvas-build.sh`.

## Truth labels

Simulated scenario claims are `simulated_v1`. Only after a real run captures and
ingests Bazel evidence do validation/cache facts become `collectable_v1`.
Worker identity, scheduler assignment, queue time, action placement, and load
distribution stay unsupported until direct worker evidence is captured.
