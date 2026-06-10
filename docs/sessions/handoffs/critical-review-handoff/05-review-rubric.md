# Critical review rubric — NLFR (`feat/docs-wiki-wave2`)

**Audience:** Fresh Claude session performing adversarial / skeptical review  
**Branch:** `feat/docs-wiki-wave2` (parent of `main` / tag `v0.2.0-mvp`)  
**Date:** 2026-06-07  
**Product rule:** Evidence-first recorder — not a UI-first dashboard. Canvas renders projection JSON only.

---

## Session setup (read first)

| Doc | Why |
|-----|-----|
| [`AGENTS.md`](../../../../AGENTS.md) | Canonical product rules, truth labels, v1 scope |
| [`docs/ONE_PAGER.md`](../../../../ONE_PAGER.md) | Proven vs unproven claims |
| [`docs/DEMO_SCRIPT.md`](../../../../DEMO_SCRIPT.md) | Full rehearsal paths (Tier 1–3) |
| [`docs/proof-samples/README.md`](../../../../proof-samples/README.md) | Honesty contract for committed samples |
| [`docs/sessions/handoffs/nlfr-kos-cutover/wave-9/gap-honesty-packet.md`](../nlfr-kos-cutover/wave-9/gap-honesty-packet.md) | Open gaps (GHA, fleet, M8 live Cursor, LRE Linux) |
| [`docs/sessions/handoffs/docs-excellence/wave-0/excellence-bar.md`](../docs-excellence/wave-0/excellence-bar.md) | Doc quality bar inherited by wiki wave 2 |

**Your deliverable:** A written review with **severity-tagged findings** (`P0` ship-blocker, `P1` honesty/claim violation, `P2` doc drift, `P3` polish). Cite file paths and commands run. Do not fix code unless asked — report first.

---

## High-level review checklist (~45 min)

Work top-down before deep dives.

### 1. Claim honesty (P0/P1)

- [ ] Every "proven" statement in README, ONE_PAGER, TRYOUT_PACKET maps to a **named script + artifact path**.
- [ ] `source_kind` is stated wherever a lens, sample, or projection is shown (`collectable_v1`, `derived_v1`, `simulated_v1`, `future`).
- [ ] Worker identity is described as **conditional** (M7 stdout + regex), not global.
- [ ] Two-worker proof is **endpoint readiness only** — not load distribution or scheduler assignment.
- [ ] Agent-loop proof distinguishes validation leg (`collectable_v1`) from agent/change leg (`simulated_v1` in bounded loop).
- [ ] Tier1 live Bazel (`bazel_validated: true`) is not conflated with pytest-only or `NLFR_SKIP_BAZEL=1` fallback.
- [ ] Compare lens (M9) is **`derived_v1`** — no new collectable fleet claims.
- [ ] GHA offline is acknowledged; docs do not instruct blocking on CI green for local proof.

### 2. Architecture integrity (P0/P1)

- [ ] Canonical flow is intact: **record → ingest → SQLite → export projection → canvas**.
- [ ] Canvas docs never describe live NativeLink API calls at render time.
- [ ] Proof packet lists **unsupported claims** explicitly (scheduler, queue, placement, fleet ops).
- [ ] Privacy: no raw prompts, env vars, credentials in committed JSON or docs.

### 3. Doc coherence (P2)

- [ ] [`docs/INDEX.md`](../../../../INDEX.md) and [`docs/wiki/README.md`](../../../../wiki/README.md) link quadrants and contracts.
- [ ] Command blocks match across README, ADOPTION_GUIDE, DEMO_SCRIPT, wiki how-tos.
- [ ] Pytest counts and milestone references are current (run `uv run pytest -q` — do not trust stale "N passed" in legacy DAGs).
- [ ] Historical banners on legacy docs where wave-1 noted gaps (`EXTENSION_DAG`, `ONE_PAGER`, `demo/nativelink/README.md`).

### 4. Proof lane health (P0/P1)

- [ ] `uv run pytest -q` passes (baseline gate).
- [ ] `bash -n scripts/*.sh` — no syntax errors.
- [ ] `npm --prefix apps/canvas run test:truth` — truth-label UI tests pass.
- [ ] Committed proof samples parse and match documented `source_kind` / confidence.

### 5. Demo credibility (P1/P2)

- [ ] Default canvas projection is **canvas-dev `collectable_v1`** (dogfood), not agent-loop fixture.
- [ ] Hero GIFs labeled as curated replay, not live shell recording.
- [ ] Tier1 demo path (`?view=tier1-demo`) matches committed `tier1-demo.json` view spec.

---

## Deep-dive checklist (~2–3 hr)

Pick at least one area per row. Cross-check code, tests, and docs together.

### A. Evidence spine (`src/nlfr/`)

- [ ] Ingest idempotency: re-ingest same artifacts → stable keys, no duplicate corruption.
- [ ] Truth labels on every exported node/edge/metric/claim: four fields present.
- [ ] `nlfr doctor` reports honest blockers outside Nix (no fake `ok`).
- [ ] `nlfr compare export` produces `derived_v1` with `evidence_refs` to source run groups.
- [ ] Worker admin stdout parser (`worker_admin_stdout.py`) — promotion rules match M7 docs.

### B. Bazel / NativeLink parsers

- [ ] Fixture tests use real files under `tests/fixtures/bazel/`.
- [ ] BEP, execution log, profile parsers do not invent worker placement.
- [ ] `simulated_v1` ingest path is explicit in CLI (`--source-kind`).

### C. Agent adapter (M8)

- [ ] `cursor_adapter_v1` sidecar shape in tier1 scenarios.
- [ ] `record-agent-change.sh` stores `model` + `prompt_sha256` only.
- [ ] `agent-live-proof.sh` blocker sample is valid `collectable_v1` negative evidence.
- [ ] Bounded `agent-loop-proof.sh` stays `simulated_v1` on agent leg.

### D. Tier1 live Bazel

- [ ] `tier1-live-bazel-proof.sh` chains Acts 1+2 with real Bazel when in Nix.
- [ ] `tests/test_tier1_live_bazel.py` — blocker smoke without Bazel; live gate behind env var.
- [ ] Proof samples `agent-bugfix-summary.json`, `agent-feature-summary.json` match live summary shape.
- [ ] Act 3 compare: `compare-agent-runs.sh` + `promote-tier1-compare.sh` → `derived_v1`.

### E. Canvas (`apps/canvas/`)

- [ ] Loads projection JSON only; no fetch to NativeLink.
- [ ] Truth legend visible; mode rail lenses match view spec protocol.
- [ ] `test:truth` covers label rendering for collectable/derived/simulated/future.
- [ ] View composer (`composer` command) exports view-spec without inventing backend state.

### F. Proof samples & promotion

- [ ] Each JSON in `docs/proof-samples/` has README catalog row with claim boundary.
- [ ] `CI_PROMOTION_MATRIX.md` — no sample promoted beyond its script's honesty ceiling.
- [ ] `fleet-claims-matrix-sample.json` aligns with `future-fleet-claims.md`.

### G. Wiki wave 2 deliverables

- [ ] `docs/wiki/reference/contracts/**` — schema docs match actual export shapes.
- [ ] `docs/wiki/decisions/001-evidence-first-recorder.md` — ADR matches implementation.
- [ ] `docs/diagrams/broker-orchestration.md` — captioned `derived_v1` / maintainer-only.
- [ ] Compare sample: `compare-projection-sample.json`, `tests/test_compare_proof_sample.py`.

### H. Open gaps (honest negatives)

- [ ] GHA: [`GHA_RESTORE_RUNBOOK.md`](../../../../GHA_RESTORE_RUNBOOK.md) matches workflow reality.
- [ ] LRE Linux parity: blocker samples honest on darwin.
- [ ] Fleet parsers: still `future` / blocked per gap-honesty packet.
- [ ] Live Cursor CLI: operator-host, not falsely claimed as CI-green.

---

## Commands to run

Run from repo root after `uv sync` and `npm --prefix apps/canvas install`.

### Baseline gates (mandatory)

| Command | Expected output | If it fails |
|---------|-----------------|-------------|
| `uv run pytest -q` | `140 passed, 3 skipped` (± as branch evolves) | P0 — stop and file finding |
| `bash -n scripts/*.sh` | Exit 0, no output | P0 |
| `npm --prefix apps/canvas run test:truth` | All truth tests pass | P1 |
| `PYTHONPATH=src uv run python -m nlfr doctor --mode cache-only --json` | JSON with `ok` true/false honestly | P1 if lies outside Nix |

### Doctor / simulate spine (no Nix)

```bash
PYTHONPATH=src uv run python -m nlfr simulate \
  --scenario safe-leaf-change \
  --output-dir /tmp/nlfr-review \
  --run-group review-smoke \
  --skip-run \
  --json
```

**Expect:** Exit 0; JSON plan with `simulated_v1` paths. No silent success if scenario missing.

```bash
PYTHONPATH=src uv run python -m nlfr ingest \
  --database /tmp/nlfr-review/nlfr.sqlite \
  --run-key simulation:safe-leaf-change:cache-only \
  --run-group review-smoke \
  --bep tests/fixtures/bazel/bep.jsonl \
  --execution-log tests/fixtures/bazel/execution-log.json \
  --profile tests/fixtures/bazel/profile.json \
  --source-kind simulated_v1

PYTHONPATH=src uv run python -m nlfr graph export \
  --db /tmp/nlfr-review/nlfr.sqlite \
  --run-group review-smoke \
  --output /tmp/nlfr-review/action-graph.json
```

**Expect:** `action-graph.json` with truth labels on nodes; `source_kind` = `simulated_v1`.

### Fixture demo bundle

```bash
./scripts/verify-demo.sh
```

**Expect:** Tests pass; exports under `data/demo-proof/projections/`; does **not** overwrite `apps/canvas/public/projections/` (canvas-dev default).

### Tier1 dry-run (no SQLite writes)

```bash
./scripts/tier1-agent-demo.sh --dry-run --json
```

**Expect:** Exit 0; JSON plan for acts 1–3; scenario paths under `demo/scenarios/tier1/`.

### Tier1 pytest fallback (no Bazel)

```bash
uv run pytest tests/test_tier1_live_bazel.py tests/test_tier1_agent_demo.py -q
```

**Expect:** Pass; blocker tests run without `NLFR_RUN_TIER1_LIVE_BAZEL=1`.

### Proof sample fixture tests

```bash
uv run pytest tests/test_compare_proof_sample.py tests/test_agent_live_proof_samples.py -q
```

**Expect:** Pass; samples match committed JSON under `docs/proof-samples/`.

### Canvas build smoke

```bash
npm --prefix apps/canvas run build
```

**Expect:** Clean build; no TypeScript errors.

### Nix paths (optional — only if `nix develop` available)

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

**Expect (green):** `data/tier1-live-bazel/summary.json` with `collectable_v1`, `bazel_validated: true`.  
**Expect (blocker):** `environment-blocker.json` with honest probe metadata — still valid negative evidence.

```bash
nix develop --command ./scripts/cold-warm-cache-proof.sh
```

**Expect:** `data/cold-warm-proof/summary.json` — cold `hit_rate` 0.0, warm `hit_rate` 1.0.

### Fleet claims audit

```bash
./scripts/fleet-claims-audit.sh
```

**Expect:** `data/fleet-claims-audit/claim-matrix.json` — unsupported claims stay `future` / blocked.

---

## Red flags to hunt

Treat any match as at least **P1** until disproven.

| Red flag | Where to look | Why it matters |
|----------|---------------|----------------|
| "Worker assigned action X" without M7 stdout evidence | Canvas, README, proof packet prose | Invented scheduler correlation |
| Two-worker demo narrated as "distributed build" | README, DEMO_SCRIPT, ONE_PAGER | Over-claim vs `worker_endpoints_ready` |
| `collectable_v1` on fixture-only path without `--source-kind simulated_v1` | Ingest CLI usage in docs | Truth-label lie |
| Canvas described as "connecting to NativeLink" | `apps/canvas/`, wiki explanation pages | Breaks evidence-first architecture |
| Agent-loop sample shown without saying agent leg is `simulated_v1` | proof-samples, Tier 2 cue cards | Mixed-label confusion |
| Tier1 pytest fallback presented as live Bazel proof | Scripts, README quickstart | `NLFR_SKIP_BAZEL=1` is not validation proof |
| Missing `unsupported_claims` in proof packet export | `nlfr proof export` output | Hides honesty surface |
| Raw prompt or env var in committed JSON | `docs/proof-samples/`, `data/` | Privacy violation |
| Stale pytest count in IMPLEMENTATION_DAG or legacy docs | `docs/IMPLEMENTATION_DAG.md` | Doc drift erodes trust |
| "CI green" as ship gate while GHA offline | CONTRIBUTING, CI_RECIPE | Blocks honest local-first workflow |
| Compare lens implying worker correlation | M9 docs, compare projection | `derived_v1` is diff-only |
| `future` nodes presented as shipped | ARCHITECTURE_TRACK, dag-gui | Roadmap cosplay |
| Hero GIF captioned as live recording | README, MEDIA_CAPTURE | Media honesty |
| `bazel_validated: true` in sample without matching `validation: bazel` field | tier1 proof samples | Schema / claim mismatch |
| Duplicate or conflicting command blocks | ADOPTION_GUIDE vs WALKTHROUGH vs wiki | Operator confusion |
| View spec routing claims backend state | `view-composer-protocol.md`, templates | Projection-only rule broken |

---

## Severity rubric

| Severity | Definition | Examples |
|----------|------------|----------|
| **P0** | Broken proof lane or false collectable claim in committed artifacts | pytest fail; sample JSON claims live Bazel without `bazel_validated`; canvas invents worker queue |
| **P1** | Honesty violation or scope overreach in user-facing docs | Scheduler claim; two-worker = distribution; missing truth labels in demo script |
| **P2** | Doc drift, stale counts, broken links, quadrant mix without headers | Wrong pytest count; missing INDEX link; historical banner gap |
| **P3** | Style, naming, minor UX | Typo in cue card; inconsistent heading case |

---

## Review output template

```markdown
# NLFR critical review — YYYY-MM-DD

## Executive summary
(3–5 sentences: ship/no-ship for external demo, top risks)

## Commands run
(bullet list with pass/fail)

## Findings
### P0
- ...
### P1
- ...
### P2
- ...
### P3
- ...

## Claim audit table
| Claim (doc location) | Evidence (script/artifact) | Verdict |
|--------------------|----------------------------|---------|

## Open questions answered
(see 08-open-questions-for-reviewer.md)

## Recommended follow-ups
(prioritized, no drive-by refactors)
```

---

## Related handoff docs

| File | Purpose |
|------|---------|
| [`04-drift-audit.md`](04-drift-audit.md) | Pre-computed drift: Goals A–F, doc matrix, demo blockers |
| [`06-demo-rehearsal-script.md`](06-demo-rehearsal-script.md) | Condensed operator demo |
| [`07-career-positioning-notes.md`](07-career-positioning-notes.md) | Portfolio framing (author context) |
| [`08-open-questions-for-reviewer.md`](08-open-questions-for-reviewer.md) | Specific questions to answer |
| [`09-claude-session-prompt.md`](09-claude-session-prompt.md) | Copy-paste prompt for fresh Claude session |
