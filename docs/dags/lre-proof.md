# LRE proof — broker DAG (cache parity wired)

**Parent:** PER-1058 architecture track Phase 3+  
**Handoffs (current):** `docs/sessions/handoffs/lre-proof/wave-4/`  
**Handoffs (archived):** `docs/sessions/handoffs/lre-proof/wave-3/`

## Objective

Record NativeLink **Local Remote Execution** substrate, Nix toolchain readiness, and observed LRE cold/warm cache economics when `demo/nativelink/lre.json5` exists, `flake.nix` wires TraceMachina LRE, and toolchain is stable on x86_64-linux.

## Current ceiling (honest)

**Claim:** `lre_cache_parity_observed` (`collectable_v1`, `medium`)

Phase 1 (`lre_substrate_ready`) remains valid via `scripts/lre-proof.sh` → `data/lre-proof/summary.json`.

Phase 2 (`lre_bazelrc_generated`) remains valid via `scripts/lre-nix-toolchain-proof.sh` → `data/lre-nix-toolchain-proof/summary.json`.

Phase 4 adds LRE cold/warm cache parity proof: `nix develop` on x86_64-linux runs `scripts/lre-cold-warm-proof.sh`, which starts NativeLink on `lre.json5` endpoints, runs `nlfr run --mode local-exec --bazel-arg=--config=lre` cold/warm legs through `//tasks:priority_test`, ingests evidence, and exports `cache_economics` with cold `hit_rate` 0 → warm `hit_rate` 1. Writes `data/lre-cold-warm-proof/summary.json` with `claim_boundary`.

Without toolchain, wrong platform, or missing deps, scripts write `environment-blocker.json` with `collectable_v1` probe metadata. NLFR does **not** invent LRE claims beyond the boundary.

**Supported today:** LRE substrate config, cache-only, local-exec smoke, two-worker endpoint readiness, Nix-generated `lre.bazelrc`, Bazel consumer wiring, optional `--config=lre` build probe on x86_64-linux, LRE cold/warm cache economics on x86_64-linux via `lre.json5` + `--config=lre`.

**Unsupported:** hermetic container-image parity across distinct worker images, `lre-cc` as parity target, aarch64-darwin full LRE cold/warm green path, fleet dashboards, queue/action correlation.

## Proof commands

```bash
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

## Wave 2 workers (DONE)

| Worker | Deliverable |
|--------|-------------|
| lre-w2-config-readme | `demo/nativelink/lre.json5`, README LRE section |
| lre-w2-proof-script | `scripts/lre-proof.sh`, proof samples |
| lre-w2-tests | `tests/test_lre_proof.py` (substrate tests) |
| lre-w2-ci-probe | CI `lre-proof-probe` → `summary.json` artifact |
| lre-w2-handoffs | Handoff closure + DAG sync |

## Wave 3 workers (DONE)

| Worker | Deliverable |
|--------|-------------|
| lre-nix-research | TraceMachina flake-parts + LRE module integration pattern |
| lre-nix-flake-wire | `flake.nix`, `flake.lock` — `flakeModules.lre`, `installationScript` |
| lre-nix-bazel-wire | `MODULE.bazel`, `.bazelrc` try-import, gitignore for generated `lre.bazelrc` |
| lre-nix-proof | `scripts/lre-nix-toolchain-proof.sh`, extended tests + proof samples |
| lre-nix-ci | CI `lre-nix-ci` → `data/lre-nix-toolchain-proof/` artifacts |
| lre-wave3-handoffs | Handoff closure + DAG ceiling sync |

## Wave 4 workers (DONE)

| Worker | Deliverable |
|--------|-------------|
| lre-parity-research | Gap analysis + implementation blueprint |
| lre-parity-proof-script | `scripts/lre-cold-warm-proof.sh`, proof samples |
| lre-parity-tests | Extended `tests/test_lre_proof.py` cold/warm contract tests |
| lre-parity-ci | CI `lre-cold-warm-ci` → `data/lre-cold-warm-proof/` artifacts |
| lre-parity-handoffs | Handoff closure + DAG ceiling sync |

## Wave 3 KOS — manual Linux proof (DONE)

| Worker | Deliverable |
|--------|-------------|
| W3-LINUX-RUNBOOK | [`docs/LRE_LINUX_PROOF.md`](../LRE_LINUX_PROOF.md) — operator runbook for x86_64-linux `nix develop` |
| W3-SAMPLE-PROMOTE | [`docs/proof-samples/lre-cold-warm-proof-linux-manual-sample.json`](../proof-samples/lre-cold-warm-proof-linux-manual-sample.json) — honest manual-path slot (Darwin blocker until Linux green promoted) |
| W3-LADDER-SYNC | LRE rows in [`future-execution-ladder.md`](future-execution-ladder.md) |

**Manual path (operator-owned, GHA offline):** On x86_64-linux inside `nix develop`, run `./scripts/lre-cold-warm-proof.sh`. Exit `0` → promote redacted `data/lre-cold-warm-proof/summary.json` to `lre-cold-warm-proof-summary-sample.json`. On Darwin, exit `2` → cite `lre-cold-warm-proof-linux-manual-sample.json` or `lre-cold-warm-proof-blocker-sample.json`; do **not** claim `lre_cache_parity_observed` without a green Linux run.

CI artifact promotion (`lre-cold-warm-ci`) remains deferred to wave 4 while GHA is offline.

## Broker rule

Do not spawn implement workers for fleet/scheduler UI. Hermetic container-image parity and fleet correlation remain blocked per `claim_boundary` in proof summaries.
