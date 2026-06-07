# Reproducible Dev Environment

**Quadrant:** How-to · **Audience:** operators running real NativeLink proofs.

NLFR uses Nix and an optional devcontainer for the real NativeLink cache,
local remote-executor smoke, worker-evidence (M7), tier1 live Bazel, LRE ladder,
and agent-loop proof paths.

The reason is practical: NativeLink's own docs recommend its Nix shell for
reproducible build-graph work, and that shell provides the pinned tooling stack
including Bazel/Bazelisk and the `nativelink` binary.

Sources:

- NativeLink Develop with Nix: <https://docs.nativelink.com/contribute/nix>
- NativeLink Develop with Bazel: <https://docs.nativelink.com/contribute/bazel>
- NativeLink Basic cache configs: <https://docs.nativelink.com/configuration/basic>

Wiki: [First Nix proof](wiki/tutorial/first-nix-proof.md) · [Proof scripts matrix](wiki/reference/proof-scripts-matrix.md) (when landed)

## Prerequisites

- Nix with flakes enabled (Determinate installer recommended).
- ~82GB free disk for the first `nix develop` fetch and Bazel proof runs.
- First cold/warm + local-exec proof may take 30+ minutes depending on network.

Outside Nix, use the fixture canvas path in README Path A (~5 minutes, no real
NativeLink proof).

**GHA offline:** CI may be non-green. Local gates substitute per
[GHA offline proof shift](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Nix — core proof stack

Install Nix with flakes enabled, then:

```bash
nix develop
uv sync
npm --prefix apps/canvas install
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w \
  scripts/local-exec-proof.sh
scripts/worker-evidence-proof.sh
scripts/agent-loop-proof.sh
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
scripts/worker-evidence-proof.sh
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
6. attaches `nativelink.stdout.txt` / `.stderr.txt` to `artifact_root` pre-ingest
   (fleet-evidence-v1);
7. runs `nlfr run --mode local-exec --skip-nativelink` with Bazel
   `--remote_cache` and `--remote_executor`;
8. ingests the run artifact directory;
9. exports graph, runway, and proof projections for `run_group=local-exec`;
10. writes `summary.json`.

This is a one-process NativeLink smoke path, not a full LRE or multi-machine
worker proof. It proves configuration and artifact capture first.

**Worker identity (M7):** conditional when attached stdout matches the M7 regex
in `worker_admin_stdout.py`. Scheduler assignment, queue timing, action
placement, and load distribution stay unsupported.

To gate a two-worker readiness proof:

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

## Worker evidence proof (M7)

`scripts/worker-evidence-proof.sh` exercises the M7 parser and promotes
`worker_identity` when admin stdout is present.

| Mode | When | Output |
|------|------|--------|
| Fixture replay | Default when `nativelink`/Bazel absent | `data/worker-evidence-proof/summary.json`, `worker_identity_observed: true` |
| Live | After `local-exec-proof.sh` or with tools on PATH | Same; stdout from live NativeLink attach |

```bash
./scripts/worker-evidence-proof.sh
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh
```

Deep dive: [`dags/m7-worker-parser.md`](dags/m7-worker-parser.md) · [Wiki § M7](wiki/README.md#frontier-tracks-pointers)

## Agent-Loop Closure Proof

`scripts/agent-loop-proof.sh`:

1. checks for `nativelink`/`native-link` and Bazel/Bazelisk, else writes a
   truth-labeled `environment-blocker.json` and exits nonzero;
2. starts the cache-only NativeLink server and waits for `127.0.0.1:50051`;
3. simulates the bounded `llm-bounded-patch` scenario into a copied workspace
   (never the source) with `simulate --ingest`, applying the patch, running
   Bazel through the NativeLink cache, and ingesting validation+cache evidence;
4. exports graph, runway, and proof projections for `run_group=agent-loop`;
5. writes `summary.json` with `chain_complete=true` and
   `source_kind: collectable_v1`.

The Action Graph shows `agent → (authored_change) → change → (validated_by) →
run → target → action → cache_event`. The bounded patch carries a `model` label
and a SHA-256 prompt hash only; the raw prompt is never stored or exported.

Agent leg is **`simulated_v1`**. For live adapter proof use M8
`record-agent-change.sh` or `tier1-live-bazel-proof.sh`.

## M8 — Agent adapter

```bash
./scripts/record-agent-change.sh \
  --change-path src/nlfr/commands/generic_run.py \
  --model composer-2.5 \
  --prompt-file /tmp/prompt.txt \
  --command "uv run pytest tests/test_generic_run.py -q --tb=no"
```

See [`adapters/cursor/README.md`](../adapters/cursor/README.md).

## Tier1 live Bazel (Acts 1+2)

Full tier1 agent demo with real Bazel validation:

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

Output: `data/tier1-live-bazel/summary.json`, per-act summaries under
`data/agent-bugfix-1/` and `data/agent-feature-compare/` with
`bazel_validated: true`.

Fixture gate without Bazel:

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
```

Deep dive: [`dags/tier1-live-bazel.md`](dags/tier1-live-bazel.md) · [Wiki § Tier1](wiki/how-to/run-tier1-live-bazel-demo.md)

## M9 — Compare proof

```bash
./scripts/record-proof.sh
./scripts/record-canvas-build.sh
./scripts/compare-proof.sh
```

Or use `nlfr compare export` directly — see [`dags/m9-multi-run-compare.md`](dags/m9-multi-run-compare.md).

## LRE proof ladder

LRE proofs run inside `nix develop`. Phases map to scripts and CI jobs in
[`CI_RECIPE.md`](CI_RECIPE.md).

| Phase | Script | Claim ceiling |
|-------|--------|---------------|
| 1 — substrate | `scripts/lre-proof.sh` | `lre_substrate_ready` |
| 2 — Nix toolchain | `scripts/lre-nix-toolchain-proof.sh` | `lre_bazelrc_generated` |
| 4 — cold/warm parity | `scripts/lre-cold-warm-proof.sh` | `lre_cache_parity_observed` (x86_64-linux) |

```bash
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh
uv run pytest tests/test_lre_proof.py -q
```

Without toolchain or on Darwin, scripts write `environment-blocker.json` —
samples in [`proof-samples/`](proof-samples/). Do not claim LRE cache parity
from CI while GHA is offline unless you have a local green `summary.json`.

Deep dive: [`dags/lre-proof.md`](dags/lre-proof.md) · [Wiki § LRE](wiki/README.md#frontier-tracks-pointers)

**Unsupported:** hermetic container-image parity across worker images, fleet
dashboards, queue/action correlation.

## Windows Gaming PC / WSL2 Option

For the later multi-machine worker proof, use the Windows PC as a Linux-like
worker host rather than as a token-heavy LLM runner:

1. Install WSL2 with an Ubuntu distribution.
2. Clone or mount this repo inside WSL2.
3. Use Nix or the devcontainer tooling to install Bazel/Bazelisk and NativeLink.
4. Run `scripts/local-exec-proof.sh` and `scripts/worker-evidence-proof.sh`
   locally in WSL2 first.
5. Only after local proof works, try a LAN worker setup with scheduler/cache on
   another machine and a worker pointed at the private worker API.

Until NLFR captures direct scheduling evidence, claims about which physical
machine executed an action beyond M7 stdout identity stay `future` or unsupported.
