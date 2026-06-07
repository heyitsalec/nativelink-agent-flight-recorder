# Proof samples (redacted)

These are redacted excerpts of the `summary.json` evidence files produced by the
real Nix proof scripts. They let an evaluator read what the recorder captured
**without** running Nix, Bazel, or NativeLink locally.

Each file is a faithful copy of a real run summary with one change: absolute
host paths are replaced with `<repo>` and the Nix store Bazel path with
`<bazel>`. Run IDs and SHA-256 hashes are preserved (they carry no secrets). No
raw prompts, logs, environment variables, or credentials are included.

| Sample | Produced by | Truth label | What it proves |
|--------|-------------|-------------|----------------|
| `cold-warm-summary.json` | `scripts/cold-warm-cache-proof.sh` | `collectable_v1` | Cold run: `hit_rate` 0.0 / 8.17s. Warm run: `hit_rate` 1.0 / 5.48s. Warm is faster and higher hit rate. |
| `two-worker-summary.json` | `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh` | `collectable_v1` | Two workers configured AND endpoints opened live (`worker_endpoints_ready`, `expected_workers=2`). Lists the claims it does **not** make. |
| `agent-loop-summary.json` | `scripts/agent-loop-proof.sh` | mixed: `collectable_v1` validation/cache; `simulated_v1` agent/change | Deterministic bounded-agent patch validates through `agent → change → run → target → action → cache_event` (`chain_complete=true`). Carries a `model` label and `prompt_sha256` only — never the raw prompt; no live LLM call. |
| `agent-bugfix-summary.json` | `scripts/tier1-agent-demo.sh --act 1` | `collectable_v1` | Tier 1 Act 1 live `cursor_adapter_v1` bugfix record (`agent-bugfix-1`). Validation via pytest fallback when Bazel skipped. |
| `agent-feature-summary.json` | `scripts/tier1-agent-demo.sh --act 2` | `collectable_v1` | Tier 1 Act 2 feature slice (`agent-feature-compare`) with shared-module policy retune. |
| `lre-proof-blocker-sample.json` | `scripts/lre-proof.sh` | `collectable_v1` | Honest blocker until `demo/nativelink/lre.json5` exists; documents claim ceiling vs fleet dashboards. |
| `lre-proof-summary-sample.json` | `scripts/lre-proof.sh` (with `demo/nativelink/lre.json5`) | `collectable_v1` (`confidence: medium`) | LRE substrate ready: delegates to `local-exec-proof.sh` on ports 50071/50081; `claim_boundary` excludes hermetic Nix `--config=lre` until toolchain wired. |
| `lre-nix-toolchain-proof-blocker-sample.json` | `scripts/lre-nix-toolchain-proof.sh` (outside `nix develop`) | `collectable_v1` | Honest blocker until flake LRE `installationScript` generates repo-root `lre.bazelrc`. |
| `lre-nix-toolchain-proof-summary-sample.json` | `scripts/lre-nix-toolchain-proof.sh` (inside `nix develop`) | `collectable_v1` (`confidence: medium`) | Phase-2 ceiling `lre_bazelrc_generated`: Nix-generated `build:lre` flags wired into demo monorepo; optional `--config=lre` build on x86_64-linux; does **not** claim cache parity. |

To regenerate the originals (under ignored `data/`), run the scripts above
inside `nix develop`. See [`../DEV_ENVIRONMENT.md`](../DEV_ENVIRONMENT.md).

## Reading the truth labels

- `collectable_v1` — recorded from real tool output.
- The cold/warm and two-worker legs are fully `collectable_v1`.
- In the agent-loop chain the validation/cache leg is `collectable_v1`
  (ingested Bazel evidence); the `agent` and `change` provenance nodes are
  `simulated_v1` because the patch is deterministic (no live LLM call). The
  top-level `source_kind: collectable_v1` on the summary refers to the proven
  validation chain, not to the agent's reasoning. The scenario fixture names the
  agent `demo-bounded-llm-worker` historically; that label does not claim
  NativeLink worker identity.
