# How-to: adopt an existing Bazel monorepo

**Quadrant:** How-to · **Audience:** teams wiring NLFR into a repo that already uses Bazel  
**Milestone:** Wave 11 — adoption init path

Point NLFR at your Bazel workspace, scaffold local recorder metadata once, and
record a single target without copying the full NLFR proof kit layout.

← [Wiki hub](../README.md) · [Adoption guide](../../ADOPTION_GUIDE.md) · [CLI reference](../reference/cli.md)

## Prerequisites

- Python 3.11+ and `uv` (or `pip install` the package in editable mode)
- A Bazel workspace root (contains `WORKSPACE`, `WORKSPACE.bazel`, or `MODULE.bazel`)
- Optional for live cache proof: NativeLink + Bazel on `PATH` (`nlfr doctor` reports blockers honestly)

NLFR v1 does **not** migrate your monorepo. This guide documents an **adapter pattern**:
keep your repo layout; add `nlfr.toml`, a local `data/` tree, and thin wrapper scripts.

## 1. Initialize recorder metadata

From your repository root (the directory that will hold `nlfr.toml`):

```bash
uv sync   # or pip install -e . when NLFR is vendored/submoduled
uv run python -m nlfr init \
  --workspace path/to/bazel/workspace \
  --output-dir data/nlfr \
  --run-group adopted
```

What `nlfr init` creates (idempotent — safe to re-run):

| Path | Purpose |
|------|---------|
| `nlfr.toml` | Defaults: Bazel workspace, SQLite path, run-group |
| `data/.nlfr/init.json` | Init marker + resolved defaults |
| `data/nlfr/` | Output directory for SQLite and run artifacts |

Example `nlfr.toml`:

```toml
[nlfr]
version = 1

[nlfr.defaults]
workspace = "path/to/bazel/workspace"
output_dir = "data/nlfr"
database = "data/nlfr/nlfr.sqlite"
run_group = "adopted"
```

Commit or gitignore `nlfr.toml` and `data/` per your team's policy (`data/` is gitignored in the NLFR reference repo).

## 2. Check the toolchain

```bash
uv run python -m nlfr doctor --mode cache-only --json
```

When Bazel or NativeLink are missing, `doctor` returns a non-zero exit with an
honest blocker — not a silent success. Fix the environment (Nix shell, devcontainer,
or host install) before expecting `collectable_v1` cache proof.

For `--mode local-exec`, `doctor` checks **your** NativeLink config, not a bundled
fixture. The config path is resolved by precedence and echoed as
`nativelink_config_checked` in the JSON output:

1. `--nativelink-config PATH` flag;
2. `nativelink_config` under `[nlfr.defaults]` in your workspace `nlfr.toml`;
3. the bundled demo config **only** when run inside the NLFR source checkout.

Outside the source checkout with no flag and no `nlfr.toml` entry, the check fails
honestly and names what to pass — it never silently validates the demo config.

## 3. Record one target

### Reference repo one-command path

Inside the NLFR reference repository:

```bash
./scripts/record-this-target.sh
# or
./scripts/record-this-target.sh //tasks:priority_test
```

The script runs `nlfr init` then `nlfr run` in `cache-only` mode against
`demo/bazel-monorepo`.

### Adapter script in your monorepo

Copy the pattern from `scripts/record-this-target.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-//your/pkg:smoke_test}"

uv run python -m nlfr init --workspace services --run-group adopted
uv run python -m nlfr run \
  --mode cache-only \
  --scenario adopted-smoke \
  --run-group adopted \
  --workspace "$ROOT/services" \
  --output-dir "$ROOT/data/nlfr" \
  --target "$TARGET" \
  --json
```

Override defaults with environment variables when needed:

| Variable | Default (reference repo) |
|----------|--------------------------|
| `NLFR_WORKSPACE` | `demo/bazel-monorepo` |
| `NLFR_OUTPUT_DIR` | `data/nlfr` |
| `NLFR_RUN_GROUP` | `latest` |
| `NLFR_MODE` | `cache-only` |

### Workspace and remote-cache defaults

- **Always pass `--workspace`** for your own repo (the examples above do). If you
  omit it, `nlfr run` resolves the workspace from the current directory: it uses
  the bundled demo workspace **only** inside the NLFR source checkout (with a
  stderr notice), else the cwd when it holds a Bazel marker
  (`MODULE.bazel` / `WORKSPACE` / `WORKSPACE.bazel`), else it exits `2` with
  `no Bazel workspace found in <cwd>; pass --workspace PATH`. It never silently
  records the demo fixture from outside the source checkout.
- **Remote cache is preflighted.** When you do not pass `--remote-cache`, NLFR
  TCP-checks the default endpoint (`grpc://127.0.0.1:50051`, override with
  `NLFR_REMOTE_CACHE_DEFAULT`) before invoking Bazel. If nothing is listening it
  fails fast with an actionable message instead of a raw Bazel connection error.
  Pass `--no-remote-cache` to record a plain Bazel run with no cache, or
  `--remote-cache URL` to point at your own endpoint (used as-is, no preflight).

## 4. Export proof and graph

After a successful or blocker-recorded run:

```bash
uv run python -m nlfr graph export \
  --db data/nlfr/nlfr.sqlite \
  --run-group adopted \
  --output data/nlfr/projections/action-graph.json

uv run python -m nlfr proof export \
  --db data/nlfr/nlfr.sqlite \
  --run-group adopted \
  --output data/nlfr/projections/proof.json
```

Projections are `derived_v1` views of SQLite facts. The canvas renders exported JSON only.

## Adapter pattern checklist

| Step | Claim boundary |
|------|----------------|
| `nlfr init` scaffold | `derived_v1` / `high` — local metadata only |
| `nlfr doctor` | `collectable_v1` when tools are probed on host |
| `nlfr run` with live Bazel | `collectable_v1` when artifacts are captured |
| Full monorepo CI migration | **future** — out of v1 scope |

## What v1 does not do

- Rewrite your `BUILD` files or Bazel modules
- Auto-discover every target in the monorepo
- Require NativeLink for `init` (only for live cache proof)
- Claim scheduler queue time, worker placement, or fleet dashboards

See [Usefulness roadmap](../../USEFULNESS_ROADMAP.md) Gap 1 and
[future fleet claims](../../dags/future-fleet-claims.md).

## Related

- [Adoption guide § Init path](../../ADOPTION_GUIDE.md#init-path-one-command-record)
- [First evidence loop](../tutorial/first-evidence-loop.md)
- [CLI reference](../reference/cli.md)
