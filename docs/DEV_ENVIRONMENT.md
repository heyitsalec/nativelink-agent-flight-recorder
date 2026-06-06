# Reproducible Dev Environment

NLFR uses Nix and an optional devcontainer for the real NativeLink cache and
local remote-executor smoke proof paths.

The reason is practical: NativeLink's own docs recommend its Nix shell for
reproducible build-graph work, and that shell provides the pinned tooling stack
including Bazel/Bazelisk and the `nativelink` binary.

Sources:

- NativeLink Develop with Nix: <https://docs.nativelink.com/contribute/nix>
- NativeLink Develop with Bazel: <https://docs.nativelink.com/contribute/bazel>
- NativeLink Basic cache configs: <https://docs.nativelink.com/configuration/basic>

## Prerequisites

- Nix with flakes enabled (Determinate installer recommended).
- ~82GB free disk for the first `nix develop` fetch and Bazel proof runs.
- First cold/warm + local-exec proof may take 30+ minutes depending on network.

Outside Nix, use the fixture canvas path in README Path A (~5 minutes, no real
NativeLink proof).

## Nix

Install Nix with flakes enabled, then:

```bash
nix develop
uv sync
npm --prefix apps/canvas install
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
```

The shell provides:

- `nativelink`
- `bazel` shimmed to Bazelisk
- `bazelisk`
- `uv`
- Python 3.13
- Node 22

It also sets:

- `NLFR_NATIVELINK_BIN`
- `NLFR_BAZEL_BIN`
- `PYTHONPATH=src`
- `BAZELISK_HOME=.cache/bazelisk`

## Devcontainer

Open the repo in a devcontainer-compatible editor. The devcontainer installs
Nix, enters `nix develop`, then runs:

```bash
uv sync
npm --prefix apps/canvas install
```

After the container is ready:

```bash
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
```

## Cold/Warm Proof

`scripts/cold-warm-cache-proof.sh`:

1. clears the local NativeLink filesystem cache;
2. starts `nativelink demo/nativelink/cache-only.json`;
3. waits for `127.0.0.1:50051`;
4. runs a cold Bazel test through `nlfr run --skip-nativelink`;
5. runs a warm Bazel test through the same NativeLink cache with a separate
   Bazel output base;
6. exports graph, runway, and proof projections for `run_group=cold-warm`;
7. writes `summary.json`.

Separate Bazel output bases are intentional. They reduce the chance that the
warm run is explained only by local Bazel state instead of the NativeLink cache.

If Bazel or NativeLink is unavailable, the script writes an
`environment-blocker.json` with truth labels and exits nonzero.

## Local Execution Smoke Proof

`scripts/local-exec-proof.sh`:

1. checks for `nativelink`/`native-link` and Bazel/Bazelisk;
2. writes preflight worker/config evidence to `worker-readiness.json`;
3. starts `nativelink demo/nativelink/local-execution.json5`;
4. waits for the public endpoint on `127.0.0.1:50051` and worker API endpoint
   on `127.0.0.1:50061`;
5. updates `worker-readiness.json` when endpoints open;
6. runs `nlfr run --mode local-exec --skip-nativelink` with Bazel
   `--remote_cache` and `--remote_executor`;
7. ingests the run artifact directory;
8. exports graph, runway, and proof projections for `run_group=local-exec`;
9. writes `summary.json`.

This is a one-process NativeLink smoke path, not a full LRE or multi-machine
worker proof. It proves configuration and artifact capture first. Exact worker
identity, queue timing, and scheduler assignment stay unsupported until NLFR
captures direct worker evidence.

To gate a future two-worker proof, provide a config with at least two workers and
set:

```bash
NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh
```

With the current one-worker config, this should stop with
`worker-readiness.json` status `configuration_blocker`.

When a generated NativeLink LRE Bazel config and toolchain exist on a supported
Linux/x86_64-style environment, pass extra Bazel test flags through either the
CLI:

```bash
nlfr run --mode local-exec \
  --bazel-arg=--config=lre \
  --bazel-arg=--remote_default_exec_properties=cpu_count=1 \
  //tasks:priority_test
```

or the proof script:

```bash
NLFR_BAZEL_ARGS="--config=lre --remote_default_exec_properties=cpu_count=1" \
  scripts/local-exec-proof.sh
```

`NLFR_BAZEL_ARGS` is intentionally simple whitespace splitting for ordinary
flag tokens; use the CLI form when a future flag needs complex quoting.

This path is expected to work best inside the Nix shell, devcontainer, a Linux
VM, or WSL2. On a plain macOS host without the pinned NativeLink/Bazel tooling,
the expected result is a truth-labeled `environment-blocker.json`.

## Windows Gaming PC / WSL2 Option

For the later multi-machine worker proof, use the Windows PC as a Linux-like
worker host rather than as a token-heavy LLM runner:

1. Install WSL2 with an Ubuntu distribution.
2. Clone or mount this repo inside WSL2.
3. Use Nix or the devcontainer tooling to install Bazel/Bazelisk and NativeLink.
4. Run `scripts/local-exec-proof.sh` locally in WSL2 first.
5. Only after local proof works, try a LAN worker setup with scheduler/cache on
   another machine and a worker pointed at the private worker API.

Until NLFR captures direct worker identity or scheduling evidence, claims about
which physical machine executed an action stay `future` or unsupported.
