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

### GHA offline (current default)

GitHub Actions workflows may be non-green. **Local gates above substitute for CI**
until `nlfr-proof.yml` runs green again. Do not claim CI passed or block release
on workflow badges while offline.

Policy handoff:
[`sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md`](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

Merge / tag when local checklist passes, review packet is posted, and human
review completes — **not** when CI is green.

## Tag message template (`v0.2.0-mvp`)

```
NLFR MVP tryout kit — v0.2.0-mvp

- Cold/warm cache proof (nix develop; cold vs warm hit_rate/duration deltas)
- Local-exec smoke + live two-worker endpoint readiness (worker_endpoints_ready)
- M7 conditional worker_identity when admin stdout matches (worker-evidence-proof)
- M8 agent adapter: hashed prompt provenance; agent-loop closure (simulated_v1 agent leg)
- M9 multi-run compare projection (derived_v1; compare-proof.sh)
- Tier 1 live Bazel acts 1+2 (cursor_adapter_v1; bazel_validated)
- Truth-labeled Action Graph + Proof Packet + Compare canvas
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

**Provenance note:** committed samples today are from author Nix runs. Linux CI
promotion is the credibility upgrade when GHA returns (runbook below).

## GHA offline → promotion runbook

Use this when GitHub Actions recovers and `nlfr-proof.yml` produces green
artifacts. Until then, skip promotion and cite local proof + existing samples.

### 1. Confirm CI green

- Workflow: [`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml)
- Jobs to watch: `unit`, `linux-nix-toolchain`, `tier1-bazel`, `verify-demo-fixture`
- Download workflow artifacts (e.g. `linux-nix-toolchain-proof`, `tier1-bazel-ci`)

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

| CI / local source | Committed sample |
|-------------------|------------------|
| `data/cold-warm-proof/summary.json` | `docs/proof-samples/cold-warm-summary.json` |
| `data/local-exec-proof-2w/summary.json` | `docs/proof-samples/two-worker-summary.json` |
| `data/agent-loop-proof/summary.json` | `docs/proof-samples/agent-loop-summary.json` |
| `data/tier1-live-bazel/summary.json` (Acts 1+2 slices) | `agent-bugfix-summary.json`, `agent-feature-summary.json` |
| `data/worker-evidence-proof/summary.json` | *(optional new sample — document in README)* |
| `data/lre-proof/summary.json` or blocker | `lre-proof-*-sample.json` |
| `data/lre-cold-warm-proof/summary.json` or blocker | `lre-cold-warm-proof-*-sample.json` |

M9 compare (`data/compare-proof/summary.json`) has no committed sample yet —
add one only if release notes need a stable `derived_v1` excerpt.

### 4. Update docs

1. Refresh [`proof-samples/README.md`](proof-samples/README.md) table rows if
   metrics or claim boundaries changed.
2. Update [`TRYOUT_PACKET.md`](TRYOUT_PACKET.md) proof table if numbers shift.
3. Update [`ONE_PAGER.md`](ONE_PAGER.md) proven bullets if CI numbers differ from
   author Nix.
4. Check [`m5-ci-proof.md`](dags/m5-ci-proof.md) promotion checkbox.
5. Revise
   [`gha-offline-proof-shift.md`](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md)
   — note GHA restored and CI is a gate again.

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

When GHA is offline, [`CI_RECIPE.md`](CI_RECIPE.md) documents the same scripts
as local substitutes — never imply CI green without a passing workflow run.
