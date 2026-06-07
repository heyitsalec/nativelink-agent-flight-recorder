# NativeLink Demo Configs

## Cache-Only

`cache-only.json` exposes a loopback gRPC endpoint on `127.0.0.1:50051` with
CAS, action-cache, capabilities, and bytestream services backed by filesystem
stores under `/tmp/nlfr-nativelink/cache-only`.

This is intentionally cache-only. It does not configure a scheduler, worker
API, worker process, or execution service, so runner output must not claim
remote execution, exact worker/action assignment, or queue time.

The matching Bazel runner command points Bazel at the local cache endpoint:

```bash
bazel test //... \
  --remote_cache=grpc://127.0.0.1:50051 \
  --remote_instance_name=main
```

The runner also emits BEP, profile, and execution-log artifacts into the run
artifact directory. If the `nativelink` binary is absent, the NativeLink runner
returns an `environment_blocker` result with `source_kind: collectable_v1` and
`confidence: high`; it does not mark the proof path successful.

## Local Execution Smoke

`local-execution.json5` is the experimental one-process remote-executor smoke
config. It adds:

- a scheduler named `MAIN_SCHEDULER`;
- execution and remote-execution capability services;
- a private worker API on `127.0.0.1:50061`;
- one local worker using filesystem stores under `/tmp/nlfr-nativelink/local-exec`.

The matching Bazel runner command points Bazel at both cache and executor:

```bash
bazel test //... \
  --remote_cache=grpc://127.0.0.1:50051 \
  --remote_executor=grpc://127.0.0.1:50051 \
  --remote_instance_name=main
```

This is for proof-path development, not production deployment or a full
NativeLink LRE setup. NLFR may claim that Bazel was configured for remote
execution, that the config declares one local worker, that smoke endpoints
opened, and that collectable artifacts were captured. Worker identity is
**conditional** (M7): only when NativeLink admin stdout is attached pre-ingest
and the M7 parser matches (`worker_admin_stdout`). Queue time, action placement,
load distribution, and fleet scheduling behavior remain unsupported until those
facts are captured directly.

`scripts/local-exec-proof.sh` writes `worker-readiness.json` for this boundary.
With this one-worker config, requesting two workers stops at
`configuration_blocker`:

```bash
NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh
```

A two-worker config has since been proven live in Nix
(`worker_endpoints_ready`, `expected_workers=2`, `configured_workers=2`,
`collectable_v1`; see `data/local-exec-proof-2w/summary.json`). That proves two
workers configured AND endpoints opened live — not work distributed across two
workers. Worker identity is conditional on M7 admin stdout (see above).
Scheduler assignment, queue time, action placement, and load distribution stay
unsupported.

## LRE Substrate (phase 1)

`lre.json5` is the NLFR **LRE substrate** config: a one-worker remote-executor
smoke stack on dedicated loopback ports (`127.0.0.1:50071` public,
`127.0.0.1:50081` worker API) under `/tmp/nlfr-nativelink/lre`. It mirrors the
local-exec shape (scheduler, execution, capabilities, worker API) but uses
dedicated LRE ports and a single local worker so it does not collide with
`cache-only.json` (`50051`) or `local-execution.json5` (`50061`).

The matching Bazel runner command points Bazel at the LRE public endpoint:

```bash
bazel test //... \
  --remote_cache=grpc://127.0.0.1:50071 \
  --remote_executor=grpc://127.0.0.1:50071 \
  --remote_instance_name=main
```

`scripts/lre-proof.sh` delegates to `local-exec-proof.sh` with this config and
writes `data/lre-proof/summary.json` with `status: lre_substrate_ready`,
`source_kind: collectable_v1`, `confidence: medium`, and honest
`claim_boundary` metadata.

**`claim_boundary` supported:** LRE NativeLink server substrate configured;
remote_executor smoke with `lre.json5` endpoints; `worker_endpoints_ready` for
one local worker.

**`claim_boundary` unsupported until Nix LRE toolchain:** hermetic Nix toolchain
parity across local and remote; generated `lre.bazelrc` / `--config=lre` cache
hit parity; fleet scheduler dashboards; queue time and action placement
correlation.

With this one-worker config, `NLFR_EXPECTED_WORKERS=2` stops at
`configuration_blocker` (same boundary as local-exec smoke).

```bash
nix develop --command ./scripts/lre-proof.sh
```

## Nix LRE toolchain (phase 2 — wiring + probe)

TraceMachina `local-remote-execution` is wired into `flake.nix` (flake-parts +
LRE module) and `demo/bazel-monorepo/MODULE.bazel` (Bzlmod `@local-remote-execution`
at the pinned NativeLink rev). `nix develop` runs the LRE `installationScript`,
which generates repo-root `lre.bazelrc` with `build:lre` flags; the demo monorepo
`.bazelrc` `try-import`s that file.

`scripts/lre-nix-toolchain-proof.sh` writes `data/lre-nix-toolchain-proof/summary.json`
with `status: lre_bazelrc_generated`, `source_kind: collectable_v1`, `confidence: medium`,
and honest `claim_boundary` metadata. On x86_64-linux it may optionally attempt
`bazel build --config=lre @local-remote-execution//examples:lre-cc`; build failure
does not lift the cache-parity ceiling.

**`claim_boundary` supported (phase 2):** Nix devShell generates `lre.bazelrc`;
demo monorepo imports it; `@local-remote-execution` resolves at pinned rev.

**Still unsupported:** hermetic local↔remote cache hit parity; `nlfr run --bazel-arg=--config=lre`
end-to-end ingest; aarch64-darwin full `lre-cc` builds; fleet dashboards; queue/action
correlation.

```bash
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
```

## LRE cold/warm cache parity (phase 4 — observed economics)

`scripts/lre-cold-warm-proof.sh` mirrors the proven `cold-warm-cache-proof.sh` pattern
with LRE-specific deltas: NativeLink on `lre.json5` (ports `50071`/`50081`), Nix-generated
`lre.bazelrc` copied into the demo monorepo, and `nlfr run --mode local-exec --bazel-arg=--config=lre`
cold/warm legs on `//tasks:priority_test`. Evidence is ingested and exported with
`cache_economics` comparing cold `hit_rate` 0 → warm `hit_rate` 1.

Writes `data/lre-cold-warm-proof/summary.json` with `status: lre_cache_parity_observed`,
`source_kind: collectable_v1`, `confidence: medium`, and honest `claim_boundary` metadata.
On Darwin or outside `nix develop`, the script records `environment-blocker.json` instead;
CI job `lre-cold-warm-ci` owns the x86_64-linux green path.

**`claim_boundary` supported (phase 4):** LRE cold/warm cache economics on x86_64-linux via
`lre.json5` + `--config=lre`; `nlfr run --mode local-exec` ingest + proof export with
`cache_economics`; warm `hit_rate` exceeds cold on `//tasks:priority_test` through LRE endpoints.

**Still unsupported:** hermetic container-image parity across distinct worker images;
`lre-cc` C++ LRE builds as parity proof target; aarch64-darwin full LRE cold/warm green path;
fleet dashboards; queue/action correlation.

```bash
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

NLFR runner integration on a supported Linux/x86_64 host:

```bash
nlfr run --mode local-exec \
  --bazel-arg=--config=lre \
  --bazel-arg=--remote_default_exec_properties=cpu_count=1 \
  //...
```
