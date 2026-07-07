# GHA restore runbook

**Quadrant:** How-to · **Audience:** operators (historical restore procedure; CI restored 2026-07-07) and air-gapped reproducers.

**Status (2026-07-07): RESOLVED — GitHub Actions is live and `main` is green.**
`nlfr-proof.yml` has been green across every completed push run on `main` since
2026-07-07 (e.g. run
[`28878270360`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28878270360)).
This runbook is retained as the **historical restore procedure** and as the
**local-substitute** reference for air-gapped reproduction; the restore trigger
below has already fired.

Committed blocker sample: [`proof-samples/ci-offline-blocker-sample.json`](proof-samples/ci-offline-blocker-sample.json).

---

## When to use this runbook

Trigger when **any** of the following is true:

1. Operator declares GHA restored.
2. First sustained green run on [`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml).

Until then, local gates are the canonical verification — see
[`CI_RECIPE.md`](CI_RECIPE.md#local-verification-policy).

---

## Sustained-green criteria

**Sustained green** on **`NLFR proof`** (`nlfr-proof.yml`) means **all** of:

1. **Seven jobs** on a single workflow run complete without workflow failure (see §1.2).
2. Toolchain jobs that support Linux/x86_64 claims upload **`summary.json`** (not only
   `environment-blocker.json`) where the claim boundary requires success.
3. **≥3 consecutive green runs** on `main` (or the branch under restore verification)
   with no intervening workflow failure — dispatch or qualifying push is fine.
4. At least one green run after any workflow YAML or proof-script change in the restore PR.

**Not sustained green:**

- Local substitutes only (`verify-gha-readiness.sh`, `cache-only-ci-gate.sh`, author Nix).
- A single accidental green run followed by failures.
- Jobs that finished with honest blockers where success was required for the claim
  (e.g. promoting `lre_cache_parity_observed` from blocker-only `lre-cold-warm-ci`).

**Cache-only gate** (`nlfr-cache-only-gate.yml`): one green run is sufficient for that
workflow's PR-safe doctor contract; it does **not** satisfy sustained green for full
`nlfr-proof.yml` or proof-sample promotion.

Detail and operator checklist: [`CI_RECIPE.md`](CI_RECIPE.md#sustained-green-criteria).

---

## GHA offline blocker (wave 10 honest close — superseded 2026-07-07)

_Historical record. Superseded: `main` has been green on hosted runners since
2026-07-07 (see Status banner above). Kept for provenance of the offline period._

| Field | Value |
|-------|-------|
| **Observation** | (historical) GHA was offline ~1 month; no sustained green run was captured **at that time** — resolved 2026-07-07 |
| **Audit status** | readiness audit + local gates only |
| **Truth label** | `collectable_v1` / `high` (negative) |
| **Readiness script** | [`scripts/verify-gha-readiness.sh`](../scripts/verify-gha-readiness.sh) |
| **Blocker sample** | [`proof-samples/ci-offline-blocker-sample.json`](proof-samples/ci-offline-blocker-sample.json) |

**What we do not claim:** CI Linux green, seven-job artifact promotion, CI badge as merge gate.

**Local substitute (run before merge while offline):**

```bash
chmod +x scripts/verify-gha-readiness.sh
./scripts/verify-gha-readiness.sh
# or individually:
./scripts/cache-only-ci-gate.sh
uv run pytest -q
bash -n scripts/*.sh
```

Outputs: `data/verify-gha-readiness/workflow-audit.json`, `summary.json`.

**Revisit trigger:** first run meeting sustained-green criteria above, or operator declares GHA restored.

---

## Phase 1 — Re-run all seven `nlfr-proof.yml` jobs

Workflow name: **`NLFR proof`**. Jobs run **in parallel** (no job-level dependencies).

### 1.1 Dispatch or push trigger

Preferred: **workflow_dispatch** on `main` (or the branch under restore verification).

```text
GitHub → Actions → NLFR proof → Run workflow → branch: main
```

Alternate: push an empty commit or merge to `main` / `codex/**` / `fix/**` (see workflow
`on:` triggers). Avoid canceling an in-flight run via concurrency unless intentional.

### 1.2 Job checklist (all seven must complete)

| # | Job ID | Display name | Artifact name | Pass criterion |
|---|--------|--------------|---------------|----------------|
| 1 | `unit` | Unit + generic record + canvas build | `record-proof` | `pytest`, doctor, tier1 dry-runs, `record-proof.sh`, canvas build + `test:truth` |
| 2 | `linux-nix-toolchain` | Nix toolchain proofs | `nix-toolchain-proof` | `cold-warm-cache-proof.sh` + `agent-loop-proof.sh` → `summary.json` (blocker only if honest env gap) |
| 3 | `tier1-bazel` | Tier1 Bazel validation (Nix) | `tier1-bazel-ci` | `tier1-bazel-ci-proof.sh` → `summary.json` or honest blocker |
| 4 | `lre-proof-probe` | LRE substrate proof | `lre-proof-probe` | `lre-proof.sh` → `summary.json` + `probe.json` or blocker |
| 5 | `lre-nix-ci` | LRE Nix toolchain proof | `lre-nix-toolchain-proof` | `lre-nix-toolchain-proof.sh` → `summary.json` or blocker |
| 6 | `lre-cold-warm-ci` | LRE cold/warm cache parity proof | `lre-cold-warm-proof` | `lre-cold-warm-proof.sh` → `summary.json` (+ `projections/`) or blocker |
| 7 | `verify-demo-fixture` | Fixture demo path | `demo-proof` | `verify-demo.sh` → `summary.json` + `projections/` |

**Sustained green** means: all seven jobs finished without workflow failure, and
toolchain jobs that are meant to prove Linux/x86_64 claims produced **`summary.json`**
(not only `environment-blocker.json`) where the claim boundary requires success.

Honest exception: LRE legs may ship blocker samples when the environment truly lacks
substrate — but do **not** promote blocker JSON as parity success or cite CI green for
`lre_cache_parity_observed` unless job 6 produced parity metrics in `summary.json`.

### 1.3 Download artifacts

From the green workflow run → **Artifacts** section, download each of the seven
artifact bundles. Extract to a scratch directory (never commit raw `data/` trees).

Key files per artifact (see also [`CI_RECIPE.md`](CI_RECIPE.md#artifacts-upload-paths)):

| Artifact | Key paths inside bundle |
|----------|-------------------------|
| `record-proof` | `data/record-proof/summary.json`, `run.json`, `projections/` |
| `nix-toolchain-proof` | `data/cold-warm-proof/summary.json` or `environment-blocker.json`; `data/agent-loop-proof/summary.json` or blocker |
| `tier1-bazel-ci` | `data/tier1-bazel-ci/summary.json` or blocker |
| `lre-proof-probe` | `data/lre-proof/summary.json`, `probe.json`, or blocker |
| `lre-nix-toolchain-proof` | `data/lre-nix-toolchain-proof/summary.json` or blocker |
| `lre-cold-warm-proof` | `data/lre-cold-warm-proof/summary.json` or blocker, `projections/` |
| `demo-proof` | `data/demo-proof/summary.json`, `projections/` |

### 1.4 Re-run on open PRs (optional but recommended)

After the first green `main` run:

1. Re-run **NLFR proof** on open PRs targeting `main` (or push/rebase to re-trigger).
2. Treat restored CI as a **merge gate** again.

---

## Phase 2 — Promote artifacts to `proof-samples/`

Follow [`GITHUB_RELEASE.md`](GITHUB_RELEASE.md#ci-restore--promotion-runbook) (promotion
runbook). Summary below; release doc is canonical for redaction rules and doc touch list.

### 2.1 Confirm promotable outputs

Do **not** promote from a run where Nix jobs wrote only `environment-blocker.json`
unless that blocker is the honest sample you intend to ship (typical for LRE on wrong
host — not for cache/tier1 claims).

### 2.2 Redact paths

For each `summary.json` to commit:

1. Copy from extracted CI artifact or `data/<proof-name>/summary.json`.
2. Replace absolute repo paths with `<repo>`.
3. Replace Nix-store Bazel paths with `<bazel>`.
4. Confirm no secrets, raw prompts, env vars, or full logs remain.
5. Preserve `run_id`, SHA-256 hashes, truth labels, and `evidence_refs`.

Spot-check:

```bash
jq . docs/proof-samples/*.json
```

### 2.3 Map CI / local source → committed sample

| CI / local source | Committed sample under `docs/proof-samples/` |
|-------------------|-----------------------------------------------|
| `data/cold-warm-proof/summary.json` | `cold-warm-summary.json` |
| `data/local-exec-proof-2w/summary.json` | `two-worker-summary.json` *(not a dedicated CI job — promote from author Nix or add CI leg later)* |
| `data/agent-loop-proof/summary.json` | `agent-loop-summary.json` |
| `data/tier1-live-bazel/summary.json` (Acts 1+2) | `agent-bugfix-summary.json`, `agent-feature-summary.json` |
| `data/tier1-bazel-ci/summary.json` | Tier1 CI slice — align with bugfix/feature samples or refresh metrics in README |
| `data/worker-evidence-proof/summary.json` | *(optional new sample — document in README)* |
| `data/lre-proof/summary.json` or blocker | `lre-proof-summary-sample.json` or `lre-proof-blocker-sample.json` |
| `data/lre-nix-toolchain-proof/summary.json` or blocker | `lre-nix-toolchain-proof-summary-sample.json` or `lre-nix-toolchain-proof-blocker-sample.json` |
| `data/lre-cold-warm-proof/summary.json` or blocker | `lre-cold-warm-proof-summary-sample.json` or `lre-cold-warm-proof-blocker-sample.json` |
| `data/compare-proof/summary.json` | `compare-summary.json` *(only if release needs stable M9 excerpt)* |

Update [`proof-samples/README.md`](proof-samples/README.md) provenance row: **Linux CI**
instead of author-Nix-only.

### 2.4 Doc follow-ups after promotion

1. [`proof-samples/README.md`](proof-samples/README.md) — table rows and provenance note.
2. [`TRYOUT_PACKET.md`](TRYOUT_PACKET.md) — proof table if numbers shift.
3. [`ONE_PAGER.md`](ONE_PAGER.md) — bullets if CI numbers differ from author Nix.
4. [`CI_RECIPE.md`](CI_RECIPE.md) — check off restore checklist.

### 2.5 Verify before tag / release

```bash
uv run pytest -q
bash -n scripts/*.sh
```

Tag and release steps: [`GITHUB_RELEASE.md`](GITHUB_RELEASE.md#6-tag-and-release).

---

## Local substitutes (cannot run GHA now)

Use these to validate workflow **scripts** and keep shipping while Actions are offline.
They do **not** substitute for Linux CI credibility on promotion — run Phase 1 on GHA
before promoting samples.

**One command (wave 10):** [`scripts/verify-gha-readiness.sh`](../scripts/verify-gha-readiness.sh)
audits workflow YAML, lists jobs, and runs the fast substitute spine below.

### Fast spine (mirrors `unit` + `verify-demo-fixture`)

```bash
uv sync
uv run pytest -q
bash -n scripts/*.sh
PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --dry-run
./scripts/compare-agent-runs.sh --dry-run
./scripts/record-proof.sh
./scripts/record-canvas-build.sh
npm ci --prefix apps/canvas
npm --prefix apps/canvas run build
npm --prefix apps/canvas run test:truth
./scripts/verify-demo.sh
```

### Nix toolchain (mirrors jobs 2–6)

Requires `nix develop` (best on x86_64-linux for LRE parity):

```bash
nix develop --command bash -lc '
  set -euo pipefail
  uv sync
  ./scripts/cold-warm-cache-proof.sh
  ./scripts/agent-loop-proof.sh
  ./scripts/tier1-bazel-ci-proof.sh
  ./scripts/lre-proof.sh
  ./scripts/lre-nix-toolchain-proof.sh
  ./scripts/lre-cold-warm-proof.sh
'
```

Darwin may record honest `environment-blocker.json` for LRE cold/warm — expected, not a
local gate failure.

### Optional local-only proofs (not CI jobs today)

```bash
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh   # M7
./scripts/compare-proof.sh   # M9
```

Full matrix: [`CI_RECIPE.md`](CI_RECIPE.md#local-substitutes-by-job).

---

## Honesty gates after restore

- Do not claim **CI passed** until all seven jobs complete on a real workflow run.
- Do not claim **`lre_cache_parity_observed`** from Darwin or from blocker-only artifacts.
- Do not claim **`worker_identity`** from CI unless M7 evidence was captured in that path.
- Do not update `proof-samples/` provenance to "Linux CI" without completing Phase 2 from
  a green run.
- Document which job or script produced each claim in [`ADOPTION_GUIDE.md`](ADOPTION_GUIDE.md).

---

## Related docs

- Job matrix and artifact paths: [`CI_RECIPE.md`](CI_RECIPE.md)
- Restore checklist (operator tick list): [`CI_RECIPE.md`](CI_RECIPE.md#gha-restore-checklist)
- Release promotion detail: [`GITHUB_RELEASE.md`](GITHUB_RELEASE.md#ci-restore--promotion-runbook)
- Sample catalog: [`proof-samples/README.md`](proof-samples/README.md)
