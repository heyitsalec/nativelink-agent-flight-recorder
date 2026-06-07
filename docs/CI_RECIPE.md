# CI recipe (M5+)

**Quadrant:** How-to · **Audience:** skeptics reproducing proofs on Linux/x86_64 and operators when GitHub Actions is offline.

How NLFR proofs are declared in GitHub Actions and how to substitute locally when workflows are non-green.

## GHA offline policy

As of 2026-06-06, `nlfr-proof.yml` has been **effectively offline / non-green** for ~1 month. **Do not block** ship, merge, or doc review on CI green.

Parent/local proof gates while Actions recover:

```bash
uv run pytest -q
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth   # when canvas touched
```

Optional when Nix is available:

```bash
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

Handoff: [GHA offline proof shift](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md) · [Wiki hub § GHA offline](wiki/README.md#gha-offline)

## Workflow file

[`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml) — workflow name **`NLFR proof`**, **seven parallel jobs** (expanded from M5's original three).

Triggers: `push` to `main`, `codex/**`, `fix/**`; all `pull_request`; `workflow_dispatch`.

## Full job matrix

| Job ID | Display name | Host | Timeout | What it runs | Artifact | `source_kind` / claim boundary |
|--------|--------------|------|---------|--------------|----------|-------------------------------|
| `unit` | Unit + generic record + canvas build | `ubuntu-latest` | 20m | `pytest`, `doctor`, tier1 dry-runs, `record-proof.sh`, `record-canvas-build.sh`, canvas `build` + `test:truth` | `record-proof` | Generic record `collectable_v1`; canvas-dev dogfood; compare dry-runs only |
| `linux-nix-toolchain` | Nix toolchain proofs | `ubuntu-latest` + Nix | 90m | `cold-warm-cache-proof.sh`, `agent-loop-proof.sh` | `nix-toolchain-proof` | Cache economics + agent-loop chain `collectable_v1`; agent leg may stay `simulated_v1` |
| `tier1-bazel` | Tier1 Bazel validation (Nix) | `ubuntu-latest` + Nix | 45m | `tier1-bazel-ci-proof.sh` | `tier1-bazel-ci` | Act 1+2 Bazel validation `collectable_v1`; no LRE/worker placement |
| `lre-proof-probe` | LRE substrate proof | `ubuntu-latest` + Nix | 30m | `lre-proof.sh` | `lre-proof-probe` | `lre_substrate_ready` or honest `environment-blocker.json` |
| `lre-nix-ci` | LRE Nix toolchain proof | `ubuntu-latest` + Nix | 45m | `lre-nix-toolchain-proof.sh` | `lre-nix-toolchain-proof` | `lre_bazelrc_generated` or blocker; no cache parity claim |
| `lre-cold-warm-ci` | LRE cold/warm cache parity proof | `ubuntu-latest` + Nix | 60m | `lre-cold-warm-proof.sh` | `lre-cold-warm-proof` | `lre_cache_parity_observed` on x86_64-linux or blocker |
| `verify-demo-fixture` | Fixture demo path | `ubuntu-latest` | 20m | `verify-demo.sh` | `demo-proof` | Fixture ingest + `simulated_v1` demo projections |

**Not CI-gated today:** M7 `worker-evidence-proof.sh`, M9 `compare-proof.sh` full cross-DB compare (covered by `unit` dry-runs + local pytest). Promote proof samples from CI only after a sustained green run — until then use author-Nix or fixture samples in [`proof-samples/`](proof-samples/).

## Local substitutes (by job)

| CI job | Local substitute | Notes |
|--------|------------------|-------|
| `unit` | `uv run pytest -q && ./scripts/record-proof.sh && ./scripts/record-canvas-build.sh && npm --prefix apps/canvas run build && npm --prefix apps/canvas run test:truth` | Matches unit spine |
| `linux-nix-toolchain` | `nix develop --command bash -lc './scripts/cold-warm-cache-proof.sh && ./scripts/agent-loop-proof.sh'` | Darwin may record blockers — honest |
| `tier1-bazel` | `nix develop --command ./scripts/tier1-bazel-ci-proof.sh` or `./scripts/tier1-live-bazel-proof.sh` for full acts 1+2 |
| `lre-proof-probe` | `nix develop --command ./scripts/lre-proof.sh` | Phase 1 substrate |
| `lre-nix-ci` | `nix develop --command ./scripts/lre-nix-toolchain-proof.sh` | Phase 2 `lre.bazelrc` |
| `lre-cold-warm-ci` | `nix develop --command ./scripts/lre-cold-warm-proof.sh` | Phase 4 parity — best on x86_64-linux |
| `verify-demo-fixture` | `./scripts/verify-demo.sh` | No Nix required |

Cross-cutting local gates (all jobs):

```bash
uv run pytest -q
bash -n scripts/*.sh
```

M7 worker evidence (local, not a dedicated CI job):

```bash
./scripts/worker-evidence-proof.sh
# fixture replay default; live when nativelink+bazel in nix develop
```

M9 compare (local):

```bash
./scripts/compare-proof.sh
# or: nlfr compare export --left-db ... --right-db ...
uv run pytest tests/test_compare.py -q
```

## Local reproduction (Linux, full stack)

```bash
# Fast path (no Nix) — mirrors unit + verify-demo-fixture spine
pip install uv
uv sync
uv run pytest -q
./scripts/record-proof.sh
./scripts/verify-demo.sh

# Full toolchain (inside repo)
nix develop --command bash -lc '
  uv sync
  ./scripts/cold-warm-cache-proof.sh
  ./scripts/agent-loop-proof.sh
  ./scripts/worker-evidence-proof.sh
  ./scripts/tier1-bazel-ci-proof.sh
  ./scripts/lre-proof.sh
  ./scripts/lre-nix-toolchain-proof.sh
  ./scripts/lre-cold-warm-proof.sh
'
```

## Artifacts (upload paths)

| Artifact | Key files |
|----------|-----------|
| `record-proof` | `data/record-proof/summary.json`, `run.json`, `projections/` |
| `nix-toolchain-proof` | `data/cold-warm-proof/summary.json` or `environment-blocker.json`; `data/agent-loop-proof/summary.json` or blocker |
| `tier1-bazel-ci` | `data/tier1-bazel-ci/summary.json` or blocker |
| `lre-proof-probe` | `data/lre-proof/summary.json`, `probe.json`, or blocker |
| `lre-nix-toolchain-proof` | `data/lre-nix-toolchain-proof/summary.json` or blocker |
| `lre-cold-warm-proof` | `data/lre-cold-warm-proof/summary.json` or blocker, `projections/` |
| `demo-proof` | `data/demo-proof/summary.json`, `projections/` |

If NativeLink/Bazel/LRE toolchain is unavailable, scripts write `environment-blocker.json` with `collectable_v1` status — never fake success.

## Redaction for committed samples

After a green CI run, redact absolute paths and copy summaries to [`proof-samples/`](proof-samples/) per [`proof-samples/README.md`](proof-samples/README.md). While GHA is offline, committed samples come from author-Nix or fixture/blocker paths — cite the sample table, not CI success.

## Honesty gates

- Do not claim CI passed if only `unit` ran green while Nix jobs recorded `environment_blocker`.
- Do not claim `worker_identity` from CI unless M7 stdout was attached in that proof path (worker-evidence is local today).
- Do not claim `lre_cache_parity_observed` from Darwin or without `lre-cold-warm-proof/summary.json` with parity metrics.
- Do not claim M9 compare from tier1 dry-runs alone — run `compare export` or `compare-proof.sh`.
- Document which job or local script produced which claim in [`ADOPTION_GUIDE.md`](ADOPTION_GUIDE.md).

See also: [`dags/m5-ci-proof.md`](dags/m5-ci-proof.md) · [Wiki hub](wiki/README.md)
