# GitHub Release Hygiene

Tag alignment: **`v0.2.0-mvp`** on `main` (NativeLink 1.3.2 + Bazel 9 proof paths,
M7/M8/M9 milestone spine, Tier 1 live Bazel, LRE substrate samples).

Point evaluators at `main` at tag `v0.2.0-mvp` or later.

## Pre-release checklist

Run locally — do not rely on hardcoded test counts; verify each command exits 0.

### Fast path (no Nix)

```bash
uv run pytest -q
npm --prefix apps/canvas run build
./scripts/record-proof.sh
./scripts/verify-demo.sh
npm --prefix apps/canvas run capture   # preview on :5174
```

### Milestone proofs (fixture or optional live)

```bash
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh   # M7
./scripts/compare-proof.sh   # M9; requires record-proof + canvas-dev DBs
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
```

### Full toolchain (inside `nix develop`)

```bash
nix develop --command bash -lc '
  set -euo pipefail
  uv sync
  ./scripts/cold-warm-cache-proof.sh
  ./scripts/local-exec-proof.sh
  NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w ./scripts/local-exec-proof.sh
  ./scripts/agent-loop-proof.sh
  ./scripts/tier1-live-bazel-proof.sh
'
```

Optional LRE legs (honest blocker or summary — not a ship gate on every host):

```bash
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh   # x86_64-linux Nix only
```

### Verification before the first green CI run

Until `nlfr-proof.yml` produces a sustained green run, the local gates above
are the canonical verification. Do not claim CI passed until workflows actually
pass.

## Tag message template (`v0.2.0-mvp`)

```
NLFR MVP tryout kit — v0.2.0-mvp

- Cold/warm cache proof (nix develop; cold vs warm hit_rate/duration deltas)
- Local-exec smoke + live two-worker endpoint readiness (worker_endpoints_ready)
- M7 conditional worker_identity when admin stdout matches (worker-evidence-proof)
- M8 agent adapter: hashed prompt provenance; agent-loop closure (simulated_v1 agent leg)
- M9 multi-run compare projection (derived_v1; compare-proof.sh)
- Tier 1 live Bazel acts 1+2 (cursor_adapter_v1; bazel_validated)
- Truth-labeled redesigned canvas: five lenses (Graph / Runway / Proof / Remote / Compare), shape+hue glyphs, dark mode, first-class mobile
- Redacted proof samples: docs/proof-samples/
- See docs/TRYOUT_PACKET.md and docs/ONE_PAGER.md
```

## What not to commit

- `data/` proof runs (gitignored)
- `output/playwright/` captures (gitignored)
- Secrets, raw logs, customer data, raw prompts, environment variables

## Redacted proof samples

For release notes, cite sanitized excerpts from `data/*/summary.json` or the
committed hub at [`proof-samples/`](proof-samples/) — not full artifact trees.

Index and honesty boundaries: [`proof-samples/README.md`](proof-samples/README.md).
GHA artifact → sample map: [`proof-samples/CI_PROMOTION_MATRIX.md`](proof-samples/CI_PROMOTION_MATRIX.md).

**Provenance note:** committed samples today are from author Nix runs. Linux CI
promotion is the credibility upgrade when GHA returns (runbook below).

## CI restore → promotion runbook

Use this when GitHub Actions recovers and `nlfr-proof.yml` produces green
artifacts. Until then, skip promotion and cite local proof + existing samples.

### 1. Confirm CI green

- Workflow: [`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml)
- Jobs to watch: all seven in `nlfr-proof.yml` (`unit`, `linux-nix-toolchain`,
  `tier1-bazel`, `lre-proof-probe`, `lre-nix-ci`, `lre-cold-warm-ci`,
  `verify-demo-fixture`)
- Download all seven workflow artifacts (see
  [`proof-samples/CI_PROMOTION_MATRIX.md`](proof-samples/CI_PROMOTION_MATRIX.md))

Do not promote from a run where toolchain jobs wrote only
`environment-blocker.json` unless that blocker is the honest sample you intend
to ship (LRE legs).

### 2. Redact paths

For each `summary.json` to promote:

1. Copy from `data/<proof-name>/summary.json` or CI artifact extract.
2. Replace absolute repo paths with `<repo>`.
3. Replace Nix-store Bazel paths with `<bazel>`.
4. Confirm no secrets, raw prompts, env vars, or full logs remain.
5. Preserve `run_id`, SHA-256 hashes, truth labels, and `evidence_refs`.

### 3. Map artifact → committed sample

**Canonical matrix:** [`proof-samples/CI_PROMOTION_MATRIX.md`](proof-samples/CI_PROMOTION_MATRIX.md)
— maps all seven GHA jobs, artifact bundle paths, and committed sample filenames
(including local-only sources and no-promote rows).

Quick reference (CI jobs with committed targets):

| GHA job | Artifact bundle | Committed sample(s) |
|---------|-----------------|---------------------|
| `linux-nix-toolchain` | `nix-toolchain-proof` | `cold-warm-summary.json`, `agent-loop-summary.json` |
| `tier1-bazel` | `tier1-bazel-ci` | `agent-bugfix-summary.json`, `agent-feature-summary.json` |
| `lre-proof-probe` | `lre-proof-probe` | `lre-proof-*-sample.json` |
| `lre-nix-ci` | `lre-nix-toolchain-proof` | `lre-nix-toolchain-proof-*-sample.json` |
| `lre-cold-warm-ci` | `lre-cold-warm-proof` | `lre-cold-warm-proof-*-sample.json` |

Local-only until a CI leg exists: `two-worker-summary.json`, M7 worker-evidence,
M9 `compare-summary.json`. See the matrix for `unit` / `demo-proof` (no promote).

### 4. Update docs

1. Refresh [`proof-samples/README.md`](proof-samples/README.md) table rows if
   metrics or claim boundaries changed.
2. Update [`TRYOUT_PACKET.md`](TRYOUT_PACKET.md) proof table if numbers shift.
3. Update [`ONE_PAGER.md`](ONE_PAGER.md) proven bullets if CI numbers differ from
   author Nix.
4. Note that GHA is restored and CI is a merge gate again.

### 5. Verify before tag

```bash
uv run pytest -q
bash -n scripts/*.sh
# Spot-check: jq . docs/proof-samples/*.json
```

### 6. Tag and release

```bash
git tag -a v0.2.0-mvp -m "$(cat <<'EOF'
<paste tag message template above>
EOF
)"
git push origin v0.2.0-mvp
```

Create GitHub Release with:

- Link to [`TRYOUT_PACKET.md`](TRYOUT_PACKET.md)
- Link to [`proof-samples/README.md`](proof-samples/README.md)
- Explicit list of **conditional** claims (M7 `worker_identity`)
- Explicit list of **unproven** fleet claims (scheduler, queue, placement, load)

## CI reference

Job matrix and local reproduction: [`CI_RECIPE.md`](CI_RECIPE.md).

[`CI_RECIPE.md`](CI_RECIPE.md) documents the same scripts as local
substitutes — never imply CI green without a passing workflow run.
