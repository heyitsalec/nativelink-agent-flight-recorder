# Adoption guide (M5+)

← [Docs index](INDEX.md) · [Wiki hub](wiki/README.md)

**Quadrant:** How-to · **Audience:** evaluators who are not on the author's Mac.

## Init path (one-command record)

Fastest way to scaffold NLFR in this repo and record a single Bazel target:

```bash
uv sync
./scripts/record-this-target.sh
# optional target override:
./scripts/record-this-target.sh //tasks:priority_test
```

Under the hood:

1. `nlfr init` writes `nlfr.toml` plus `data/.nlfr/init.json` with workspace,
   database (`data/nlfr/nlfr.sqlite`), and run-group (`latest`) defaults.
2. `nlfr run --mode cache-only` records `//tasks:priority_test` against
   `demo/bazel-monorepo` into `data/nlfr/`.

`init` is idempotent — re-running does not clobber an existing `nlfr.toml` unless
you pass `--force`. When Bazel or NativeLink are absent, `run` still records an
`environment_blocker` artifact (honest failure, not a silent skip).

Adopting a **different** Bazel monorepo: [How-to: adopt existing Bazel monorepo](wiki/how-to/adopt-existing-bazel-monorepo.md).

Proof:

```bash
uv run pytest tests/test_init_cmd.py -q
```

## 5-minute path (no Nix, no NativeLink)

```bash
git clone https://github.com/heyitsalec/nativelink-agent-flight-recorder.git
cd nativelink-agent-flight-recorder
pip install uv
uv sync
uv run pytest -q
./scripts/cache-only-ci-gate.sh   # PR-safe doctor JSON + smoke (see CI_RECIPE.md)
./scripts/verify-demo.sh
npm --prefix apps/canvas ci && npm --prefix apps/canvas run build
npm --prefix apps/canvas run preview   # http://127.0.0.1:5174/
```

What you get:

- Fixture-backed `simulated_v1` demo projections under `data/demo-proof/projections/`
- Committed default canvas: **`canvas-dev`** `collectable_v1` dogfood record (not overwritten by `verify-demo.sh`)
- Truth labels on every node; fixture fallback banner if projection fetch fails

What you do **not** get:

- Live NativeLink cache proof
- Live Bazel validation chain (`collectable_v1` cold/warm, tier1 acts)

Optional M9 compare smoke (fixture DBs from `record-proof` + `canvas-dev`):

```bash
./scripts/record-proof.sh
./scripts/record-canvas-build.sh
./scripts/compare-proof.sh
```

See [Export and compare run groups](wiki/how-to/export-and-compare-run-groups.md) (wiki) · DAG mirror: [`dags/m9-multi-run-compare.md`](dags/m9-multi-run-compare.md).

## 30-minute path (Nix, real toolchain)

Requires Nix with flakes enabled (~82GB disk for the first Bazel fetch).

```bash
nix develop
uv sync
./scripts/cold-warm-cache-proof.sh
./scripts/agent-loop-proof.sh
./scripts/worker-evidence-proof.sh
npm --prefix apps/canvas run capture
```

Evidence locations:

- `data/cold-warm-proof/summary.json`
- `data/agent-loop-proof/summary.json`
- `data/worker-evidence-proof/summary.json` — M7 `worker_identity_observed` when stdout regex matches

Tier1 Acts 1+2 with live Bazel (optional):

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

See [`DEV_ENVIRONMENT.md`](DEV_ENVIRONMENT.md), [`TRYOUT_PACKET.md`](TRYOUT_PACKET.md), and [First Nix proof](wiki/tutorial/first-nix-proof.md).

## Skeptic path (CI artifacts)

Local proof gates (`uv run pytest -q`, `./scripts/verify-demo.sh`) are the canonical verification; see the README Status section for current CI state.

**Fast PR gate:** [`scripts/cache-only-ci-gate.sh`](../scripts/cache-only-ci-gate.sh) (or workflow **`NLFR cache-only gate`**) proves the cache-only doctor JSON contract plus pytest smoke — independent of full proof restore. See [Cache-only gate](CI_RECIPE.md#cache-only-gate-pr-safe) in [`CI_RECIPE.md`](CI_RECIPE.md).

When workflows run, workflow **`NLFR proof`** (`.github/workflows/nlfr-proof.yml`) has **seven parallel jobs**. See [`CI_RECIPE.md`](CI_RECIPE.md) for the full matrix.

Quick artifact map:

| Artifact name | Job | Primary claim |
|---------------|-----|---------------|
| `record-proof` | `unit` | Generic record + canvas dogfood (`collectable_v1`) |
| `nix-toolchain-proof` | `linux-nix-toolchain` | Cold/warm + agent-loop cache economics |
| `tier1-bazel-ci` | `tier1-bazel` | Tier1 Act 1+2 Bazel validation |
| `lre-proof-probe` | `lre-proof-probe` | LRE substrate (`lre_substrate_ready`) |
| `lre-nix-toolchain-proof` | `lre-nix-ci` | Nix-generated `lre.bazelrc` |
| `lre-cold-warm-proof` | `lre-cold-warm-ci` | LRE cold/warm cache parity (x86_64-linux) |
| `demo-proof` | `verify-demo-fixture` | Fixture demo path (`simulated_v1` projections) |

1. Open the latest GitHub Actions run for workflow `NLFR proof`.
2. Download the artifact that matches the claim you want to verify.
3. Confirm `summary.json` has the expected `source_kind` and `claim_boundary` (if present).
4. Compare redacted samples in [`proof-samples/`](proof-samples/) with your download (paths redacted).

If a toolchain job failed with `environment-blocker.json`, the honest claim is "CI recorded a blocker" — not "proof passed on Linux."

## Default canvas projection

Committed under `apps/canvas/public/projections/` is a redacted **`canvas-dev`** generic-run projection (`collectable_v1`). It records NLFR building its own GUI — not the Bazel demo fixtures.

`verify-demo.sh` writes **fixture** projections to `data/demo-proof/projections/` only; it does **not** overwrite committed `canvas-dev` files.

Regenerate dogfood locally:

```bash
./scripts/record-canvas-build.sh
```

Walkthrough screenshots in [`images/`](images/) are **fixture-backed** `simulated_v1` renders for teaching the UI shape; the preview default banner should read **canvas-dev collectable_v1**.

## Landed milestones (M7–M9)

| Milestone | What landed | Proof / wiki |
|-----------|-------------|--------------|
| **M7** worker identity | `worker_admin_stdout` parser promotes `worker_identity` when admin stdout is attached and regex matches | `./scripts/worker-evidence-proof.sh` · [Wiki § M7](wiki/README.md#frontier-tracks-pointers) · [`dags/m7-worker-parser.md`](dags/m7-worker-parser.md) |
| **M8** agent adapter | `record-agent-change.sh` + `adapters/cursor/` — `model` + `prompt_sha256` only | [`adapters/cursor/README.md`](../adapters/cursor/README.md) · [`dags/m8-agent-adapter.md`](dags/m8-agent-adapter.md) |
| **M9** compare | `nlfr compare export` + `compare index`, `derived_v1` compare projection, canvas Compare lens | `./scripts/compare-proof.sh` · [Wiki § M9](wiki/how-to/export-and-compare-run-groups.md) · [`dags/m9-multi-run-compare.md`](dags/m9-multi-run-compare.md) |

M9 is **not** a shell stub — use `compare export`, not a placeholder CLI.

## What remains unsupported

Per [`future-fleet-claims.md`](dags/future-fleet-claims.md) and [`ONE_PAGER.md`](ONE_PAGER.md):

| Claim | Status |
|-------|--------|
| `worker_identity` | **Conditional** — `collectable_v1` when M7 stdout attached + regex matches; otherwise `future` |
| `worker_endpoints_ready` | `collectable_v1` when local-exec proof observes endpoints |
| Scheduler assignment, queue time, action placement, load distribution | **Out of scope** — no direct evidence parsers |
| Multi-machine fleet ops dashboards | **Out of scope** |
| Live Cursor→Bazel E2E in every proof script | M8 dry-run + tier1-live-bazel proven; generic agent-loop still `simulated_v1` on agent leg |

LRE ceiling: substrate + Nix toolchain + optional cold/warm parity on x86_64-linux — not hermetic container-image parity. See [`DEV_ENVIRONMENT.md` § LRE](DEV_ENVIRONMENT.md#lre--proof-ladder-substrate--toolchain--cache-parity).

## Questions the MVP answers today

| Question | Answer source |
|----------|---------------|
| What ran? | `nlfr run` + SQLite + projections |
| Did it pass? | `summary.json` status |
| Cache behavior? | cold/warm proof (Nix) |
| What changed? | `changes` table / generic `--change-path` / M8 `record-agent-change.sh` |
| Agent provenance? | M8 adapter (`collectable_v1`) or bounded simulate (`simulated_v1`) |
| Worker identity? | M7 parser when stdout captured — `worker-evidence-proof.sh` |
| Compare two run groups? | M9 `compare export` (`derived_v1`) |
| Real vs simulated? | truth labels on every node |

## Milestone mirror

M5 CI → M6 polish → M7 parser → M8 adapter → M9 compare → LRE phases → fleet-evidence-v1 stdout breadth.

More: [Wiki hub](wiki/README.md)

← [Docs index](INDEX.md)
