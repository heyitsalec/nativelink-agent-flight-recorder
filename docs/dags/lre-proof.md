# LRE proof — broker DAG (toolchain wired)

**Parent:** PER-1058 architecture track Phase 3+  
**Handoffs:** `docs/sessions/handoffs/lre-proof/wave-3/`

## Objective

Record NativeLink **Local Remote Execution** substrate and Nix toolchain readiness when `demo/nativelink/lre.json5` exists, `flake.nix` wires TraceMachina LRE, and toolchain is stable.

## Current ceiling (honest)

**Claim:** `lre_bazelrc_generated` (`collectable_v1`, `medium`)

Phase 1 (`lre_substrate_ready`) remains valid via `scripts/lre-proof.sh` → `data/lre-proof/summary.json`.

Phase 2 adds Nix LRE toolchain proof: `nix develop` runs `config.lre.installationScript`, generating repo-root `lre.bazelrc` with `build:lre` flags; `demo/bazel-monorepo` imports it via Bzlmod `@local-remote-execution` (pinned to `flake.lock` nativelink rev) and `.bazelrc` `try-import`. `scripts/lre-nix-toolchain-proof.sh` writes `data/lre-nix-toolchain-proof/summary.json` with `claim_boundary`.

Without toolchain or missing deps, scripts write `environment-blocker.json` with `collectable_v1` probe metadata. NLFR does **not** invent LRE claims beyond the boundary.

**Supported today:** LRE substrate config, cache-only, local-exec smoke, two-worker endpoint readiness, Nix-generated `lre.bazelrc`, Bazel consumer wiring, optional `--config=lre` build probe on x86_64-linux.

**Unsupported:** hermetic local↔remote cache hit parity, `nlfr run --bazel-arg=--config=lre` end-to-end ingest, aarch64-darwin full `lre-cc`, fleet dashboards, queue/action correlation.

## Proof commands

```bash
uv run pytest tests/test_lre_proof.py -q
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
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

## Broker rule

Do not spawn implement workers for fleet/scheduler UI. Cache parity and `nlfr run --config=lre` remain blocked per `claim_boundary` in proof summaries.
