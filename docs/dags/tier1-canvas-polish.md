# Tier1 canvas polish — NLFR KOS wave 1

**Status:** SHIPPED (wave-1 DONE_WITH_CONCERNS — 2026-06-06)  
**Wave id:** `tier1-canvas-polish`  
**Umbrella:** [nlfr-kos-roadmap.md](nlfr-kos-roadmap.md)  
**Branch:** `feat/nlfr-kos-cutover` (spawn from merged `feat/docs-wiki-wave2`)  
**Handoffs:** `docs/sessions/handoffs/nlfr-kos-cutover/wave-1/`  
**Design brief:** [`human-design-handoff.md`](../sessions/handoffs/m5-m9-umbrella/wave-4/human-design-handoff.md) items 1–4

Broker contract: [knowledge-os/agent-os/harness/broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md)

Control plane: **local KOS primary** — `kos serve http://127.0.0.1:7423`, `dag_ref` **`dag:nlfr-flagship`**, `linear_authority: false`. See [`KOS-startup-routing.md`](../sessions/handoffs/nlfr-kos-cutover/wave-1/KOS-startup-routing.md).

---

## Objective

Human-design pass on tier1 canvas: compare lens polish, run-group selector UX, typography/density
on Proof Drawer and Remote Boundary lens — **projection JSON only**, no invented backend state.

## North star

Evaluator opens `?view=tier1-demo`, selects run groups from `nlfr compare index` output (or
committed index fixture), and sees visually coherent compare/worker/proof surfaces with updated
screenshot baselines.

## Sub-DAG coordinators (parent spawns; coordinators do not spawn)

| Coordinator | Sub-DAG | write_scope |
|-------------|---------|-------------|
| `coord-canvas-ux-polish` | Compare + worker + lens styling | `apps/canvas/src/components/**`, `apps/canvas/src/styles/**` |
| `coord-run-group-selector` | Run selector UX | `apps/canvas/src/**/RunSelector*`, `apps/canvas/public/views/**` |
| `coord-canvas-screenshots` | Baseline capture | `scripts/record-canvas-build.sh`, `apps/canvas/tests/**`, `docs/images/canvas/**` |
| `coord-canvas-readme` | Canvas operator docs | `apps/canvas/README.md` |

Disjoint scopes: UX polish must not touch `RunSelector*` files; selector coordinator owns selector
component tree only. Screenshots run after UX + selector land.

## KOS node IDs

| Node | Role | Prerequisite |
|------|------|--------------|
| `W1-CANVAS-UX` | Compare lens, worker nodes, Proof Drawer density | wave-0 ARM |
| `W1-RUN-SELECTOR` | Run-group selector from compare index fixture/API shape | wave-0 ARM |
| `W1-SCREENSHOTS` | Screenshot baselines + truth test updates | `W1-CANVAS-UX`, `W1-RUN-SELECTOR` |
| `W1-INTEGRATE` | Integration brief + KOS close | all W1 implementers |

## Wave schedule

| Phase | Work | Gate |
|-------|------|------|
| **ARM** | DAG mirror, KOS routing, spawn ledger | this document + handoffs |
| **1a** | Parallel: UX polish, run selector, canvas README | per-coordinator brief |
| **1b** | Screenshot baselines + truth tests | after 1a merge |
| **close** | `W1-INTEGRATE` — integration brief, KOS node closure | parent proof gates |

## Proof commands (local — GHA offline)

```bash
npm --prefix apps/canvas run test:truth
npm --prefix apps/canvas run build
./scripts/record-canvas-build.sh
uv run pytest -q   # if canvas test helpers touched
```

Parent proof gates substitute for CI while GHA is offline:
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Broker rules

| Action | Allowed |
|--------|---------|
| Visual polish on compare lens, worker nodes, Proof Drawer, Remote Boundary | Yes |
| Run-group selector driven by compare index fixture or export shape | Yes |
| Screenshot baseline refresh via `record-canvas-build.sh` | Yes |
| Canvas README operator guidance | Yes |
| Invent worker/scheduler/queue/fleet claims in UI | **No** |
| Add compare dimensions not in projection JSON | **No** |
| New backend API beyond projection export for selector | **No** — stop wave |
| Live SQLite rows not representable as projection | **No** — blocked |

## Ceiling / stop conditions

| Claim | Label | Gate |
|-------|-------|------|
| Run selector shows indexed run groups | `derived_v1` / `medium` | Fixture or CLI-exported index only |
| Compare lens visual polish | `simulated_v1` → layout | Must not add unsupported compare dimensions |
| Live backend / fleet state in UI | **blocked** | Stop if selector invents SQLite rows not in projection |

**Stop wave** if run-selector requires new backend API beyond projection JSON export.

## Relationship to prior work

| Prior DAG | Relationship |
|-----------|--------------|
| [docs-wiki-wave2.md](docs-wiki-wave2.md) | Prerequisite — wiki, diagrams, proof-samples hub |
| [m5-m9-umbrella.md](m5-m9-umbrella.md) | Substrate — M6 real default, M9 compare lens |
| [nlfr-kos-roadmap.md](nlfr-kos-roadmap.md) | Parent umbrella — waves 2–4 follow |

## Exit criteria (wave 1 close)

1. Compare lens and worker nodes visually coherent at `?view=tier1-demo`.
2. Run-group selector reads indexed groups from fixture or compare index export — no invented backend.
3. Proof Drawer and Remote Boundary lens density pass complete.
4. Screenshot baselines updated; `test:truth` green.
5. `apps/canvas/README.md` documents operator path for tier1 demo + compare index.
6. `W1-INTEGRATE` closed on KOS; `integration-brief.md` + `worker-results.json` in handoffs.

## Handoff index

- Wave-1 ARM: [`broker-arm.md`](../sessions/handoffs/nlfr-kos-cutover/wave-1/broker-arm.md)
- KOS routing: [`KOS-startup-routing.md`](../sessions/handoffs/nlfr-kos-cutover/wave-1/KOS-startup-routing.md)
- Spawn ledger: [`spawn-ledger.md`](../sessions/handoffs/nlfr-kos-cutover/wave-1/spawn-ledger.md)
- Wave-0 plan: [`four-wave-plan.md`](../sessions/handoffs/nlfr-kos-cutover/wave-0/four-wave-plan.md)
- KOS cutover brief: [knowledge-os `nlfr-kos-cutover/wave-0/integration-brief.md`](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/nlfr-kos-cutover/wave-0/integration-brief.md)
