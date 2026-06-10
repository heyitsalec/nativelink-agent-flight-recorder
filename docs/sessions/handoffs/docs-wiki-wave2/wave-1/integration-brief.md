# Wave 1 Integration Brief — Docs wiki wave 2

**Date:** 2026-06-06  
**Coordinator:** broker-parent  
**Status:** DONE_WITH_CONCERNS (wave-1 SHIPPED; waves 1.5–3 pending)  
**Branch:** `feat/docs-wiki-wave2`  
**Excellence bar (inherited):** [`docs-excellence/wave-0/excellence-bar.md`](../../docs-excellence/wave-0/excellence-bar.md)

---

## Wave-1 coordinators (5 parallel sub-DAGs)

| Coordinator | Worker | Status | Summary |
|-------------|--------|--------|---------|
| `coord-historical-banners` | `historical-banners` | SHIPPED (partial) | Historical banners on 5/7 legacy docs (`IMPLEMENTATION_DAG`, `LOCAL_EXECUTION_DAG`, `PRODUCT_FRAMING`, `REMOTE_EXECUTION_PLAN`, `FRAMING_DISTANCE`). **Open:** `EXTENSION_DAG`, `ONE_PAGER`, `demo/nativelink/README.md`; stale `41 passed` line remains in `IMPLEMENTATION_DAG.md` |
| `coord-broker-diagram` | `broker-diagram` | SHIPPED | `docs/diagrams/broker-orchestration.md` with honest `derived_v1` / maintainer-only caption; indexed from `docs/diagrams/README.md` |
| `coord-wiki-adrs` | `wiki-adrs` | SHIPPED | `docs/wiki/decisions/README.md` + ADR [001](../../../../wiki/decisions/001-evidence-first-recorder.md) evidence-first recorder; linked from wiki hub |
| `coord-compare-sample` | `compare-sample` | SHIPPED | `compare-projection-sample.json` + `compare-summary.json` committed; hub updated; fixture test `tests/test_compare_proof_sample.py` |
| `coord-link-audit` | `link-audit` | SHIPPED | `docs/INDEX.md` + `docs/wiki/README.md` contracts cross-links; `export-and-compare-run-groups.md` sample pointers; broker/decisions INDEX rows deferred to wave 1.5 |

---

## KOS flagship wave-2 nodes (parallel track)

| Node | Status | Summary |
|------|--------|---------|
| `W2-CONTRACTS` | done | `docs/wiki/reference/contracts/**` — artifact manifest, proof packet, canvas, compare projection v1 |
| `W2-COMPARE` | done | M9 compare proof samples + pytest fixture |
| `W2-KOS-ROUTING` | done | NLFR wave-0 routing handoffs + KOS cutover brief cross-linked; `dag:nlfr-flagship` on local serve |

Authority: [knowledge-os `nlfr-kos-cutover/wave-0/integration-brief.md`](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/nlfr-kos-cutover/wave-0/integration-brief.md)

---

## Handoffs close worker

| Worker | Status | Summary |
|--------|--------|---------|
| `wiki-wave2-handoffs-close` | DONE | This brief, wave-1 spawn ledger + worker-results, wave-0 coordinator SHIPPED markers, handoffs README row, DAG status update, `docs/dags/README.md` nlfr-kos-roadmap link |

---

## Landed deliverables (branch `feat/docs-wiki-wave2`)

| Layer | Artifacts |
|-------|-----------|
| Diagrams | `docs/diagrams/broker-orchestration.md` |
| ADR-lite | `docs/wiki/decisions/README.md`, `001-evidence-first-recorder.md` |
| Compare sample | `docs/proof-samples/compare-projection-sample.json`, `compare-summary.json`, `tests/test_compare_proof_sample.py` |
| Contracts | `docs/wiki/reference/contracts/**` |
| Historical hygiene | Banners on 5 legacy docs (see partial note above) |
| Link audit | INDEX + wiki hub contracts links; compare how-to sample refs |
| KOS roadmap | `docs/dags/nlfr-kos-roadmap.md` (four-wave plan post merge) |
| Handoffs | `docs/sessions/handoffs/docs-wiki-wave2/wave-0/**`, this wave-1 close packet |

---

## Remaining concerns (post wave-1)

| ID | Gap | Severity | Wave |
|----|-----|----------|------|
| C-1′ | `EXTENSION_DAG`, `ONE_PAGER`, `demo/nativelink/README.md` lack historical banners; stale pytest count in `IMPLEMENTATION_DAG.md` | P1 | 1.5 rescue |
| C-5′ | Integrative link audit — add decisions + broker-orchestration to INDEX diagram table | P2 | 1.5 |
| — | Waves 1.5 reflect, 2 rescue, 3 integrative review | gate | parent |

Inherited gaps C-2–C-4 from docs-excellence are **closed** on this branch.

---

## Proof (local parent gates — GHA offline)

```bash
uv run pytest -q
# 103 passed, 2 skipped (includes test_compare_proof_sample.py)

bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
```

CI green is **not** a ship gate. See [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).

---

## Honesty / claim boundary

**Docs now correctly state:**

- M9 compare sample is `derived_v1` with redacted fixture pair (`record-proof` vs `canvas-dev`)
- Broker orchestration diagram is maintainer-only; no scheduler/fleet claims
- JSON contract pages describe projection shapes only — not live backend state

**Still unsupported (unchanged):**

- Scheduler / queue / worker placement claims without direct evidence
- Global historical-banner coverage on all legacy entry docs

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Wave-0 ARM: `../wave-0/broker-arm.md`
- KOS routing: `../wave-0/KOS-startup-routing.md`
- DAG mirror: `docs/dags/docs-wiki-wave2.md`
- Next umbrella: `docs/dags/nlfr-kos-roadmap.md`
