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
documented in [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md) — deferred while
GHA is offline per
[`gha-offline-proof-shift.md`](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Milestone map (M7 · M8 · M9 · Tier 1)

| Milestone | What landed | Honesty ceiling |
|-----------|-------------|-----------------|
| **M7** worker parser | `worker_admin_stdout` promotes `worker_identity` when admin stdout is attached pre-ingest **and** lines match the M7 regex | **Conditional** — not global. Runs without captured stdout keep `worker_identity` in `unsupported_claims`. |
| **M8** agent adapter | `record-agent-change.sh` with `model` + `prompt_sha256` only; dry-run and pytest paths proven | Agent leg may be `simulated_v1` (deterministic patch) or `collectable_v1` when live adapter + Bazel validation run. |
| **M9** multi-run compare | `nlfr compare export`, canvas Compare lens, `scripts/compare-proof.sh` | `derived_v1` compare projection — no new collectable fleet claims. No committed compare sample yet; run `compare-proof.sh` locally. |
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

### Agent loop and Tier 1 (`collectable_v1` / mixed)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`agent-loop-summary.json`](agent-loop-summary.json) | `scripts/agent-loop-proof.sh` | mixed: `collectable_v1` validation/cache; `simulated_v1` agent/change · `high` | Deterministic bounded-agent patch validates `agent → change → run → target → action → cache_event` (`chain_complete=true`). `model` + `prompt_sha256` only — never the raw prompt; no live LLM call. |
| [`agent-bugfix-summary.json`](agent-bugfix-summary.json) | `scripts/tier1-live-bazel-proof.sh` (Act 1) | `collectable_v1` · `high` | Tier 1 Act 1 live `cursor_adapter_v1` bugfix (`agent-bugfix-1`). `bazel_validated: true`, `validation: bazel` — real Bazel, not pytest fallback. |
| [`agent-feature-summary.json`](agent-feature-summary.json) | `scripts/tier1-live-bazel-proof.sh` (Act 2) | `collectable_v1` · `high` | Tier 1 Act 2 feature slice (`agent-feature-compare`). `bazel_validated: true`; shared-module policy retune with live Bazel validation. |

### LRE substrate and parity ceilings (`collectable_v1`)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`lre-proof-blocker-sample.json`](lre-proof-blocker-sample.json) | `scripts/lre-proof.sh` | `collectable_v1` · `high` | Honest blocker until `demo/nativelink/lre.json5` exists; documents claim ceiling vs fleet dashboards. |
| [`lre-proof-summary-sample.json`](lre-proof-summary-sample.json) | `scripts/lre-proof.sh` (with `lre.json5`) | `collectable_v1` · `medium` | LRE substrate ready: delegates to `local-exec-proof.sh` on ports 50071/50081; `claim_boundary` excludes hermetic Nix `--config=lre` until toolchain wired. |
| [`lre-nix-toolchain-proof-blocker-sample.json`](lre-nix-toolchain-proof-blocker-sample.json) | `scripts/lre-nix-toolchain-proof.sh` (outside `nix develop`) | `collectable_v1` · `high` | Honest blocker until flake LRE `installationScript` generates repo-root `lre.bazelrc`. |
| [`lre-nix-toolchain-proof-summary-sample.json`](lre-nix-toolchain-proof-summary-sample.json) | `scripts/lre-nix-toolchain-proof.sh` (inside `nix develop`) | `collectable_v1` · `medium` | Phase-2 ceiling `lre_bazelrc_generated`: Nix-generated `build:lre` flags; optional `--config=lre` build on x86_64-linux; does **not** claim cache parity. |
| [`lre-cold-warm-proof-blocker-sample.json`](lre-cold-warm-proof-blocker-sample.json) | `scripts/lre-cold-warm-proof.sh` (Darwin or outside `nix develop`) | `collectable_v1` · `high` | Honest blocker until x86_64-linux `nix develop` with generated `lre.bazelrc`; Darwin gets rust-only LRE env without full cold/warm parity path. |
| [`lre-cold-warm-proof-summary-sample.json`](lre-cold-warm-proof-summary-sample.json) | `scripts/lre-cold-warm-proof.sh` (x86_64-linux `nix develop`) | `collectable_v1` · `medium` | Phase-4 ceiling `lre_cache_parity_observed`: LRE cold/warm via `lre.json5` + `--config=lre` + `local-exec`; cold `hit_rate` 0 → warm `hit_rate` 1; does **not** claim hermetic container-image parity. |

### Research and policy (`derived_v1`)

| Sample | Produced by | `source_kind` · `confidence` | What it proves |
|--------|-------------|-------------------------------|----------------|
| [`fleet-claims-matrix-sample.json`](fleet-claims-matrix-sample.json) | `scripts/fleet-claims-audit.sh` | `derived_v1` · `high` | v1 fleet claim matrix: `worker_identity` is **conditional** (M7); scheduler, queue time, placement, and load distribution remain `out_of_scope`. |

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

**Tier 1 agent samples** (`agent-bugfix-summary.json`, `agent-feature-summary.json`)
are fully `collectable_v1` with `bazel_validated: true` from
`scripts/tier1-live-bazel-proof.sh` with live `cursor_adapter_v1` records.

**M9 compare** outputs `derived_v1` projections — dimension deltas across run
groups, not new backend observations.

## Regenerate originals

Full summaries live under gitignored `data/`. Regenerate inside `nix develop`:

```bash
./scripts/cold-warm-cache-proof.sh
./scripts/local-exec-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w ./scripts/local-exec-proof.sh
./scripts/agent-loop-proof.sh
./scripts/tier1-live-bazel-proof.sh
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh
./scripts/compare-proof.sh   # M9; requires record-proof + canvas-dev DBs
```

See [`../DEV_ENVIRONMENT.md`](../DEV_ENVIRONMENT.md) and [`../TRYOUT_PACKET.md`](../TRYOUT_PACKET.md).

## Related docs

- Tryout narrative: [`../TRYOUT_PACKET.md`](../TRYOUT_PACKET.md)
- Release and GHA promotion: [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md)
- One-page claims: [`../ONE_PAGER.md`](../ONE_PAGER.md)
- CI jobs: [`../CI_RECIPE.md`](../CI_RECIPE.md)
