# Drift audit — NLFR critical review

← [03-broker-history-and-waves.md](03-broker-history-and-waves.md) · [05-review-rubric.md](05-review-rubric.md)  
**Branch:** `feat/docs-wiki-wave2` · **Date:** 2026-06-07  
**Sources audited:** [`docs/ONE_PAGER.md`](../../../ONE_PAGER.md), [`wave-14/umbrella-close-packet.md`](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md), [`docs/DEMO_SCRIPT.md`](../../../DEMO_SCRIPT.md), committed canvas projections (`apps/canvas/public/projections/`), live `uv run pytest -q`.

**Purpose:** Pre-computed drift snapshot for a fresh reviewer. Confirms what still aligns and what has drifted since broker close — without replacing hands-on verification in [`05-review-rubric.md`](05-review-rubric.md).

---

## Executive drift verdict

| Area | Verdict |
|------|---------|
| **Evidence spine (code)** | **ALIGNED** — 140 passed, 3 skipped (verified 2026-06-07) |
| **Truth labels on committed canvas** | **ALIGNED** — default `canvas-dev` is uniformly `collectable_v1` in `action-graph.json` |
| **Authoritative claim docs (ONE_PAGER, DEMO_SCRIPT)** | **ALIGNED** — proven/unproven boundaries match umbrella residuals C-UMB-1–6 |
| **Legacy / historical docs** | **DRIFTED** — stale pytest counts, missing banners on ONE_PAGER / EXTENSION_DAG |
| **CI / live proof posture** | **BLOCKED** — GHA offline; local gates substitute (documented, not hidden) |
| **Demo rehearsal** | **READY with caveats** — Tier 2 fixture path green; Tier 3 / `test:truth` need Nix or running preview |

**Bottom line:** Product honesty docs and committed projections are coherent. Drift is concentrated in **historical planning artifacts**, **wave integration brief snapshots**, and **environment-gated proof paths** — not in the default canvas claim.

---

## Goals A–F scores (deep-dive rubric)

Scores are **1 (broken/dishonest) → 5 (fully aligned + tested)**. Evidence cites repo state on `feat/docs-wiki-wave2`.

| Goal | Area | Score | Rationale |
|------|------|-------|-----------|
| **A** | Evidence spine (`src/nlfr/`) | **5** | Ingest → SQLite → export → canvas intact; `uv run pytest -q` → **140 passed, 3 skipped**; doctor reports honest blockers outside Nix; compare/history/init commands shipped (waves 11–12). |
| **B** | Bazel / NativeLink parsers | **4** | Fixture-backed tests under `tests/fixtures/bazel/`; parsers do not invent scheduler/placement; `simulated_v1` requires explicit `--source-kind`. **Gap:** no live Bazel parser regression in CI (GHA offline). |
| **C** | Agent adapter (M8) | **4** | `record-agent-change.sh` stores model + `prompt_sha256` only; bounded `agent-loop-proof.sh` stays `simulated_v1` on agent leg; live path host-gated (C-UMB-4). Blocker samples committed. |
| **D** | Tier1 live Bazel | **4** | `tier1-live-bazel-proof.sh` + proof samples with `bazel_validated: true`; pytest live gate behind `NLFR_RUN_TIER1_LIVE_BAZEL=1`. **Risk:** `NLFR_SKIP_BAZEL=1` fallback must not be narrated as live proof (DEMO_SCRIPT cue cards address this). |
| **E** | Canvas (`apps/canvas/`) | **4** | Committed projections load without backend fetch; `run_group: canvas-dev`; proof packet includes `future` unsupported claims. **Gap:** `npm run test:truth` requires preview on `:5174` (fails if server not running). |
| **F** | Proof samples & promotion | **4** | 20 JSON samples + README catalog + `CI_PROMOTION_MATRIX.md`; fleet audit script exists. **Gap:** CI promotion deferred (C-UMB-2); wave-1 integration brief still cites **103 passed**. |

**Weighted posture:** **4.2 / 5** — architecture credible; residuals are environmental and doc-hygiene, not spine dishonesty.

---

## Committed canvas projection audit

### `action-graph.json` (default graph)

| Field | Observed | Expected per ONE_PAGER / DEMO_SCRIPT | Verdict |
|-------|----------|--------------------------------------|---------|
| `run_group` | `canvas-dev` | canvas-dev dogfood default | **MATCH** |
| Node/edge `source_kind` | **100% `collectable_v1`** (no `simulated_v1` / `future` in graph file) | Green banner: collectable_v1 dogfood | **MATCH** |
| Truth quad | `confidence`, `evidence_refs`, `redaction_state` present on sampled edges | AGENTS.md four-field rule | **MATCH** |

### Sibling projections (`apps/canvas/public/projections/`)

| File | Dominant `source_kind` | Role | Verdict |
|------|------------------------|------|---------|
| `proof.json` | `collectable_v1` + **`future`** on unsupported fleet claims | Proof Packet lens | **MATCH** — fleet claims correctly `future` |
| `runway.json` | `collectable_v1` | Runway / operator summary | **MATCH** |
| `run-history.json` | `derived_v1` | Multi-run history (W12) | **MATCH** |
| `compare-index.json` | `derived_v1` | Compare index | **MATCH** |
| `compare-projection.json` | `derived_v1` (nested refs may cite `collectable_v1` sources) | Compare lens — diff only | **MATCH** |

**Drift risk:** Presenters opening **only** `action-graph.json` see uniform `collectable_v1` — correct for dogfood, but easy to confuse with agent-loop **mixed** labels. DEMO_SCRIPT Tier 2 cue cards and proof-samples segment mitigate this.

---

## Doc drift matrix

Cross-check of authoritative docs vs repo state. **Severity:** P0 ship-blocker · P1 honesty · P2 doc drift · P3 polish.

| Doc / artifact | Claim or field | Repo reality | Severity | Notes |
|----------------|----------------|--------------|----------|-------|
| [`ONE_PAGER.md`](../../../ONE_PAGER.md) | Proven list (cold/warm, two-worker, M7, agent-loop) | Matches scripts + `docs/proof-samples/` | — | **ALIGNED** |
| [`ONE_PAGER.md`](../../../ONE_PAGER.md) | Branch `main` · tag `v0.2.0-mvp` | Active work on `feat/docs-wiki-wave2` / PR #10 | P2 | Historical tag reference; not a product lie |
| [`ONE_PAGER.md`](../../../ONE_PAGER.md) | Historical banner | **Missing** (wave-1 C-1′ open) | P2 | `EXTENSION_DAG`, `demo/nativelink/README.md` same gap |
| [`DEMO_SCRIPT.md`](../../../DEMO_SCRIPT.md) | Default canvas = canvas-dev `collectable_v1` | `action-graph.json` `run_group: canvas-dev`, all collectable | — | **ALIGNED** |
| [`DEMO_SCRIPT.md`](../../../DEMO_SCRIPT.md) | `verify-demo.sh` does not overwrite `public/projections/` | Script behavior + tests | — | **ALIGNED** |
| [`DEMO_SCRIPT.md`](../../../DEMO_SCRIPT.md) | Tier1 live vs agent-loop mixed labels | proof-samples + cue cards distinguish | — | **ALIGNED** |
| [`umbrella-close-packet.md`](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md) | 140 passed, 3 skipped | `uv run pytest -q` → 140 passed, 3 skipped | — | **ALIGNED** (2026-06-07) |
| [`umbrella-close-packet.md`](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md) | C-UMB-1 … C-UMB-6 residuals | Still true (GHA, fleet, M8, LRE, console) | — | **ALIGNED** |
| [`README.md`](../../../../README.md) | Two-worker = endpoint readiness | Consistent with ONE_PAGER | — | **ALIGNED** |
| [`IMPLEMENTATION_DAG.md`](../../../IMPLEMENTATION_DAG.md) | `41 passed` pytest line | Current: **140 passed, 3 skipped** | P2 | Has historical banner but stale one-liner remains |
| [`docs/dags/README.md`](../../../dags/README.md) | Wave 9: **126 passed** | Current: **140 passed** | P2 | Snapshot at W9 close; wave 10–13 section correct |
| [`docs-wiki-wave2/wave-1/integration-brief.md`](../docs-wiki-wave2/wave-1/integration-brief.md) | **103 passed, 2 skipped** | Current: **140 passed, 3 skipped** | P2 | Integration brief snapshot drift |
| [`ONE_PAGER.md`](../../../ONE_PAGER.md) vs [`02-current-state`](02-current-state-and-proof-matrix.md) | ONE_PAGER omits M9 compare, Tier1, adoption | Handoff matrix includes W10–13 capabilities | P2 | ONE_PAGER is narrower (tag-era); not false, incomplete |
| [`COMPLETION_REVIEW.md`](../../../COMPLETION_REVIEW.md) | Two-worker wording | Endpoint-only caveat present | — | **ALIGNED** |
| Hero GIF captions | Curated replay, not live shell | README + DEMO_SCRIPT | — | **ALIGNED** |

---

## Test suite snapshot

**Command:** `uv run pytest -q`  
**Result (2026-06-07):** `140 passed, 3 skipped in 6.47s`

| Skipped test module | Gate | Why skipped |
|---------------------|------|-------------|
| `tests/test_tier1_live_bazel.py` (live) | `NLFR_RUN_TIER1_LIVE_BAZEL=1` | Requires `nix develop` + real Bazel |
| `tests/test_agent_live_proof.py` | env gate | Live Cursor CLI path |
| `tests/test_tier1_bazel_ci.py` | env gate | CI-tier1 script |

**Other gates:**

| Command | Result | Notes |
|---------|--------|-------|
| `bash -n scripts/*.sh` | **PASS** | Exit 0 |
| `npm --prefix apps/canvas run test:truth` | **FAIL** (no server) | Needs `npm run preview` on `127.0.0.1:5174` first — demo prep blocker, not code regression |

---

## Test gaps (not covered by default pytest)

| Gap | Impact | Mitigation in repo |
|-----|--------|-------------------|
| No sustained **GHA green** on `nlfr-proof.yml` | Skeptics cannot verify Linux Nix path in CI | `cache-only-ci-gate.sh`, `verify-gha-readiness.sh`, `ci-offline-blocker-sample.json` |
| Live Tier1 Bazel skipped by default | External reviewer may only see fixture path | `tier1-live-bazel-proof.sh` + proof-samples with `bazel_validated: true` |
| `test:truth` requires running dev server | Easy to miss in quick review | Document in rubric; run preview before truth tests |
| Fleet / scheduler parsers | No collectable fleet claims | Policy + `future` labels; `fleet-claims-audit.sh` |
| LRE Linux on Darwin | Blocker samples only | `lre-proof-blocker-sample.json`, wave-3 runbook |
| Historical docs cite old pytest counts | Trust erosion in deep doc dives | Wave 1.5 rescue list in `docs-wiki-wave2` integration brief |
| Compare / history UI | Backend tested; UI truth-guard needs server | `test_compare_history.py`, manual Tier 2 Compare lens |

---

## Demo blockers and mitigations

| Blocker | Tiers affected | Severity | Workaround |
|---------|----------------|----------|------------|
| **GHA offline** (~1 month) | Tier 3 skeptic, CI narrative | P0 env | Local gate bundle; `gha-offline-proof-shift.md`; do not claim CI green |
| **Nix + ~82GB disk** for live cold/warm, agent-loop, Tier1 | Tier 1 primary, Tier 3 | P1 env | Tier 2 proof-samples + hero GIFs |
| **Preview server for canvas** | Tier 2 live, `test:truth` | P1 ops | `npm --prefix apps/canvas run preview` before demo |
| **Cursor CLI missing** on host | M8 live, Tier1 Acts 1–2 live | P1 env | `agent-live-blocker-sample.json`; redacted Tier1 JSON samples |
| **LRE Linux** on author's Mac | LRE narrative | P1 env | Blocker samples; manual Linux runbook |
| **Agent-loop vs canvas-dev shape** | Tier 2 narration | P1 honesty | Say labels aloud; use proof-samples for mixed agent-loop |
| **PR #10 unmerged** | Integration story | P2 process | Review on `feat/docs-wiki-wave2`; umbrella already closed locally |

### Tier readiness (from DEMO_SCRIPT)

| Tier | Ready? | Preconditions |
|------|--------|---------------|
| **Tier 1** (~5 min) | **Partial** | Nix for live Bazel; else proof-samples + `tier1-agent-demo.sh --dry-run` |
| **Tier 2** (~15 min) | **Yes** | `uv sync`, `npm install`, preview smoke; proof-samples tabs open |
| **Tier 3** (~30 min) | **Host-gated** | `nix develop` + proof scripts with exit codes |

---

## Claim alignment: ONE_PAGER ↔ umbrella ↔ canvas

| Claim | ONE_PAGER | Umbrella C-UMB | Committed canvas / samples |
|-------|-----------|----------------|----------------------------|
| Cold/warm cache economics | Proven `collectable_v1` | Landed W1–5 | `cold-warm-summary.json` |
| Two-worker endpoints | Proven, not distribution | — | `two-worker-summary.json` |
| Worker identity | Conditional M7 | C-UMB-3 fleet blocked | `proof.json` `future` fleet nodes |
| Agent-loop chain | Mixed labels | C-UMB-4 live gated | `agent-loop-summary.json` (not default canvas) |
| Scheduler / queue / placement | Unproven | C-UMB-3 | `unsupported_claims` in proof export |
| Compare / history | *(not in ONE_PAGER)* | W12 SHIPPED | `compare-projection.json`, `run-history.json` `derived_v1` |
| GHA sustained green | *(implicit via tag)* | C-UMB-1 **open** | `ci-offline-blocker-sample.json` |

---

## Recommended reviewer actions

1. **Run baseline gates** from [`05-review-rubric.md`](05-review-rubric.md) — start preview before `test:truth`.
2. **Spot-check drift rows** marked P2 — confirm whether stale counts matter for merge decision.
3. **Open `action-graph.json`** — confirm `run_group: canvas-dev` and say **collectable_v1** before any lens tour.
4. **Answer** [`08-open-questions-for-reviewer.md`](08-open-questions-for-reviewer.md) Q6–Q10 (claim/doc coherence) using this matrix as starter evidence.
5. **Deliver** review report per rubric template — do not fix code unless asked.

---

← [03-broker-history-and-waves.md](03-broker-history-and-waves.md) · Next: [04-file-mapping.md](04-file-mapping.md) · [05-review-rubric.md](05-review-rubric.md)
