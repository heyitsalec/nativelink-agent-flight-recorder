# CI promotion matrix — GHA artifact → proof sample

**Quadrant:** Reference · **Audience:** operators promoting hosted GitHub Actions evidence into committed samples.

**Status (2026-07-07): live.** [`nlfr-proof.yml`](../../.github/workflows/nlfr-proof.yml) runs on hosted GitHub Actions (`ubuntu-latest`) and `main` has been green across every completed push run since 2026-07-07 — e.g. [`28878270360`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28878270360), [`28876722425`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28876722425), [`28862144465`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28862144465). (`cancelled` entries in the run list are `cancel-in-progress` concurrency supersessions from rapid pushes, not failures.) This matrix is now the **live** promotion procedure, not a deferred plan.

**Which jobs actually run, and where.** Four jobs **gate** (block) **every push/PR**: `unit`, `linux-nix-toolchain` (**Nix toolchain proofs**), `tier1-bazel` (**Tier1 Bazel validation (Nix)**), and `verify-demo-fixture`. `lre-nix-ci` (**LRE Nix toolchain proof**) also runs on **every push/PR** but is **`continue-on-error: true`** (non-blocking): on a cold Nix cache the hosted runner can exhaust disk building NativeLink's Rust deps from source ("No space left on device"), an environmental limit that records an honest `environment-blocker.json` without spuriously gating (GitHub issue #100) — matching the sibling LRE jobs' non-blocking posture. The two heavier LRE jobs — `lre-proof-probe` (**LRE substrate proof**) and `lre-cold-warm-ci` (**LRE cold/warm cache parity proof**) — are `schedule`/`workflow_dispatch`-only and `continue-on-error: true`; on push/PR they are **skipped** (see run [`28878270360`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28878270360): both LRE-substrate and LRE-cold/warm jobs `skipped`). Per their workflow comments they have **not** passed on hosted runners — the LRE overlay is version-blocked (`demo/bazel-monorepo/MODULE.lre.bazel`) and Magic Nix Cache throttles cold public runners. They gate nothing and exist as honest, exercised blocker probes. **Canonical LRE cold/warm parity evidence remains local `nix develop` on x86_64-linux** ([`../LRE_LINUX_PROOF.md`](../LRE_LINUX_PROOF.md)).

Canonical procedure: [`../GITHUB_RELEASE.md`](../GITHUB_RELEASE.md#ci-restore--promotion-runbook) · historical restore procedure (Actions are live now): [`../GHA_RESTORE_RUNBOOK.md`](../GHA_RESTORE_RUNBOOK.md) · sample catalog: [`README.md`](README.md).

---

## Scope boundary — single-node smoke; bring-your-own fleet (permanent)

Every LRE proof here is **single-node smoke**: one runner (or one dev host), one local NativeLink worker, cache economics measured on that node. This is a deliberate, **permanent** scope boundary — not a gap awaiting a future closure:

- **NLFR records what your fleet emits; it ships no fleet.** No scheduler, no worker pool, and no cross-worker placement is bundled. Point NLFR at your own NativeLink deployment and it ingests the BEP, worker admin stdout, and cache metrics that deployment produces.
- **Multi-worker / fleet-scale remote execution is bring-your-own-fleet.** `worker_identity` stays **conditional** (M7 — promoted only when admin stdout is attached and matches the parser); scheduler assignment, queue time, action placement, and load distribution stay `out_of_scope`.
- Full claim policy: [`fleet-claims-matrix-sample.json`](fleet-claims-matrix-sample.json) and [`../dags/future-fleet-claims.md`](../dags/future-fleet-claims.md).

No committed sample in this directory claims fleet-scale remote execution, and none will without a bring-your-own-fleet recording that actually emits it.

---

## Preconditions

1. On the **same** workflow run, all blocking jobs finished without failure. On push/PR that is **four** jobs (`unit`, `linux-nix-toolchain`, `tier1-bazel`, `verify-demo-fixture`); `lre-nix-ci` also runs per-push but is non-blocking (`continue-on-error: true`, GitHub issue #100), and the two `schedule`/`workflow_dispatch`-only LRE jobs (`lre-proof-probe`, `lre-cold-warm-ci`) are non-blocking and present only on scheduled/dispatched runs.
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
| 4 | `lre-proof-probe` | `lre-proof-probe` | `data/lre-proof/summary.json` | [`lre-proof-summary-sample.json`](lre-proof-summary-sample.json) | **Schedule/dispatch-only job; has not passed on hosted CI.** Committed sample stays **author-Nix vintage (2026-06-06)** — do **not** promote from hosted CI |
| 4 | `lre-proof-probe` | `lre-proof-probe` | `data/lre-proof/environment-blocker.json` | [`lre-proof-blocker-sample.json`](lre-proof-blocker-sample.json) | **Honest blocker** — author-Nix/local vintage; no hosted-CI run has exercised this probe (schedule/dispatch-only) |
| 4 | `lre-proof-probe` | `lre-proof-probe` | `data/lre-proof/probe.json` | — | **No** — internal probe; cite via `summary.json` only |
| 5 | `lre-nix-ci` | `lre-nix-toolchain-proof` | `data/lre-nix-toolchain-proof/summary.json` | [`lre-nix-toolchain-proof-summary-sample.json`](lre-nix-toolchain-proof-summary-sample.json) | **Refreshed 2026-07-07** from hosted run [`28878270360`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28878270360): `lre_bazelrc_generated`, `build_config_lre.succeeded=false` (bazelrc generated; optional `--config=lre` build did not complete on hosted runner). This job runs **per-push** but is **non-blocking** (`continue-on-error: true`, GitHub issue #100) — cold-cache disk exhaustion records an honest blocker without gating |
| 5 | `lre-nix-ci` | `lre-nix-toolchain-proof` | `data/lre-nix-toolchain-proof/environment-blocker.json` | [`lre-nix-toolchain-proof-blocker-sample.json`](lre-nix-toolchain-proof-blocker-sample.json) | **Honest blocker** for outside-`nix develop` / toolchain gap; hosted per-push runs record the `summary.json` path instead |
| 6 | `lre-cold-warm-ci` | `lre-cold-warm-proof` | `data/lre-cold-warm-proof/summary.json` | [`lre-cold-warm-proof-summary-sample.json`](lre-cold-warm-proof-summary-sample.json) | **Schedule/dispatch-only job; has not passed on hosted CI.** Committed sample is **local x86_64-linux `nix develop`** vintage (regenerated 2026-07-07, PR #75) — promote parity only from local Linux or a green scheduled LRE run; never fabricate |
| 6 | `lre-cold-warm-ci` | `lre-cold-warm-proof` | `data/lre-cold-warm-proof/environment-blocker.json` | [`lre-cold-warm-proof-blocker-sample.json`](lre-cold-warm-proof-blocker-sample.json) | **Honest blocker** on Darwin / missing `lre.bazelrc`; schedule/dispatch-only job — no hosted-CI parity run |
| 6 | `lre-cold-warm-ci` | `lre-cold-warm-proof` | `data/lre-cold-warm-proof/projections/` | — | **No** — optional local inspect; no committed projection sample today |
| 7 | `verify-demo-fixture` | `demo-proof` | `data/demo-proof/summary.json` | — | **No** — fixture demo path (`simulated_v1`); verify-demo gate only |
| 7 | `verify-demo-fixture` | `demo-proof` | `data/demo-proof/projections/` | — | **No** — does not overwrite committed `canvas-dev` |

---

## Local-only sources (no dedicated CI job)

These committed samples are **not** produced by a per-push `nlfr-proof.yml` job — they are either local-only or ride the `schedule`/`workflow_dispatch`-only LRE jobs (`lre-proof-probe`, `lre-cold-warm-ci`) that have not passed on hosted runners. Keep them and promote from local x86_64-linux `nix develop` runs, or — for the LRE legs — a green scheduled/dispatched LRE job; never fabricate metrics.

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
