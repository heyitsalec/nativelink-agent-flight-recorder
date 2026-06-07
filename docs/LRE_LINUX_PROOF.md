# LRE Linux manual proof — operator runbook

**Quadrant:** How-to · **Audience:** operators with an x86_64-linux host (bare metal, VM, or WSL2).

Phase 4 of the LRE proof ladder records **observed LRE cold/warm cache economics** on
x86_64-linux inside `nix develop`. The script is `scripts/lre-cold-warm-proof.sh`; the
claim ceiling is `lre_cache_parity_observed` (`collectable_v1`, `medium`).

While GitHub Actions is offline, this manual path is the supported way to produce a green
`summary.json` or to promote a redacted sample for skeptics who will not run Nix locally.

Related:

- LRE ladder overview: [`DEV_ENVIRONMENT.md` § LRE](DEV_ENVIRONMENT.md#lre-proof-ladder)
- DAG ceiling: [`dags/lre-proof.md`](dags/lre-proof.md)
- Redacted samples: [`proof-samples/README.md`](proof-samples/README.md)
- GHA deferral: [`sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md`](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md)

## What this proves (and does not)

| Supported (`lre_cache_parity_observed`) | Unsupported |
|----------------------------------------|-------------|
| LRE cold/warm cache economics on x86_64-linux via `lre.json5` + `--config=lre` | Hermetic container-image parity across distinct worker images |
| `nlfr run --mode local-exec` ingest + proof export with `cache_economics` | `lre-cc` C++ LRE builds as parity proof target |
| Warm `hit_rate` exceeds cold on `//tasks:priority_test` through LRE endpoints | aarch64-darwin full LRE cold/warm green path |
| | Fleet scheduler dashboards, queue time, action placement correlation |

Do not claim LRE cache parity from CI while GHA is offline unless you have a local green
`summary.json` or cite the redacted sample in [`proof-samples/`](proof-samples/).

## Darwin blocker honesty

On **macOS (Darwin)**, `scripts/lre-cold-warm-proof.sh` exits immediately with exit code
`2` and writes `data/lre-cold-warm-proof/environment-blocker.json`. This is the **expected,
honest outcome** — not a bug.

Darwin hosts get a rust-only LRE Nix environment without the full `lre-cc` cold/warm parity
path. The blocker records:

- `status`: `environment_blocker`
- `source_kind`: `collectable_v1`
- `confidence`: `high`
- `reason`: LRE cold/warm requires x86_64-linux inside `nix develop`

**On a Mac, do not retry until green.** Use one of:

1. Cite [`proof-samples/lre-cold-warm-proof-linux-manual-sample.json`](proof-samples/lre-cold-warm-proof-linux-manual-sample.json) for the operator manual-path slot (Darwin blocker + promotion steps).
2. Cite [`proof-samples/lre-cold-warm-proof-blocker-sample.json`](proof-samples/lre-cold-warm-proof-blocker-sample.json) for the script blocker schema mirror.
3. Cite [`proof-samples/lre-cold-warm-proof-summary-sample.json`](proof-samples/lre-cold-warm-proof-summary-sample.json) for the x86_64-linux green schema (redacted).
4. Run this runbook on a Linux host and attach your own `summary.json`.

Phases 1–2 remain runnable on Darwin inside `nix develop` (`lre-proof.sh`,
`lre-nix-toolchain-proof.sh`). Only phase 4 cold/warm parity is Linux-gated.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Host** | `uname -s` = `Linux`, `uname -m` = `x86_64` |
| **Nix** | Flakes enabled (Determinate installer recommended) |
| **Disk** | ~82GB free for first `nix develop` fetch + Bazel proof runs |
| **Time** | First cold/warm leg may take 30+ minutes depending on network |
| **Repo** | Clone at the commit you intend to prove |

Optional earlier ladder legs (recommended before phase 4):

```bash
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
```

Phase 4 requires a generated repo-root `lre.bazelrc` from the flake LRE
`installationScript` (normally created when entering `nix develop` on Linux).

## Procedure

### 1. Enter the Nix shell

```bash
cd /path/to/nativelink-agent-flight-recorder
nix develop
```

Inside the shell, confirm tooling:

```bash
command -v nativelink
command -v bazel
test -f lre.bazelrc && echo "lre.bazelrc present"
```

If `lre.bazelrc` is missing, you are not inside a Linux `nix develop` session with the
LRE module wired — see [`demo/nativelink/README.md`](../demo/nativelink/README.md) § Nix LRE
toolchain.

### 2. Sync Python and run contract tests

```bash
uv sync
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
```

### 3. Run the cold/warm proof

```bash
./scripts/lre-cold-warm-proof.sh
```

Or from outside the shell (equivalent):

```bash
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

The script:

1. Clears `/tmp/nlfr-nativelink/lre` and prior output under `data/lre-cold-warm-proof/`.
2. Starts NativeLink on `demo/nativelink/lre.json5` (ports `50071` / `50081`).
3. Runs cold then warm Bazel tests via `nlfr run --mode local-exec --bazel-arg=--config=lre`
   on `//tasks:priority_test` with separate Bazel output bases.
4. Ingests evidence, exports graph/runway/proof projections for `run_group=lre-cold-warm`.
5. Writes `data/lre-cold-warm-proof/summary.json`.

### 4. Verify success

Green output:

```bash
jq -r '.status' data/lre-cold-warm-proof/summary.json
# expect: lre_cache_parity_observed
```

Check cache economics:

```bash
jq '.cache_economics.comparison | {cold_hit_rate, warm_hit_rate, warm_hit_rate_higher}' \
  data/lre-cold-warm-proof/summary.json
```

Expected pattern: cold `hit_rate` ≈ `0`, warm `hit_rate` ≈ `1`, `warm_hit_rate_higher`:
`true`.

Artifacts:

| Path | Purpose |
|------|---------|
| `data/lre-cold-warm-proof/summary.json` | Claim boundary + leg summaries |
| `data/lre-cold-warm-proof/cold-run.json`, `warm-run.json` | Per-leg `nlfr run` payloads |
| `data/lre-cold-warm-proof/projections/proof.json` | Proof packet incl. `cache_economics` |
| `data/lre-cold-warm-proof/nativelink.stdout.txt` | NativeLink server log (attach for debug) |

Exit code `0` = green. Exit code `2` = honest environment blocker (wrong host or missing deps).

## Promoting a redacted sample

After a green manual run, operators may promote a redacted excerpt to
`docs/proof-samples/` so evaluators can read the schema without your host paths.

1. Copy `data/lre-cold-warm-proof/summary.json` as the source.
2. Redact absolute paths:
   - Replace the repo root with `<repo>`.
   - Replace the Nix-store Bazel path with `<bazel>`.
3. Preserve run IDs, metrics, truth labels, and `claim_boundary` verbatim.
4. Do **not** include secrets, raw logs, environment variables, or credentials.
5. Write to `docs/proof-samples/lre-cold-warm-proof-summary-sample.json`.
6. Update the row in [`proof-samples/README.md`](proof-samples/README.md) if the schema
   changed.

The committed sample [`lre-cold-warm-proof-summary-sample.json`](proof-samples/lre-cold-warm-proof-summary-sample.json)
is the reference shape. If no Linux host is available, **promote or cite the blocker sample
only** — do not fabricate parity metrics.

```bash
# Darwin honest outcome (no Linux host required):
./scripts/lre-cold-warm-proof.sh
# → data/lre-cold-warm-proof/environment-blocker.json
# Manual-path mirror: docs/proof-samples/lre-cold-warm-proof-linux-manual-sample.json
# Script schema mirror: docs/proof-samples/lre-cold-warm-proof-blocker-sample.json
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NLFR_LRE_COLD_WARM_OUTPUT` | `data/lre-cold-warm-proof` | Output root |
| `NLFR_LRE_BAZELRC` | `$ROOT/lre.bazelrc` | Generated LRE Bazel config |
| `NLFR_LRE_COLD_WARM_TARGET` | `//tasks:priority_test` | Bazel test target |
| `NLFR_REMOTE_CACHE` | `grpc://127.0.0.1:50071` | LRE public endpoint |
| `NLFR_REMOTE_EXECUTOR` | `grpc://127.0.0.1:50071` | LRE executor endpoint |
| `NLFR_CACHE_ROOT` | `/tmp/nlfr-nativelink/lre` | NativeLink filesystem cache |

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Immediate `environment-blocker.json` on Mac | Darwin gate | Expected; use blocker sample or Linux host |
| `lre.bazelrc not found` | Outside `nix develop` on Linux | `nix develop` then retry |
| Ports 50071/50081 timeout | NativeLink failed to start | Read `nativelink.stderr.txt` |
| `missing nativelink` / `missing bazel` | Plain host without Nix shell | `nix develop --command ./scripts/lre-cold-warm-proof.sh` |
| Warm `hit_rate` not higher than cold | Stale cache or shared output base | Re-run script (it clears cache root); confirm separate `bazel-output-cold` / `warm` |

## Proof gates (broker / review packet)

```bash
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
# Operator-owned green (x86_64-linux + Nix only):
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

Attach `data/lre-cold-warm-proof/summary.json` to the review packet when green. When blocked,
attach `environment-blocker.json` or cite
[`lre-cold-warm-proof-blocker-sample.json`](proof-samples/lre-cold-warm-proof-blocker-sample.json).
