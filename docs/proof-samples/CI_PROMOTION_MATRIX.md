# CI promotion matrix — GHA artifact → proof sample

**Quadrant:** Reference · **Audience:** operators promoting Linux CI evidence into committed samples after GHA restore.

**Status (2026-06-06):** GitHub Actions cannot be exercised from this repo — this matrix is **documentation only**. Use it when the first sustained green [`nlfr-proof.yml`](../../.github/workflows/nlfr-proof.yml) run completes.

Canonical procedure: [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md#ci-restore--promotion-runbook) · restore checklist: [`../GHA_RESTORE_RUNBOOK.md`](../GHA_RESTORE_RUNBOOK.md) · sample catalog: [`README.md`](README.md).

---

## Preconditions

1. All **seven** jobs on the **same** workflow run finished without workflow failure.
2. Toolchain jobs meant to prove Linux/x86_64 claims produced `summary.json` (not only `environment-blocker.json`), unless the honest outcome is a blocker sample (typical LRE legs on wrong host).
3. Artifacts downloaded to a scratch directory — never commit raw `data/` trees.

Redaction rules (every promoted file):

- Replace absolute repo paths with `<repo>`.
- Replace Nix-store Bazel paths with `<bazel>`.
- Preserve `run_id`, SHA-256 hashes, truth labels, and `evidence_refs`.
- Confirm no secrets, raw prompts, env vars, or full logs remain.

---

## Seven-job matrix

Workflow name: **`NLFR proof`**. Jobs run in parallel; artifact names match upload steps in `nlfr-proof.yml`.

| # | Job ID | Artifact bundle | Artifact path inside bundle | Committed sample | Promote? |
|---|--------|-----------------|------------------------------|----------------|----------|
| 1 | `unit` | `record-proof` | `data/record-proof/summary.json` | — | **No** — generic record spine; no public sample |
| 1 | `unit` | `record-proof` | `data/record-proof/run.json` | — | **No** — run metadata only |
| 1 | `unit` | `record-proof` | `data/record-proof/projections/` | — | **No** — canvas-dev dogfood; committed projection lives under `apps/canvas/public/projections/` |
| 2 | `linux-nix-toolchain` | `nix-toolchain-proof` | `data/cold-warm-proof/summary.json` | [`cold-warm-summary.json`](cold-warm-summary.json) | **Yes** — primary cache economics sample |
| 2 | `linux-nix-toolchain` | `nix-toolchain-proof` | `data/cold-warm-proof/environment-blocker.json` | — | **No** — do not ship as cache success; re-run or cite blocker honestly in run notes only |
| 2 | `linux-nix-toolchain` | `nix-toolchain-proof` | `data/agent-loop-proof/summary.json` | [`agent-loop-summary.json`](agent-loop-summary.json) | **Yes** — agent-loop chain excerpt |
| 2 | `linux-nix-toolchain` | `nix-toolchain-proof` | `data/agent-loop-proof/environment-blocker.json` | — | **No** — unless documenting honest env gap (not chain success) |
| 3 | `tier1-bazel` | `tier1-bazel-ci` | `data/tier1-bazel-ci/summary.json` | [`agent-bugfix-summary.json`](agent-bugfix-summary.json), [`agent-feature-summary.json`](agent-feature-summary.json) | **Yes** — split or derive Act 1 / Act 2 excerpts from combined CI summary; refresh metrics in README |
| 3 | `tier1-bazel` | `tier1-bazel-ci` | `data/tier1-bazel-ci/environment-blocker.json` | — | **No** for tier1 success claims — honest blocker only if shipping LRE-style ceiling doc |
| 4 | `lre-proof-probe` | `lre-proof-probe` | `data/lre-proof/summary.json` | [`lre-proof-summary-sample.json`](lre-proof-summary-sample.json) | **Yes** when substrate ready |
| 4 | `lre-proof-probe` | `lre-proof-probe` | `data/lre-proof/environment-blocker.json` | [`lre-proof-blocker-sample.json`](lre-proof-blocker-sample.json) | **Yes** when substrate missing — honest ceiling |
| 4 | `lre-proof-probe` | `lre-proof-probe` | `data/lre-proof/probe.json` | — | **No** — internal probe; cite via `summary.json` only |
| 5 | `lre-nix-ci` | `lre-nix-toolchain-proof` | `data/lre-nix-toolchain-proof/summary.json` | [`lre-nix-toolchain-proof-summary-sample.json`](lre-nix-toolchain-proof-summary-sample.json) | **Yes** when `lre.bazelrc` generated |
| 5 | `lre-nix-ci` | `lre-nix-toolchain-proof` | `data/lre-nix-toolchain-proof/environment-blocker.json` | [`lre-nix-toolchain-proof-blocker-sample.json`](lre-nix-toolchain-proof-blocker-sample.json) | **Yes** when outside `nix develop` or toolchain gap |
| 6 | `lre-cold-warm-ci` | `lre-cold-warm-proof` | `data/lre-cold-warm-proof/summary.json` | [`lre-cold-warm-proof-summary-sample.json`](lre-cold-warm-proof-summary-sample.json) | **Yes** — parity metrics on x86_64-linux |
| 6 | `lre-cold-warm-ci` | `lre-cold-warm-proof` | `data/lre-cold-warm-proof/environment-blocker.json` | [`lre-cold-warm-proof-blocker-sample.json`](lre-cold-warm-proof-blocker-sample.json) | **Yes** on Darwin / missing `lre.bazelrc` — not parity success |
| 6 | `lre-cold-warm-ci` | `lre-cold-warm-proof` | `data/lre-cold-warm-proof/projections/` | — | **No** — optional local inspect; no committed projection sample today |
| 7 | `verify-demo-fixture` | `demo-proof` | `data/demo-proof/summary.json` | — | **No** — fixture demo path (`simulated_v1`); verify-demo gate only |
| 7 | `verify-demo-fixture` | `demo-proof` | `data/demo-proof/projections/` | — | **No** — does not overwrite committed `canvas-dev` |

---

## Local-only sources (no dedicated CI job)

These committed samples exist today but are **not** produced by a current `nlfr-proof.yml` job. After GHA restore, keep them until a CI leg is added or promote from author-Nix local runs.

| Local source | Script | Committed sample | CI today |
|--------------|--------|------------------|----------|
| `data/local-exec-proof-2w/summary.json` | `NLFR_EXPECTED_WORKERS=2 ./scripts/local-exec-proof.sh` | [`two-worker-summary.json`](two-worker-summary.json) | **None** — promote from `nix develop` on Linux or add future CI job |
| `data/worker-evidence-proof/summary.json` | `NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh` | *(optional new sample)* | **None** — M7 fixture replay local only |
| `data/compare-proof/summary.json` | `./scripts/compare-proof.sh` | [`compare-summary.json`](compare-summary.json) | **None** — M9; `unit` runs compare dry-runs only |
| `data/compare-proof/projections/` (compare export) | `nlfr compare export` / compare-proof | [`compare-projection-sample.json`](compare-projection-sample.json) | **None** |
| `data/tier1-live-bazel/summary.json` (Acts 1+2) | `./scripts/tier1-live-bazel-proof.sh` | [`agent-bugfix-summary.json`](agent-bugfix-summary.json), [`agent-feature-summary.json`](agent-feature-summary.json) | **Superseded on restore** by `tier1-bazel-ci` artifact when green — CI uses `tier1-bazel-ci-proof.sh` (Bazel validation slice; no live `cursor_adapter_v1` record) |
| `data/agent-live-proof/summary.json` or blocker | `./scripts/agent-live-proof.sh` | [`agent-live-summary-sample.json`](agent-live-summary-sample.json), [`agent-live-blocker-sample.json`](agent-live-blocker-sample.json) | **None** — operator-gated live Cursor path |
| `data/*/summary.json` (fleet audit) | `./scripts/fleet-claims-audit.sh` | [`fleet-claims-matrix-sample.json`](fleet-claims-matrix-sample.json) | **None** — policy matrix, not runtime proof |
| `data/two-act-spark-stub/summary.json` + `data/two-act-spark/` (live) | `./scripts/two-act-spark-proof.sh` | [`two-act-spark-stub-summary-sample.json`](two-act-spark-stub-summary-sample.json), [`two-act-spark-live-blocker-sample.json`](two-act-spark-live-blocker-sample.json), [`two-act-spark-live-receipt-sample.json`](two-act-spark-live-receipt-sample.json) | **None** — live leg is operator-gated (`claude` auth); a green live run promotes a `two-act-spark-summary-sample.json` with `receipt_verified` agent legs |

---

## Tier1 CI vs live-Bazel samples

Job `tier1-bazel` runs [`scripts/tier1-bazel-ci-proof.sh`](../../scripts/tier1-bazel-ci-proof.sh), which emits **one** combined `data/tier1-bazel-ci/summary.json` covering Acts `agent-bugfix-1` and `agent-feature-compare` with `validation: bazel`.

Committed [`agent-bugfix-summary.json`](agent-bugfix-summary.json) and [`agent-feature-summary.json`](agent-feature-summary.json) today mirror [`scripts/tier1-live-bazel-proof.sh`](../../scripts/tier1-live-bazel-proof.sh) (live `cursor_adapter_v1` + Bazel). On promotion:

1. Prefer Linux CI numbers from `tier1-bazel-ci/summary.json` for **Bazel validation** bullets in README / TRYOUT_PACKET.
2. Split or hand-trim act-specific excerpts so each committed sample stays a single-act shape.
3. Do **not** claim live Cursor adapter provenance from CI alone — CI proves Bazel validation slice; live adapter remains local / `agent-live-*` samples.

---

## Post-promotion checklist

- [ ] Update provenance in [`README.md`](README.md) from author-Nix to **Linux CI** (with workflow run URL).
- [ ] Refresh sample catalog table rows if metrics or claim boundaries changed.
- [ ] Touch [`../TRYOUT_PACKET.md`](../TRYOUT_PACKET.md) / [`../ONE_PAGER.md`](../ONE_PAGER.md) if public numbers shifted.
- [ ] Check off restore items in [`../CI_RECIPE.md`](../CI_RECIPE.md#gha-restore-checklist).
- [ ] `uv run pytest -q` and `bash -n scripts/*.sh` pass after sample commits.

Spot-check JSON:

```bash
jq . docs/proof-samples/*.json
```

---

## Related docs

- Release runbook: [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md#ci-restore--promotion-runbook)
- GHA restore phases: [`../GHA_RESTORE_RUNBOOK.md`](../GHA_RESTORE_RUNBOOK.md)
- Job matrix and local substitutes: [`../CI_RECIPE.md`](../CI_RECIPE.md)
- Sample catalog and honesty contract: [`README.md`](README.md)
