# Reference: proof scripts matrix

**Quadrant:** Reference · **Audience:** proof reviewers, release operators

Map each proof script to its claim boundary, artifact path, and typical
`source_kind`. Do not cite a script as proving a claim outside its boundary.

← [Wiki hub](../README.md) · [One pager](../../ONE_PAGER.md) · [Architecture track](../../ARCHITECTURE_TRACK.md)

## Core spine (fixture-friendly)

| Script | Claim / outcome | Artifact | `source_kind` | Nix required |
|--------|-----------------|----------|---------------|------------|
| `scripts/verify-demo.sh` | End-to-end fixture demo + exports | `data/demo-proof/` | mixed | No |
| `scripts/record-proof.sh` | Dogfood record path for canvas dev | `data/record-proof/` | `collectable_v1` | Optional |

Local gates:

```bash
uv run pytest -q
./scripts/verify-demo.sh
```

## Cache economics (M2)

| Script | Claim | Artifact | Labels |
|--------|-------|----------|--------|
| `scripts/cold-warm-cache-proof.sh` | Warm `hit_rate` > cold; duration delta | `data/cold-warm-proof/summary.json` | `collectable_v1`, `high` |

Tutorial: [first Nix proof](../tutorial/first-nix-proof.md).

## Remote execution ladder (M3)

| Script | Claim | Artifact | Notes |
|--------|-------|----------|-------|
| `scripts/local-exec-proof.sh` | `worker_endpoints_ready` | `data/local-exec-proof/summary.json` | 1-worker default |
| `NLFR_EXPECTED_WORKERS=2 … local-exec-proof.sh` | Two workers configured + live endpoints | `data/local-exec-proof-2w/summary.json` | Not work distribution |

Unsupported after these steps: scheduler assignment, queue time, action placement,
load distribution — [One pager](../../ONE_PAGER.md).

## M7 worker evidence

| Script | Claim | Artifact | Condition |
|--------|-------|----------|-----------|
| `scripts/worker-evidence-proof.sh` | `worker_identity_observed: true` | `data/worker-evidence-proof/summary.json` | Stdout attached pre-ingest + M7 regex |

Default path: fixture replay when NativeLink absent. Live path chains with
`local-exec-proof.sh` inside Nix.

Parser: `src/nlfr/ingest/worker_admin_stdout.py`.

## M4 agent loop

| Script | Claim | Artifact | Labels |
|--------|-------|----------|--------|
| `scripts/agent-loop-proof.sh` | `chain_complete=true` (agent→change→run→cache) | `data/agent-loop-proof/summary.json` | validation `collectable_v1`; agent leg `simulated_v1` |

Bounded scenario: `demo/scenarios/llm-bounded-patch.json`.

## M8 agent adapter

| Script | Claim | Artifact | Notes |
|--------|-------|----------|-------|
| `scripts/record-agent-change.sh` | Agent provenance sidecar + validation capture | `data/agent-change-proof/` | `model` + `prompt_sha256` only |

Adapter doc: [adapters/cursor/README.md](../../../adapters/cursor/README.md).

## M9 compare

| Script | Claim | Artifact | Labels |
|--------|-------|----------|--------|
| `scripts/compare-proof.sh` | Cross run-group compare projection | `data/compare-proof/summary.json` | `derived_v1` |

How-to: [export and compare run groups](../how-to/export-and-compare-run-groups.md).

## Tier1 live Bazel

| Script | Claim | Artifact | Notes |
|--------|-------|----------|-------|
| `scripts/tier1-live-bazel-proof.sh` | Tier1 Acts 1+2 live Bazel | `data/tier1-live-bazel/summary.json` | No LRE / placement |
| `scripts/tier1-bazel-ci-proof.sh` | CI-oriented tier1 Bazel slice | per env | See [ci-bazel-tier1](../../dags/ci-bazel-tier1.md) |

How-to: [run tier1 live Bazel demo](../how-to/run-tier1-live-bazel-demo.md).  
DAG: [tier1-live-bazel](../../dags/tier1-live-bazel.md).

## LRE proof ladder

| Script | Phase | Claim | Artifact |
|--------|-------|-------|----------|
| `scripts/lre-proof.sh` | 1 | `lre_substrate_ready` | `data/lre-proof/summary.json` |
| `scripts/lre-nix-toolchain-proof.sh` | 2 | `lre_bazelrc_generated` | `data/lre-nix-toolchain-proof/summary.json` |
| `scripts/lre-cold-warm-proof.sh` | 4 | `lre_cache_parity_observed` | `data/lre-cold-warm-proof/summary.json` |

**Ceiling:** x86_64-linux green path; darwin may emit blocker samples. CI parity
deferred while GHA offline — [GHA offline proof shift](../../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

DAG: [lre-proof](../../dags/lre-proof.md).  
Samples: [proof-samples/lre-cold-warm-*](../../proof-samples/README.md).

## Fleet evidence v1

Broadens **stdout pre-ingest** so M7 can promote `worker_identity` on more proof
scripts. Does **not** add fleet dashboards or scheduler claims.

| Script | Stdout attach status | DAG |
|--------|---------------------|-----|
| `local-exec-proof.sh` | Landed | [fleet-evidence-v1](../../dags/fleet-evidence-v1.md) |
| `worker-evidence-proof.sh` | Landed | same |
| `agent-loop-proof.sh` | Pending breadth worker | same |
| `cold-warm-cache-proof.sh` | Pending breadth worker | same |

Claim ceiling: `stdout_ingest_breadth` (`collectable_v1`, `high`).  
Unsupported: `scheduler_assignment`, `queue_time`, `action_placement`, `load_distribution`.

Research: [fleet-evidence-v1 wave-0 research](../../sessions/handoffs/fleet-evidence-v1/wave-0/research-nativelink-stdout-formats.md).

## Canvas capture

| Script | Purpose |
|--------|---------|
| `apps/canvas/scripts/capture-proof.mjs` | Truth-guarded media capture |
| `npm --prefix apps/canvas run capture` | Hero GIF regeneration |

See [Media capture](../../MEDIA_CAPTURE.md).

## pytest matrix (quick)

```bash
uv run pytest -q
uv run pytest tests/test_compare.py -q
uv run pytest tests/test_lre_proof.py -q
uv run pytest tests/test_tier1_live_bazel.py -q
uv run pytest tests/test_worker_admin_stdout.py -q
```

## GHA offline

Parent proof gates substitute for CI:

```bash
uv run pytest -q
bash -n scripts/*.sh
```

Do not claim CI-green summaries until workflows actually pass.
