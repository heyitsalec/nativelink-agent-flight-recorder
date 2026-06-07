# 04 — Repository file mapping

**Packet:** [critical-review-handoff](README.md) · **Branch:** `feat/docs-wiki-wave2`  
**Purpose:** Orient a skeptical reviewer to *where* evidence is recorded, projected, tested, and rendered — without re-walking 13 broker waves.  
**Companion:** [03-broker-history-and-waves.md](03-broker-history-and-waves.md) · [nlfr-kos-cutover index](../nlfr-kos-cutover/README.md)

---

## ASCII tree (key dirs)

```
nativelink-agent-flight-recorder/
├── AGENTS.md                 # Engineering rules: evidence-first, truth labels, proof-before-done
├── README.md                 # Evaluator entry: paths A/B, loop diagram, quick commands
├── pyproject.toml            # uv project; `nlfr` console script → nlfr.cli:main
├── flake.nix / flake.lock    # Nix dev shell: NativeLink 1.3.2, Bazel 9.1.1, LRE toolchain
├── adapters/
│   └── cursor/               # M8 bounded agent adapter docs + runbook
├── apps/
│   └── canvas/               # Vite/React sparse canvas (projection-only)
├── contracts/                # JSON Schema v1: manifest, projections, proof packet
├── data/                     # Proof run outputs (gitignored summaries; committed samples in docs/)
├── demo/
│   ├── bazel-monorepo/       # Tiny Bazel workspace for dogfood proofs
│   ├── nativelink/           # cache-only / local-exec / LRE JSON configs
│   └── scenarios/            # Bounded agent-change JSON scenarios (M4/M8)
├── docs/
│   ├── dags/                 # DAG specs per milestone / KOS wave
│   ├── diagrams/             # Architecture + truth-label ladder visuals
│   ├── proof-samples/        # Committed projection/proof JSON for offline review
│   ├── sessions/handoffs/    # Broker wave receipts (nlfr-kos-cutover, tier1, lre, …)
│   └── wiki/                 # Diátaxis docs: tutorial, how-to, reference, decisions
├── scripts/                  # Proof shell scripts + redact/worker helpers
├── src/
│   └── nlfr/
│       ├── __main__.py       # `python -m nlfr` entry
│       ├── cli.py            # argparse shell; dispatches subcommands
│       ├── config.py         # Paths, modes (cache-only, local-exec, lre)
│       ├── artifacts.py      # Immutable artifact writes + SHA-256 manifest
│       ├── ids.py            # Stable id helpers for runs/artifacts
│       ├── retention_policy.py   # W6 retention limits for compare index
│       ├── commands/
│       │   ├── doctor.py     # Host readiness + mode gates
│       │   ├── init_cmd.py   # W11 scaffold: nlfr init
│       │   ├── run_cmd.py    # Bazel workload orchestration
│       │   ├── generic_run.py    # Non-Bazel record path
│       │   ├── ingest_cmd.py # Manifest → SQLite ingest
│       │   ├── export_cmds.py    # graph/proof/runway export
│       │   ├── compare_cmd.py    # compare export + history index (M9/W12)
│       │   ├── serve_cmd.py  # Static projection HTTP for canvas-dev
│       │   └── simulate_cmd.py   # Fixture agent loop without Bazel
│       ├── db/
│       │   ├── schema.py     # SQLite DDL (evidence spine)
│       │   ├── connection.py # DB open/migrate helpers
│       │   └── ingest.py     # Idempotent row upserts
│       ├── ingest/
│       │   ├── bazel.py      # BEP, profile, execution log parsers
│       │   ├── worker_admin_stdout.py  # M7 worker identity regex
│       │   ├── sqlite.py     # Ingest orchestration
│       │   └── models.py     # Normalized row shapes
│       ├── projectors/
│       │   ├── common.py     # truth() helper — attaches four truth labels
│       │   ├── graph.py      # Action Graph projection
│       │   ├── proof.py      # Proof packet projection
│       │   ├── proof_markdown.py   # W8 PR comment exporter
│       │   ├── compare.py    # M9 compare projection
│       │   ├── remote_execution.py # Remote boundary nodes; unsupported-claim guard
│       │   └── runway.py     # Runway / operator summary export
│       └── runners/
│           ├── bazel.py      # Bazel subprocess + artifact capture
│           ├── nativelink.py # NativeLink server lifecycle
│           └── process.py    # Generic command runner
├── tests/                    # pytest: parsers, projectors, CLI, proof scripts
└── .github/workflows/        # nlfr-proof.yml (offline), cache-only gate (W7)
```

---

## Path → purpose → truth labels → proof command

Truth-label columns describe **where the four fields** (`source_kind`, `confidence`, `evidence_refs`, `redaction_state`) are **defined, enforced, or consumed**. Proof commands are the fastest honest check for that path.

| Path | Purpose | Truth-label relevance | Key proof command |
|------|---------|----------------------|-------------------|
| `AGENTS.md` | Contributor contract: evidence-first spine, label vocabulary, privacy | **Policy** — canonical `source_kind` enum | — |
| `README.md` | Public evaluator onboarding; paths A (fixture) vs B (Nix) | **Docs** — labels explained; fixture = `simulated_v1` | `uv run pytest -q` |
| `contracts/*.v1.json` | JSON Schema for manifest + projections; `$defs/truth` required on nodes | **Schema enforcement** — contract is source of truth for export shape | `uv run pytest tests/test_projectors.py -q` |
| `docs/wiki/reference/truth-labels.md` | Human-readable label ladder + misuse guards | **Docs** — reviewer vocabulary | — |
| `docs/wiki/reference/contracts/` | Wiki mirrors for each contract | **Docs** — ties schema to examples | — |
| `docs/proof-samples/` | Committed projection JSON for offline skeptic pass | **Samples** — inspect `source_kind` per node | `uv run pytest tests/test_compare_proof_sample.py -q` |
| `src/nlfr/artifacts.py` | Immutable artifact capture + `artifact_manifest.json` | **Collectable** — manifest rows carry hashes, not labels yet | `nlfr run` / `scripts/record-proof.sh` |
| `src/nlfr/db/schema.py` | SQLite tables for runs, artifacts, invocations, graph | **Storage** — truth columns on normalized rows | `uv run pytest tests/test_data_spine.py -q` |
| `src/nlfr/ingest/bazel.py` | Parse Bazel BEP/profile into normalized rows | **Collectable** — parsers stamp `collectable_v1` where evidenced | `uv run pytest tests/test_ingest_bazel.py -q` |
| `src/nlfr/ingest/worker_admin_stdout.py` | M7 worker admin stdout → `worker_identity` events | **Collectable** — regex-bound; no scheduler inference | `uv run pytest tests/test_worker_admin_stdout.py -q` |
| `src/nlfr/projectors/common.py` | `truth()` helper; `TRUTH_DEFAULTS` for gaps | **Projection** — every exported node/edge gets four labels | `uv run pytest tests/test_projectors.py -q` |
| `src/nlfr/projectors/graph.py` | Action Graph JSON (`canvas_projection.v1`) | **Derived** — graph from SQLite; remote boundary honesty | `python3 -m nlfr graph export --run-group latest` |
| `src/nlfr/projectors/proof.py` | Proof packet JSON (`proof_packet.v1`) | **Derived** — claims carry evidence_refs | `python3 -m nlfr proof export --run-group latest` |
| `src/nlfr/projectors/compare.py` | Compare projection across run groups (M9) | **Derived** — cross-run metrics labeled `derived_v1` | `python3 -m nlfr compare export --run-group latest` |
| `src/nlfr/projectors/remote_execution.py` | Remote boundary nodes + `unsupported_claims` list | **Honesty guard** — blocks scheduler/queue claims | `uv run pytest tests/test_projectors.py -k remote -q` |
| `src/nlfr/projectors/proof_markdown.py` | PR comment markdown from proof packet (W8) | **Derived** — re-exports labeled claims only | `uv run pytest tests/test_pr_proof_markdown.py -q` |
| `src/nlfr/commands/doctor.py` | Host/mode readiness; cache-only gate hints (W7/W13) | **Operational** — surfaces blockers, not fake labels | `python3 -m nlfr doctor --mode cache-only` |
| `src/nlfr/commands/simulate_cmd.py` | Fixture agent loop without Bazel | **Simulated** — explicit `simulated_v1` on agent leg | `python3 -m nlfr simulate --scenario llm-bounded-patch` |
| `src/nlfr/retention_policy.py` | Compare index retention limits (W6) | **Policy** — no label change; bounds history surface | `uv run pytest tests/test_retention_policy.py -q` |
| `scripts/verify-demo.sh` | Fixture E2E: ingest → export → gate | **Mixed** — fixture path; checks exports exist | `./scripts/verify-demo.sh` |
| `scripts/cold-warm-cache-proof.sh` | M2 cache economics proof | **Collectable** — `hit_rate`, duration delta | `nix develop -c scripts/cold-warm-cache-proof.sh` |
| `scripts/local-exec-proof.sh` | M3 worker endpoint readiness | **Collectable** — no placement claims | `nix develop -c scripts/local-exec-proof.sh` |
| `scripts/worker-evidence-proof.sh` | M7 worker identity via stdout | **Collectable** — `worker_identity_observed` | `scripts/worker-evidence-proof.sh` |
| `scripts/agent-loop-proof.sh` | M4 agent→change→run chain | **Mixed** — validation `collectable_v1`, agent `simulated_v1` | `scripts/agent-loop-proof.sh` |
| `scripts/record-agent-change.sh` | M8 Cursor adapter capture | **Collectable** — `model` + `prompt_sha256` only | `scripts/record-agent-change.sh` |
| `scripts/agent-live-proof.sh` | W2 live agent E2E (host-gated) | **Collectable** when live; else blocker sample | `scripts/agent-live-proof.sh` |
| `scripts/compare-proof.sh` | M9 compare projection smoke | **Derived** — cross run-group lens | `scripts/compare-proof.sh` |
| `scripts/lre-proof.sh` | LRE substrate readiness (phase 1) | **Collectable** / blocker samples on darwin | `scripts/lre-proof.sh` |
| `scripts/cache-only-ci-gate.sh` | W7 offline CI gate recipe | **Gate** — pytest + verify-demo subset | `./scripts/cache-only-ci-gate.sh` |
| `scripts/redact-projection.py` | Strip/redact sensitive spans before export | **Redaction** — sets `redaction_state` | `uv run pytest tests/test_redact_projection.py -q` |
| `adapters/cursor/README.md` | M8 adapter boundary + live runbook | **Docs** — explicit out-of-scope fleet claims | `scripts/record-agent-change.sh` |
| `apps/canvas/src/App.tsx` | Canvas shell: ViewProvider + GridShell | **Consumer** — renders projection only | `npm --prefix apps/canvas run preview` |
| `apps/canvas/src/view/` | View spec load/persist; routing | **Consumer** — no backend invention | `npm --prefix apps/canvas run test:truth` |
| `apps/canvas/src/panels/` | Action Graph, Proof, Compare, Operator panels | **Consumer** — displays truth badges from JSON | `npm --prefix apps/canvas run capture` |
| `apps/canvas/scripts/truth-guard.mjs` | CI guard: every node has four truth keys | **Enforcement** — fails build on missing labels | `npm --prefix apps/canvas run test:truth` |
| `apps/canvas/public/projections/` | Committed fixture projections for dev/preview | **Fixture** — default `simulated_v1` / `collectable_v1` mix | `npm --prefix apps/canvas run preview` |
| `demo/nativelink/*.json5` | NativeLink server configs (cache, local-exec, LRE) | **Config** — enables collectable paths | `python3 -m nlfr doctor --mode cache-only` |
| `demo/scenarios/*.json` | Bounded agent-change scenario definitions | **Fixture** — shapes simulate + live adapter | `nlfr simulate --scenario llm-bounded-patch` |
| `demo/bazel-monorepo/` | Dogfood Bazel targets for proofs | **Workload** — produces real Bazel artifacts | `scripts/record-proof.sh` |
| `tests/fixtures/` | Bazel BEP, worker-admin, compare, agent JSON | **Test evidence** — parser/projection contracts | `uv run pytest -q` |
| `tests/test_projectors.py` | Projection shape + truth label attachment | **Test enforcement** | `uv run pytest tests/test_projectors.py -q` |
| `tests/test_canvas_node_cap.py` | W13 default 8-node cap | **UX guard** — not truth semantics | `uv run pytest tests/test_canvas_node_cap.py -q` |
| `.github/workflows/nlfr-proof.yml` | Full proof CI (currently offline) | **CI** — would re-run collectable proofs | `scripts/verify-gha-readiness.sh` |
| `.github/workflows/nlfr-cache-only-gate.yml` | W7 cache-only gate workflow | **CI** — fixture-friendly gate | `./scripts/cache-only-ci-gate.sh` |
| `docs/dags/nlfr-kos-roadmap*.md` | KOS wave DAG specs (waves 1–13) | **Planning** — maps milestones to files | — |
| `docs/sessions/handoffs/nlfr-kos-cutover/` | Per-wave integration briefs + worker-results | **Receipts** — wave close evidence | see cross-links below |

---

## Reviewer fast path (15 files, read order)

Read after [00-executive-summary.md](00-executive-summary.md) and [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md) if you want code receipts.

| # | File | Why read it |
|---|------|-------------|
| 1 | `AGENTS.md` | Non-negotiable product rules: evidence-first, truth labels, v1 scope ceiling. |
| 2 | `contracts/canvas_projection.v1.json` | Schema `$defs/truth` — the contract every graph node must satisfy. |
| 3 | `src/nlfr/projectors/common.py` | `truth()` helper — where labels are attached at projection time. |
| 4 | `src/nlfr/projectors/graph.py` | Action Graph construction; remote boundary + unsupported-claim honesty. |
| 5 | `src/nlfr/projectors/remote_execution.py` | Explicit list of fleet claims the recorder refuses to invent. |
| 6 | `src/nlfr/ingest/bazel.py` | What Bazel evidence is actually parsed vs ignored. |
| 7 | `src/nlfr/ingest/worker_admin_stdout.py` | M7 ceiling: worker identity from stdout regex only. |
| 8 | `src/nlfr/commands/doctor.py` | What the tool admits it cannot run on this host. |
| 9 | `apps/canvas/src/view/ViewContext.tsx` | Canvas loads projection JSON only — no SQLite/API backend. |
| 10 | `apps/canvas/scripts/truth-guard.mjs` | Automated enforcement that UI-facing JSON includes four truth keys. |
| 11 | `scripts/verify-demo.sh` | Shortest honest E2E: fixture ingest → export → local gates. |
| 12 | `docs/proof-samples/compare-projection-sample.json` | Committed compare lens — inspect labels without Nix. |
| 13 | `adapters/cursor/README.md` | M8 boundary: prompt hash yes, raw prompt / fleet ops no. |
| 14 | `tests/test_projectors.py` | pytest receipts for projection + truth attachment. |
| 15 | `docs/sessions/handoffs/nlfr-kos-cutover/wave-9/gap-honesty-packet.md` | Residual gaps: GHA offline, fleet parsers blocked, host-gated live proofs. |

---

## Handoff cross-links — nlfr-kos-cutover waves

Map major code/doc paths to KOS waves ([full index](../nlfr-kos-cutover/README.md)). Use integration briefs for spawn receipts; use this table for **file locality**.

| Wave | Theme | Primary paths | Integration brief |
|------|-------|---------------|-------------------|
| **W1** | Tier1 canvas polish | `apps/canvas/`, `apps/canvas/baselines/`, `scripts/record-canvas-build.sh` | [wave-1](../nlfr-kos-cutover/wave-1/integration-brief.md) |
| **W2** | Agent provenance live | `adapters/cursor/`, `scripts/agent-live-proof.sh`, `scripts/record-agent-change.sh`, `docs/proof-samples/agent-*` | [wave-2](../nlfr-kos-cutover/wave-2/integration-brief.md) |
| **W3** | LRE Linux manual proof | `docs/LRE_LINUX_PROOF.md`, `scripts/lre-cold-warm-proof.sh`, `docs/proof-samples/lre-*` | [wave-3](../nlfr-kos-cutover/wave-3/integration-brief.md) |
| **W4** | CI restore verify | `docs/GHA_RESTORE_RUNBOOK.md`, `.github/workflows/nlfr-proof.yml`, `scripts/verify-gha-readiness.sh` | [wave-4](../nlfr-kos-cutover/wave-4/integration-brief.md) |
| **W5** | Live proof residual | `scripts/tier1-live-bazel-proof.sh`, `data/agent-live-proof/` (host-gated) | [wave-5](../nlfr-kos-cutover/wave-5/integration-brief.md) |
| **W6** | Retention policy v1 | `src/nlfr/retention_policy.py`, `docs/wiki/how-to/browse-run-history.md` | [wave-6](../nlfr-kos-cutover/wave-6/integration-brief.md) |
| **W7** | Cache-only CI gate | `scripts/cache-only-ci-gate.sh`, `.github/workflows/nlfr-cache-only-gate.yml` | [wave-7](../nlfr-kos-cutover/wave-7/integration-brief.md) |
| **W8** | PR proof attachment | `src/nlfr/projectors/proof_markdown.py`, `scripts/export-pr-proof-comment.sh`, `docs/wiki/how-to/attach-proof-to-pr.md` | [wave-8](../nlfr-kos-cutover/wave-8/integration-brief.md) |
| **W9** | KOS operator bridge | `docs/sessions/handoffs/nlfr-kos-cutover/README.md`, `wave-9/cutover-manifest.json`, `wave-9/gap-honesty-packet.md` | [wave-9](../nlfr-kos-cutover/wave-9/integration-brief.md) |
| **W10** | GHA sustained green | `scripts/verify-gha-readiness.sh`, `docs/sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md` | [wave-10](../nlfr-kos-cutover/wave-10/integration-brief.md) |
| **W11** | Adoption init path | `src/nlfr/commands/init_cmd.py`, `scripts/record-this-target.sh`, `docs/wiki/how-to/adopt-existing-bazel-monorepo.md` | [wave-11](../nlfr-kos-cutover/wave-11/integration-brief.md) |
| **W12** | Multi-run history v1 | `src/nlfr/commands/compare_cmd.py`, `src/nlfr/projectors/compare.py`, `docs/wiki/how-to/browse-run-history.md` | [wave-12](../nlfr-kos-cutover/wave-12/integration-brief.md) |
| **W13** | Operator console ergonomics | `apps/canvas/src/panels/`, `src/nlfr/commands/doctor.py`, `tests/test_canvas_node_cap.py` | [wave-13](../nlfr-kos-cutover/wave-13/integration-brief.md) |
| **W14** | Umbrella 1–13 close | `docs/sessions/handoffs/nlfr-kos-cutover/wave-14/umbrella-close-packet.md` | [wave-14](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md) |

### Milestone DAG aliases (pre-KOS naming)

Older docs and tests still reference M2–M9 milestone names. Quick alias map:

| Milestone | Maps to paths above | DAG doc |
|-----------|---------------------|---------|
| M2 cache economics | `scripts/cold-warm-cache-proof.sh`, `src/nlfr/ingest/bazel.py` | [m5-m9 umbrella](../../../dags/m5-m9-umbrella.md) |
| M3 local-exec | `demo/nativelink/local-execution.json5`, `scripts/local-exec-proof.sh` | [future-execution-ladder](../../../dags/future-execution-ladder.md) |
| M4 agent loop | `demo/scenarios/`, `scripts/agent-loop-proof.sh` | [m8-agent-adapter](../../../dags/m8-agent-adapter.md) |
| M7 worker parser | `src/nlfr/ingest/worker_admin_stdout.py` | [m7-worker-parser](../../../dags/m7-worker-parser.md) |
| M8 agent adapter | `adapters/cursor/`, `scripts/record-agent-change.sh` | [m8-agent-adapter](../../../dags/m8-agent-adapter.md) |
| M9 compare | `src/nlfr/projectors/compare.py`, `scripts/compare-proof.sh` | [m9-multi-run-compare](../../../dags/m9-multi-run-compare.md) |

### docs-wiki-wave2 (this branch)

| Path | Role |
|------|------|
| `docs/wiki/reference/contracts/` | Wiki contract pages promoted in PR #10 |
| `docs/dags/docs-wiki-wave2.md` | DAG for wiki wave 2 scope |
| `docs/sessions/handoffs/docs-wiki-wave2/` | Broker receipts for wiki expansion |

---

## Subtree quick reference

### `scripts/` (proof lane)

All proof scripts write under `data/<proof-name>/` with `summary.json` truth-labeled claims. Matrix: [docs/wiki/reference/proof-scripts-matrix.md](../../../wiki/reference/proof-scripts-matrix.md).

### `tests/` (29 modules)

| Cluster | Files | Proves |
|---------|-------|--------|
| Spine | `test_data_spine.py`, `test_ingest_bazel.py`, `test_cli.py` | SQLite + ingest + CLI wiring |
| Projectors | `test_projectors.py`, `test_compare.py`, `test_pr_proof_markdown.py` | Export shape + truth labels |
| Proof scripts | `test_lre_proof.py`, `test_agent_live_proof.py`, `test_tier1_*.py` | Script contracts fixture-backed |
| Canvas | `test_canvas_node_cap.py` | W13 UX cap |
| Policy | `test_retention_policy.py`, `test_redact_projection.py`, `test_fleet_claims_audit.py` | W6 retention, redaction, fleet honesty audit |

### `docs/wiki/` (Diátaxis)

| Quadrant | Dir | Reviewer entry |
|----------|-----|----------------|
| Tutorial | `tutorial/` | [first-evidence-loop.md](../../../wiki/tutorial/first-evidence-loop.md) |
| How-to | `how-to/` | [export-and-compare-run-groups.md](../../../wiki/how-to/export-and-compare-run-groups.md) |
| Reference | `reference/` | [truth-labels.md](../../../wiki/reference/truth-labels.md), [cli.md](../../../wiki/reference/cli.md) |
| Explanation | `explanation/` | [projection-only-canvas.md](../../../wiki/explanation/projection-only-canvas.md) |
| Decisions | `decisions/` | [001-evidence-first-recorder.md](../../../wiki/decisions/001-evidence-first-recorder.md) |

---

## Sanity commands (post-read)

```bash
uv sync && npm --prefix apps/canvas install
uv run pytest -q                              # ~140 passed, 3 skipped
./scripts/verify-demo.sh                      # fixture spine
npm --prefix apps/canvas run test:truth       # truth-guard on projections
python3 -m nlfr doctor --mode cache-only      # host readiness
```

Nix collectable proofs (optional, ~30+ min): `nix develop` then `scripts/cold-warm-cache-proof.sh`.

---

← [README — START HERE](README.md) · Next: use [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md) to challenge any row in the table above.
