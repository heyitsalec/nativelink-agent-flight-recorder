# Four-wave plan — NLFR KOS cutover (post docs-wiki-wave2)

**Date:** 2026-06-06  
**Worker:** `four-wave-planner` (`coord-roadmap`)  
**Branch:** `feat/docs-wiki-wave2` → next `feat/nlfr-kos-cutover`  
**Status:** PLANNED  
**Canonical DAG:** [`docs/dags/nlfr-kos-roadmap.md`](../../../../dags/nlfr-kos-roadmap.md)

---

## Control plane

| Field | Value |
|-------|-------|
| **dag_ref** | `nlfr-flagship` |
| **Authority** | KOS local primary |
| **linear_authority** | `false` |
| **Serve** | `kos serve` (kos-mcp) |
| **Dispatch** | Parent broker per [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) |

PER-* Linear issues are historical mirrors only. Do **not** create or gate waves on PER tickets.

---

## Prerequisite

**docs-wiki-wave2** (`feat/docs-wiki-wave2`, merged): flagship Diátaxis wiki, README, adoption
paths, diagrams, proof-samples hub — see [`docs-excellence.md`](../../../../dags/docs-excellence.md).

Substrate from M5–M9 + frontier wave (compare, worker parser, agent adapter dry-run, LRE scripts)
must remain green under local proof gates.

---

## Wave summary

| # | Wave id | Objective (one line) | Integrate node |
|---|---------|----------------------|----------------|
| 1 | `tier1-canvas-polish` | Human-design UX on tier1 canvas + run selector | `W1-INTEGRATE` |
| 2 | `agent-provenance-live` | M8 non-dry-run E2E + redacted stdout proof | `W2-INTEGRATE` |
| 3 | `lre-linux-manual-proof` | x86_64-linux LRE parity sample promotion | `W3-INTEGRATE` |
| 4 | `ci-restore-verify` | GHA green + proof-sample promotion | `W4-INTEGRATE` |

---

## Wave 1 — tier1-canvas-polish

**dag_ref:** `nlfr-flagship`  
**Handoffs:** `docs/sessions/handoffs/nlfr-kos-cutover/wave-1/`

### North star

Polished tier1 demo canvas with run-group selector driven by compare index data (fixture or
export) — implements human-design-handoff items 1–4 without inventing backend state.

### Coordinators + write_scope

| coordinator_id | write_scope |
|----------------|-------------|
| `coord-canvas-ux-polish` | `apps/canvas/src/components/**`, `apps/canvas/src/styles/**` |
| `coord-run-group-selector` | `apps/canvas/src/**/RunSelector*`, `apps/canvas/public/views/**` |
| `coord-canvas-screenshots` | `scripts/record-canvas-build.sh`, `apps/canvas/tests/**`, `docs/images/canvas/**` |
| `coord-canvas-readme` | `apps/canvas/README.md` |

### KOS nodes

`W1-CANVAS-UX` · `W1-RUN-SELECTOR` · `W1-SCREENSHOTS` · `W1-INTEGRATE`

### Proof gates

```bash
npm --prefix apps/canvas run test:truth
npm --prefix apps/canvas run build
./scripts/record-canvas-build.sh
```

### Ceiling / stops

- **Ceiling:** run selector reads indexed groups as `derived_v1`; visual polish only on existing projection nodes.
- **Stop:** selector needs live SQLite/API not representable as projection JSON.
- **Blocked:** fleet/scheduler/queue claims in UI copy or new compare dimensions.

---

## Wave 2 — agent-provenance-live

**dag_ref:** `nlfr-flagship`  
**Handoffs:** `docs/sessions/handoffs/nlfr-kos-cutover/wave-2/`

### North star

One real (non-dry-run) agent change produces `collectable_v1` provenance chain matching
deterministic scenario shape — closes human-design-handoff blocker #3 and USEFULNESS_ROADMAP Gap 5.

### Coordinators + write_scope

| coordinator_id | write_scope |
|----------------|-------------|
| `coord-agent-live-e2e` | `scripts/record-agent-change.sh`, `scripts/agent-live-proof.sh` |
| `coord-agent-proof-samples` | `docs/proof-samples/agent-live-*` |
| `coord-agent-adapter-docs` | `adapters/cursor/**` |
| `coord-agent-live-tests` | `tests/test_record_agent_change.py`, `tests/test_agent_live_proof.py` |

### KOS nodes

`W2-AGENT-E2E` · `W2-AGENT-PROOF` · `W2-ADAPTER-DOCS` · `W2-INTEGRATE`

### Proof gates

```bash
./scripts/record-agent-change.sh --dry-run
./scripts/agent-live-proof.sh
uv run pytest tests/test_record_agent_change.py tests/test_agent_live_proof.py -q
```

### Ceiling / stops

- **Ceiling:** `chain_complete=true`, model + `prompt_sha256` only.
- **Stop:** `environment-blocker.json` if Cursor CLI unavailable — no fake collectable run.
- **Blocked:** raw prompt storage; live LLM as validation proof.

---

## Wave 3 — lre-linux-manual-proof

**dag_ref:** `nlfr-flagship`  
**Handoffs:** `docs/sessions/handoffs/nlfr-kos-cutover/wave-3/`

### North star

Redacted `lre_cache_parity_observed` sample from x86_64-linux manual Nix run promoted to
`docs/proof-samples/` — closes ladder phase-4 sample gap while GHA remains offline.

### Coordinators + write_scope

| coordinator_id | write_scope |
|----------------|-------------|
| `coord-lre-linux-runbook` | `docs/LRE_LINUX_PROOF.md`, `docs/DEV_ENVIRONMENT.md` (LRE section) |
| `coord-lre-sample-promote` | `docs/proof-samples/lre-cold-warm-proof-*`, `docs/proof-samples/README.md` |
| `coord-lre-ladder-sync` | `docs/dags/lre-proof.md`, `docs/dags/future-execution-ladder.md` |

### KOS nodes

`W3-LINUX-RUNBOOK` · `W3-SAMPLE-PROMOTE` · `W3-LADDER-SYNC` · `W3-INTEGRATE`

### Proof gates

```bash
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
# Operator-owned optional green:
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

### Ceiling / stops

- **Ceiling:** manual Linux sample OR honest blocker sample — both `collectable_v1`.
- **Stop:** no Linux host → promote blocker sample only; do not claim parity.
- **Blocked:** fleet UI; CI artifact claims (wave 4); aarch64-darwin full green.

---

## Wave 4 — ci-restore-verify

**dag_ref:** `nlfr-flagship`  
**Handoffs:** `docs/sessions/handoffs/nlfr-kos-cutover/wave-4/`

### North star

Sustained green `nlfr-proof.yml` + promoted redacted CI summaries — closes human-design-handoff
blocker #1 and USEFULNESS_ROADMAP Gap 3 CI attachment path.

### Coordinators + write_scope

| coordinator_id | write_scope |
|----------------|-------------|
| `coord-gha-restore` | `.github/workflows/nlfr-proof.yml`, `scripts/*-ci-proof.sh` |
| `coord-ci-proof-promote` | `docs/proof-samples/**` |
| `coord-ci-docs-sync` | `docs/CI_RECIPE.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/dags/README.md`, gha-offline shift status note |

### KOS nodes

`W4-GHA-RESTORE` · `W4-PROOF-PROMOTE` · `W4-CI-DOCS` · `W4-INTEGRATE`

### Proof gates

Local until GHA green; then:

```bash
gh run list --workflow=nlfr-proof.yml --limit 5
uv run pytest -q
./scripts/record-proof.sh
./scripts/tier1-bazel-ci-proof.sh
```

### Ceiling / stops

- **Ceiling:** at least one sustained green run with promoted samples matching local schemas.
- **Stop:** GHA still offline → wave `blocked` on KOS; waves 1–3 ship independently.
- **Blocked:** claiming CI green before observed pass; PR comment exporter (future).

---

## Cross-wave policy

| Policy | Rule |
|--------|------|
| GHA offline | Local proof gates at every wave close; see [gha-offline-proof-shift.md](../../frontier-wave/wave-1/gha-offline-proof-shift.md) |
| Truth labels | Every new claim: `source_kind`, `confidence`, `evidence_refs`, `redaction_state` |
| Privacy | No secrets, raw prompts, customer logs |
| Spawn | Coordinators return `DispatchManifest` only; parent spawns workers |
| Write scope | Disjoint per coordinator; integration workers (`W*-INTEGRATE`) docs-only |

---

## Next broker action

1. ARM wave-0: `broker-arm.md`, `spawn-ledger.md`, `KOS-startup-routing.md` under this tree.
2. Seed KOS nodes for wave 1 (`W1-*` runnable, rest `blocked_by` prior integrate).
3. Dispatch wave 1 coordinators in parallel on `feat/nlfr-kos-cutover`.

---

## Source refs

- [`USEFULNESS_ROADMAP.md`](../../../../USEFULNESS_ROADMAP.md) — gaps 3, 5, 6; demo polish
- [`human-design-handoff.md`](../../m5-m9-umbrella/wave-4/human-design-handoff.md) — design pass + blockers
- [`future-execution-ladder.md`](../../../../dags/future-execution-ladder.md) — tier1-canvas-polish priority 3
- [`nlfr-kos-roadmap.md`](../../../../dags/nlfr-kos-roadmap.md) — canonical DAG + mermaid timeline
