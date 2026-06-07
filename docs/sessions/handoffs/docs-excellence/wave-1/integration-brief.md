# Wave 1 Integration Brief — Docs excellence

**Date:** 2026-06-06  
**Coordinator:** broker-parent  
**Status:** DONE_WITH_CONCERNS (wave-1 SHIPPED; wave-2 gap workers partial)  
**Branch:** `feat/docs-excellence`  
**Excellence bar:** [`wave-0/excellence-bar.md`](../wave-0/excellence-bar.md)

---

## Wave-1 coordinators (7 parallel sub-DAGs)

| Coordinator | Worker | Status | Summary |
|-------------|--------|--------|---------|
| `coord-readme-flagship` | `readme-flagship` | DONE | Harmony-style `README.md`: trimmed loop + Path A/B, M7 conditional worker identity, tier1 `?view=tier1-demo`, GHA-offline local gates primary, `docs/INDEX.md` hub link, hero GIF embeds + capture fallback note |
| `coord-wiki-hub` | `wiki-hub` | DONE | Full Diátaxis rewrite: `docs/INDEX.md` router + 10 `docs/wiki/**` pages (tutorials, how-tos, reference, explanation); broker handoffs fenced maintainer-only; M7/M8/M9/tier1/LRE/fleet pointers |
| `coord-adoption-paths` | `adoption-paths` | DONE | Synced `ADOPTION_GUIDE`, `WALKTHROUGH`, `CI_RECIPE`, `DEV_ENVIRONMENT`, `DEMO_SCRIPT`: M7–M9 landed, 7-job CI matrix + GHA offline, `compare export`, conditional worker identity, tier1/LRE proof scripts |
| `coord-diagrams` | `diagrams` | DONE | 8 files under `docs/diagrams/`: evidence loop, truth-label ladder, execution ladder, agent-loop provenance, compare projection flow, canvas projection boundary, CI proof lane + README index; captioned mermaid + `source_kind` honesty notes |
| `coord-proof-samples-hub` | `proof-samples-hub` | DONE | Flagship honesty hub in `proof-samples/README.md`; `TRYOUT_PACKET.md` aligned to `v0.2.0-mvp`; `GITHUB_RELEASE.md` GHA-offline promotion runbook; M7 conditional / M8 / M9 / tier1 sections |
| `coord-code-polish` | `code-polish` | DONE | 25 `src/nlfr/**` files: docstrings + one import hygiene fix (`artifacts.py`); **no behavior change**; `uv run pytest -q` → 100 passed, 2 skipped |
| `coord-contributing` | `contributing` | DONE | `CONTRIBUTING.md` proof-scripts table + GHA offline; `USEFULNESS_ROADMAP.md` M9/compare shipped + conditional M7; `IMPLEMENTATION_DAG.md` historical banner; **NEW** `apps/canvas/README.md` |

---

## Wave-2 gap workers (parent dispatch after reflect)

| Worker | Coordinator | Status | Summary |
|--------|-------------|--------|---------|
| `wiki-hub-integrate` | `coord-wiki-hub` | DONE | Diagram links in `INDEX.md` + `wiki/README.md`; `docs/dags/README.md` docs-excellence row; `docs/wiki/compare-runs.md` alias fixes README broken link |
| `media-capture` | broker-parent | DONE | `npm run build` + `capture:heroes` exit 0; `docs/media/nlfr-canvas-tour.gif` + `nlfr-evidence-loop.gif` regenerated; 6 PNGs present under `docs/images/` |
| `historical-docs-batch` | broker-parent | **PENDING** | Historical banners + stale one-liner fixes for 7 legacy docs + `demo/nativelink/README.md` — spawned, not landed at handoff close |
| `docs-excellence-reflect` | broker-parent | DONE (read-only) | Excellence-bar dims 1–5 score ~4.4/5; verdict **DONE_WITH_CONCERNS**; README ↔ ONE_PAGER worker identity consistent |
| `docs-excellence-handoffs-close` | broker-parent | DONE | This brief, spawn ledger, worker-results, wave-0 SHIPPED markers, handoffs README row, DAG status update |

---

## Media P0 (blocker note)

| Phase | Status | Detail |
|-------|--------|--------|
| Reflect (pre-wave-2) | **P0 blocker** | Read-only review flagged missing hero GIFs under `docs/media/` while README embedded them |
| Wave-2 `media-capture` | **Resolved** | Playwright capture succeeded on port 5174; both hero GIFs on disk (888 KB + 652 KB). **Not a blocker at wave-1 close.** |

Operator note: commit regenerated `docs/media/nlfr-canvas-tour.gif` before merge if byte diff vs `main`.

---

## Landed deliverables (working tree on `feat/docs-excellence`)

| Layer | Artifacts |
|-------|-----------|
| Entry | `README.md` (Harmony-style) |
| Router | `docs/INDEX.md`, `docs/wiki/**` (11 pages incl. `compare-runs` alias) |
| Adoption | `ADOPTION_GUIDE`, `WALKTHROUGH`, `CI_RECIPE`, `DEV_ENVIRONMENT`, `DEMO_SCRIPT` |
| Diagrams | `docs/diagrams/**` (7 mermaid topics + README) |
| Proof hub | `docs/proof-samples/README.md`, `TRYOUT_PACKET.md`, `GITHUB_RELEASE.md` |
| Contributor | `CONTRIBUTING.md`, `USEFULNESS_ROADMAP.md`, `IMPLEMENTATION_DAG.md`, `apps/canvas/README.md` |
| Code polish | `src/nlfr/**` docstrings only |
| Media | `docs/media/*.gif`, `docs/images/*.png` |

---

## Remaining concerns (post wave-1)

| ID | Gap | Severity |
|----|-----|----------|
| C-1 | `historical-docs-batch` not landed — legacy docs lack banners; stale "41 passed" may remain | P1 |
| C-2 | Excellence-bar `broker-orchestration` diagram not created (7 other diagrams landed) | P1 |
| C-3 | `docs/wiki/decisions/` ADR-lite directory empty | P1 |
| C-4 | No committed M9 compare proof-sample JSON (documented honestly in hub) | P2 |
| C-5 | Wave-3 integrative review + link audit not run | wave-3 gate |

---

## Proof (local parent gates — GHA offline)

```bash
uv run pytest -q
# 100 passed, 2 skipped

bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
npm --prefix apps/canvas run build
npm --prefix apps/canvas run capture:heroes   # media P0 resolution
```

CI green is **not** a ship gate. See [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).

---

## Honesty / claim boundary

**Docs now correctly state:**

- M7 `worker_identity` is **conditional** on admin stdout attach + parser match
- M9 compare via `nlfr compare export` (`derived_v1`)
- Seven CI jobs with local substitutes when GHA offline
- Canvas renders projection JSON only — no invented scheduler/fleet state

**Still unsupported in prose (unchanged):**

- Scheduler / queue / action placement / load distribution claims
- Fleet ops dashboards
- Global worker-identity proof without stdout evidence

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Wave-0 ARM: `../wave-0/broker-arm.md`
- Excellence bar: `../wave-0/excellence-bar.md`
- DAG mirror: `docs/dags/docs-excellence.md`
