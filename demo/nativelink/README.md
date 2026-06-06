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
opened, and that collectable artifacts were captured. It must not claim exact
queue time, worker identity, action placement, load distribution, or fleet
scheduling behavior until those facts are captured directly.

`scripts/local-exec-proof.sh` writes `worker-readiness.json` for this boundary.
For a future two-worker config, run:

```bash
NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh
```

With this one-worker config, that command should stop at
`configuration_blocker`.

Future full-LRE experiments can pass generated Bazel flags through NLFR after
the LRE config/toolchains exist on a supported Linux/x86_64-style environment:

```bash
nlfr run --mode local-exec \
  --bazel-arg=--config=lre \
  --bazel-arg=--remote_default_exec_properties=cpu_count=1 \
  //...
```
