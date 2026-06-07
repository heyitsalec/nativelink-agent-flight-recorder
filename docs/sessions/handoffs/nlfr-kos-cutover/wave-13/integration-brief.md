# Wave 13 Integration Brief — operator-console-ergonomics

**Date:** 2026-06-07  
**Worker:** `operator-console-ergonomics` (W13)  
**Status:** SHIPPED  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 12 `W12-INTEGRATE` — closed 2026-06-07

---

## Wave-13 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-canvas-8node-cap` | `operator-console-ergonomics` | `W13-CANVAS-8NODE-CAP` | SHIPPED | 8-node default cap in canvas + contract tests |
| `coord-lens-ergonomics` | `operator-console-ergonomics` | `W13-LENS-ERGONOMICS` | SHIPPED | Compare/table lens panel polish + truth guard |
| `coord-failure-messages` | `operator-console-ergonomics` | `W13-FAILURE-MESSAGES` | SHIPPED | Doctor + init actionable missing-toolchain errors |
| `w13-integrate` | `operator-console-ergonomics` | `W13-INTEGRATE` | DONE | This brief; umbrella 10–13 close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Canvas cap | `apps/canvas/src/pageModel.ts` (`DEFAULT_MAX_VISIBLE_GRAPH_NODES = 8`, `capVisibleGraphNodes`) |
| Contract tests | `tests/test_canvas_node_cap.py` (mirrors pageModel priority + cap logic) |
| Lens ergonomics | `apps/canvas/src/panels/TablePanel.tsx`, `apps/canvas/src/styles.css` (`.lens-panel`, `.compare-lens`) |
| Truth guard | `apps/canvas/scripts/truth-guard.mjs` (compare-lens visibility) |
| Failure messaging | `src/nlfr/commands/doctor.py` (`TOOL_ADOPTION_HINTS`, `ADOPTION_HINT`), `src/nlfr/commands/init_cmd.py` (`_print_next_steps`) |
| Tests | `tests/test_doctor.py`, `tests/test_init_cmd.py` |

---

## Claim boundary

**Supported:** default Action Graph projection renders **≤8 nodes** with priority ordering (`derived_v1` / `high`); compare/table lenses remain accessible; doctor/init cite adoption paths on missing toolchain.

**Blocked (honest):** full operator console / fleet UI, unlimited default graph nodes — labeled `blocked`.

---

## Proof (local)

```bash
uv run pytest tests/test_canvas_node_cap.py tests/test_doctor.py tests/test_init_cmd.py -q
npm --prefix apps/canvas run test:truth
uv run pytest -q
```

---

## KOS close

Wave 13 closes operator-console ergonomics for v1 canvas cap. KOS nodes `W13-*` marked done via
`seed_nlfr_flagship_waves_10_13.py --mark-done`. Proof gate: **140 passed, 3 skipped** (`uv run pytest -q`).

**Next broker action:** Umbrella 1–13 reflection in
[`../wave-14/umbrella-close-packet.md`](../wave-14/umbrella-close-packet.md).

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Canvas cap source: [`pageModel.ts`](../../../../../apps/canvas/src/pageModel.ts)
- Prior wave: [`../wave-12/integration-brief.md`](../wave-12/integration-brief.md)
- Roadmap: [`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md)
