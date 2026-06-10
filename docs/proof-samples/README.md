# Proof samples — flagship honesty hub

**Audience:** evaluators, buyers, and skeptical engineers who will not run Nix,
Bazel, or NativeLink locally.

**Quadrant:** Reference (schema mirrors) + Explanation (claim boundaries).

These are redacted excerpts of real `summary.json` evidence files produced by NLFR
proof scripts. They let you read what the recorder captured **without** trusting
marketing prose or a live demo.

## Honesty contract

Every sample in this directory follows the same rules:

1. **Faithful shape** — JSON mirrors a real run summary; only absolute host paths
   are replaced with `<repo>` and the Nix-store Bazel path with `<bazel>`.
2. **Hashes preserved** — run IDs and SHA-256 digests carry no secrets and stay
   intact for cross-checking.
3. **No secrets** — no raw prompts, logs, environment variables, credentials, or
   customer data.
4. **Truth labels intact** — each row below lists `source_kind` and what the
   sample does **not** claim.

The canvas renders projection JSON only. These files are the ground truth for what
those projections may say — not invented backend state.

**Provenance today:** samples are sourced from author Nix runs on a development
host (tag `v0.2.0-mvp`). Promotion from the first green GitHub Actions run is
documented in [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md) — deferred until
the first sustained green public CI run.

## GHA restore promotion

When [`nlfr-proof.yml`](../../.github/workflows/nlfr-proof.yml) returns sustained
green, copy redacted CI `summary.json` (or honest blockers) into this directory
per the artifact → sample map in
[`CI_PROMOTION_MATRIX.md`](CI_PROMOTION_MATRIX.md).

| CI job | Artifact bundle | Primary committed targets |
|--------|-----------------|---------------------------|
| `linux-nix-toolchain` | `nix-toolchain-proof` | `cold-warm-summary.json`, `agent-loop-summary.json` |
| `tier1-bazel` | `tier1-bazel-ci` | `agent-bugfix-summary.json`, `agent-feature-summary.json` (Act excerpts from combined CI summary) |
| `lre-proof-probe` | `lre-proof-probe` | `lre-proof-summary-sample.json` or `lre-proof-blocker-sample.json` |
| `lre-nix-ci` | `lre-nix-toolchain-proof` | `lre-nix-toolchain-proof-*-sample.json` |
| `lre-cold-warm-ci` | `lre-cold-warm-proof` | `lre-cold-warm-proof-*-sample.json` |
| `unit` | `record-proof` | *(none — generic record; not promoted)* |
| `verify-demo-fixture` | `demo-proof` | *(none — fixture demo gate only)* |

**Not CI-gated today:** `two-worker-summary.json`, `compare-summary.json`,
`agent-live-*`, `lre-cold-warm-proof-linux-manual-sample.json`, and optional M7
worker-evidence — see
[Local-only sources](CI_PROMOTION_MATRIX.md#local-only-sources-no-dedicated-ci-job)
in the matrix.

After promotion, update the provenance note above to cite the Linux workflow run
URL and refresh catalog rows if metrics changed. Full operator steps:
[`../GHA_RESTORE_RUNBOOK.md`](../GHA_RESTORE_RUNBOOK.md) Phase 2.

## Milestone map (M7 · M8 · M9 · Tier 1)

| Milestone | What landed | Honesty ceiling |
|-----------|-------------|-----------------|
| **M7** worker parser | `worker_admin_stdout` promotes `worker_identity` when admin stdout is attached pre-ingest **and** lines match the M7 regex | **Conditional** — not global. Runs without captured stdout keep `worker_identity` in `unsupported_claims`. |
| **M8** agent adapter | `record-agent-change.sh` + `agent-live-proof.sh`; `model` + `prompt_sha256` only; dry-run, pytest fixture, and honest Cursor CLI blocker proven | Agent leg is `collectable_v1` via `cursor_adapter_v1` when adapter records; `simulated_v1` only in bounded `agent-loop-proof.sh`. Live Cursor session is operator-gated — see [`agent-live-blocker-sample.json`](agent-live-blocker-sample.json). |
| **M9** multi-run compare | `nlfr compare export`, canvas Compare lens, `scripts/compare-proof.sh` | `derived_v1` compare projection — no new collectable fleet claims. [`compare-summary.json`](compare-summary.json) excerpt committed. |
| **Tier 1** live Bazel | `scripts/tier1-live-bazel-proof.sh` Acts 1+2 with `cursor_adapter_v1` + real Bazel | Fully `collectable_v1` with `bazel_validated: true` — not pytest fallback. |

Fleet claim policy (what v1 will and will not promote) lives in
[`fleet-claims-matrix-sample.json`](fleet-claims-matrix-sample.json) and
[`../dags/future-fleet-claims.md`](../dags/future-fleet-claims.md).

## Sample catalog

### Cache and remote execution (`collectable_v1`)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`cold-warm-summary.json`](cold-warm-summary.json) | `scripts/cold-warm-cache-proof.sh` | `collectable_v1` · `high` | Cold: `hit_rate` 0.0 / 8.17s. Warm: `hit_rate` 1.0 / 5.48s. Warm is faster with higher hit rate. |
| [`two-worker-summary.json`](two-worker-summary.json) | `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh` | `collectable_v1` · `high` | Two workers configured **and** endpoints opened live (`worker_endpoints_ready`, `expected_workers=2`). `nativelink.stdout.txt` / `.stderr.txt` attached pre-ingest. Does **not** prove work distribution. `worker_identity` stays in `unsupported_claims` here unless M7 regex matches attached stdout. |

### Agent loop, live adapter, and Tier 1 (`collectable_v1` / mixed)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`agent-loop-summary.json`](agent-loop-summary.json) | `scripts/agent-loop-proof.sh` | mixed: `collectable_v1` validation/cache; `simulated_v1` agent/change · `high` | Deterministic bounded-agent patch validates `agent → change → run → target → action → cache_event` (`chain_complete=true`). `model` + `prompt_sha256` only — never the raw prompt; no live LLM call. |
| [`agent-live-blocker-sample.json`](agent-live-blocker-sample.json) | `scripts/agent-live-proof.sh` (no Cursor CLI) | `collectable_v1` · `high` | Honest `environment_blocker` when `cursor` is unavailable; documents M8 ceiling vs live adapter. Does **not** fake a collectable run. |
| [`agent-live-summary-sample.json`](agent-live-summary-sample.json) | `scripts/agent-live-proof.sh` (fixture / pytest validation) | `collectable_v1` · `high` | `cursor_adapter_v1` agent leg with `chain_complete=true` via `agent → change → run`; `model` + `prompt_sha256` only. Pytest validation path — not Tier 1 Bazel parity. |
| [`agent-bugfix-summary.json`](agent-bugfix-summary.json) | `scripts/tier1-live-bazel-proof.sh` (Act 1) | `collectable_v1` · `high` | Tier 1 Act 1 live `cursor_adapter_v1` bugfix (`agent-bugfix-1`). `bazel_validated: true`, `validation: bazel` — real Bazel, not pytest fallback. |
| [`agent-feature-summary.json`](agent-feature-summary.json) | `scripts/tier1-live-bazel-proof.sh` (Act 2) | `collectable_v1` · `high` | Tier 1 Act 2 feature slice (`agent-feature-compare`). `bazel_validated: true`; shared-module policy retune with live Bazel validation. |

### Two-act live spark — verifiable agent receipts (R2)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`two-act-spark-stub-summary-sample.json`](two-act-spark-stub-summary-sample.json) | `scripts/two-act-spark-proof.sh` (stub CLI) | mixed: `collectable_v1` validation/cache; `simulated_v1` agent leg · `high` | Full two-act mechanics under real Bazel + NativeLink: act1 red **attributed to the hidden target** (`act1-failure-classification.json`), act2 green with warm cache hits (`hit_rate` 0.5), M9 compare exported, prompt-redaction scan gate clean. Agent leg is the deterministic stub — labeled `simulated_v1`/`stub_receipt_v1`, never presented as live. |
| [`two-act-spark-live-blocker-sample.json`](two-act-spark-live-blocker-sample.json) | `scripts/two-act-spark-proof.sh` (live `claude`, unauthenticated host) | `collectable_v1` · `high` | Honest `environment_blocker` when the headless Claude CLI cannot authenticate; the failed invocation's receipt is kept as evidence. Does **not** fake a live run. |
| [`two-act-spark-live-receipt-sample.json`](two-act-spark-live-receipt-sample.json) | `nlfr agent-invoke` (live `claude`, 401) | `collectable_v1` · `high` | Receipt shape of `nlfr.agent_receipt.v1`: CLI name/version, sanitized command (`<prompt:sha256>` placeholder), `prompt_sha256`, honest `api_error` status. Raw prompt is structurally absent. A green live run upgrades this slot with server-resolved model id, session id, usage, and `response_sha256`. |

### LRE substrate and parity ceilings (`collectable_v1`)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`lre-proof-blocker-sample.json`](lre-proof-blocker-sample.json) | `scripts/lre-proof.sh` | `collectable_v1` · `high` | Honest blocker until `demo/nativelink/lre.json5` exists; documents claim ceiling vs fleet dashboards. |
| [`lre-proof-summary-sample.json`](lre-proof-summary-sample.json) | `scripts/lre-proof.sh` (with `lre.json5`) | `collectable_v1` · `medium` | LRE substrate ready: delegates to `local-exec-proof.sh` on ports 50071/50081; `claim_boundary` excludes hermetic Nix `--config=lre` until toolchain wired. |
| [`lre-nix-toolchain-proof-blocker-sample.json`](lre-nix-toolchain-proof-blocker-sample.json) | `scripts/lre-nix-toolchain-proof.sh` (outside `nix develop`) | `collectable_v1` · `high` | Honest blocker until flake LRE `installationScript` generates repo-root `lre.bazelrc`. |
| [`lre-nix-toolchain-proof-summary-sample.json`](lre-nix-toolchain-proof-summary-sample.json) | `scripts/lre-nix-toolchain-proof.sh` (inside `nix develop`) | `collectable_v1` · `medium` | Phase-2 ceiling `lre_bazelrc_generated`: Nix-generated `build:lre` flags; optional `--config=lre` build on x86_64-linux; does **not** claim cache parity. |
| [`lre-cold-warm-proof-blocker-sample.json`](lre-cold-warm-proof-blocker-sample.json) | `scripts/lre-cold-warm-proof.sh` (Darwin or outside `nix develop`) | `collectable_v1` · `high` | Honest blocker until x86_64-linux `nix develop` with generated `lre.bazelrc`; Darwin gets rust-only LRE env without full cold/warm parity path. |
| [`lre-cold-warm-proof-linux-manual-sample.json`](lre-cold-warm-proof-linux-manual-sample.json) | `scripts/lre-cold-warm-proof.sh` (manual x86_64-linux path; Darwin blocker recorded 2026-06-06) | `collectable_v1` · `high` | Manual Linux proof slot: cites honest `environment_blocker` until operator promotes green `summary.json` from [`LRE_LINUX_PROOF.md`](../LRE_LINUX_PROOF.md); does **not** fabricate parity metrics. |
| [`lre-cold-warm-proof-summary-sample.json`](lre-cold-warm-proof-summary-sample.json) | `scripts/lre-cold-warm-proof.sh` (x86_64-linux `nix develop`) | `collectable_v1` · `medium` | Phase-4 ceiling `lre_cache_parity_observed`: LRE cold/warm via `lre.json5` + `--config=lre` + `local-exec`; cold `hit_rate` 0 → warm `hit_rate` 1; does **not** claim hermetic container-image parity. |

### Research and policy (`derived_v1`)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`fleet-claims-matrix-sample.json`](fleet-claims-matrix-sample.json) | `scripts/fleet-claims-audit.sh` | `derived_v1` · `high` | v1 fleet claim matrix: `worker_identity` is **conditional** (M7); scheduler, queue time, placement, and load distribution remain `out_of_scope`. |
| [`compare-summary.json`](compare-summary.json) | `scripts/compare-proof.sh` | `derived_v1` · `medium` | M9 compare of `record-proof` vs `canvas-dev`: five dimension ids (`run_counts`, `cache_metrics`, `worker_identity`, `agent_provenance`, `status_deltas`). Does **not** claim cross-run worker correlation or scheduler assignment. Projection excerpt: [`compare-projection-sample.json`](compare-projection-sample.json). |

## M7 conditional `worker_identity`

`worker_identity` is promoted only when **all** of the following hold:

1. `nativelink.stdout.txt` is in `artifact_root` before ingest (fleet-evidence-v1
   attach on local-exec and worker-evidence paths).
2. Admin lines match the M7 parser (`src/nlfr/ingest/worker_admin_stdout.py`).
3. The proof script or fixture documents the match (`worker_identity_observed:
   true` in `data/worker-evidence-proof/summary.json` when run).

[`two-worker-summary.json`](two-worker-summary.json) lists `worker_identity` under
`unsupported_claims` because this particular excerpt has no promoted identity rows.
That is honest — endpoint readiness ≠ worker identity.

Proof path: `NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh`
(fixture replay) or live chain via `local-exec-proof.sh`.

## Reading truth labels

Every projected node, edge, metric, and proof claim carries four fields (see
[`AGENTS.md`](../../AGENTS.md)):

| Field | Values |
|-------|--------|
| `source_kind` | `collectable_v1`, `derived_v1`, `simulated_v1`, `future` |
| `confidence` | `high`, `medium`, `low`, `unknown` |
| `evidence_refs` | artifact paths or script ids |
| `redaction_state` | `safe`, `redacted`, `blocked`, `unknown` |

**Cold/warm and two-worker legs** are fully `collectable_v1`.

**Agent-loop chain:** validation/cache leg is `collectable_v1` (ingested Bazel
evidence); `agent` and `change` nodes are `simulated_v1` (deterministic patch, no
live LLM). Top-level `source_kind: collectable_v1` on the summary refers to the
proven validation chain, not the agent's reasoning. The scenario names the agent
`demo-bounded-llm-worker` historically — that label does not claim NativeLink
worker identity.

**M8 agent-live samples** (`agent-live-blocker-sample.json`,
`agent-live-summary-sample.json`) document the live adapter wrapper. The blocker
is honest when Cursor CLI is absent. The summary excerpt is fixture-backed
`collectable_v1` with `cursor_adapter_v1` — pytest validation, not Bazel.

**Tier 1 agent samples** (`agent-bugfix-summary.json`, `agent-feature-summary.json`)
are fully `collectable_v1` with `bazel_validated: true` from
`scripts/tier1-live-bazel-proof.sh` with live `cursor_adapter_v1` records.

**M9 compare** outputs `derived_v1` projections — dimension deltas across run
groups, not new backend observations.

**LRE Linux manual sample** (`lre-cold-warm-proof-linux-manual-sample.json`)
documents the operator-owned phase-4 path until CI promotion lands. On Darwin it
records an honest `environment_blocker` — cite it instead of fabricating
`lre_cache_parity_observed` metrics. After a green x86_64-linux
`nix develop` run, promote redacted output to
[`lre-cold-warm-proof-summary-sample.json`](lre-cold-warm-proof-summary-sample.json)
per [`LRE_LINUX_PROOF.md`](../LRE_LINUX_PROOF.md).

## Regenerate originals

Full summaries live under gitignored `data/`. Regenerate inside `nix develop`:

```bash
./scripts/cold-warm-cache-proof.sh
./scripts/local-exec-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w ./scripts/local-exec-proof.sh
./scripts/agent-loop-proof.sh
./scripts/agent-live-proof.sh --dry-run
./scripts/record-agent-change.sh --dry-run --change-path adapters/cursor/README.md --model composer-2.5 --prompt-file demo/scenarios/tier1/fixtures/prompt-meta.txt
NLFR_RUN_AGENT_LIVE=1 ./scripts/agent-live-proof.sh   # live; requires Cursor CLI
NLFR_SPARK_CLAUDE_BIN=$PWD/scripts/spark-stub-claude.sh NLFR_TWO_ACT_OUTPUT=$PWD/data/two-act-spark-stub NLFR_SPARK_RUN_GROUP_PREFIX=two-act-spark-stub ./scripts/two-act-spark-proof.sh   # mechanics, stub agent
./scripts/two-act-spark-proof.sh   # two-act live spark; requires authenticated `claude` CLI
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh
./scripts/compare-proof.sh   # M9; requires record-proof + canvas-dev DBs
```

See [`../DEV_ENVIRONMENT.md`](../DEV_ENVIRONMENT.md) and [`../TRYOUT_PACKET.md`](../TRYOUT_PACKET.md).

## Related docs

- Tryout narrative: [`../TRYOUT_PACKET.md`](../TRYOUT_PACKET.md)
- Release and GHA promotion: [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md)
- Artifact → sample matrix: [`CI_PROMOTION_MATRIX.md`](CI_PROMOTION_MATRIX.md)
- One-page claims: [`../ONE_PAGER.md`](../ONE_PAGER.md)
- CI jobs: [`../CI_RECIPE.md`](../CI_RECIPE.md)
