# Wave 12 Integration Brief — multi-run-history-v1

**Date:** 2026-06-07  
**Worker:** `multi-run-history-v1` (W12)  
**Status:** SHIPPED  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 11 `W11-INTEGRATE` — closed 2026-06-07

---

## Wave-12 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-history-index` | `multi-run-history-v1` | `W12-HISTORY-INDEX` | SHIPPED | Enhanced `compare index --limit` + run-group metadata |
| `coord-history-projection` | `multi-run-history-v1` | `W12-HISTORY-PROJECTION` | SHIPPED | `compare history` multi-run projection exporter |
| `coord-history-wiki` | `multi-run-history-v1` | `W12-HISTORY-WIKI` | SHIPPED | Diátaxis history docs + USEFULNESS Gap 2 sync |
| `w12-integrate` | `multi-run-history-v1` | `W12-INTEGRATE` | DONE | This brief; KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Index CLI | `src/nlfr/commands/compare_cmd.py` (`index --limit`) |
| History exporter | `src/nlfr/projectors/compare.py` (`export_history_projection`) |
| History CLI | `compare history` subcommand |
| Canvas sample | `apps/canvas/public/projections/run-history.json` |
| Wiki | `docs/wiki/how-to/browse-run-history.md`, `docs/wiki/how-to/export-and-compare-run-groups.md` |
| CLI reference | `docs/wiki/reference/cli.md` (`compare history`) |
| Tests | `tests/test_compare_history.py`, `tests/test_compare.py`, `tests/test_retention_policy.py` |

---

## Claim boundary

**Supported:** multi-run index + `run_history` projection (`derived_v1` / `high`); index-only retention; no auto-purge.

**Blocked (honest):** org-wide trend dashboards, auto-purge/TTL jobs — labeled `future`.

Builds on wave 6 retention policy (`index_only`, `no_auto_purge`).

---

## Proof (local)

```bash
uv run pytest tests/test_compare_history.py tests/test_compare.py tests/test_retention_policy.py -q
PYTHONPATH=src uv run python -m nlfr compare index --limit 10 --help
PYTHONPATH=src uv run python -m nlfr compare history --help
```

---

## KOS close

Wave 12 extends M9 beyond pairwise compare without inventing fleet trends. KOS nodes `W12-*` marked done via
`seed_nlfr_flagship_waves_10_13.py --mark-done`. Proof gate: **140 passed, 3 skipped** (`uv run pytest -q`).

**Next broker action:** ARM wave 13 `operator-console-ergonomics` per
[`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md).

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Browse history wiki: [`browse-run-history.md`](../../../../wiki/how-to/browse-run-history.md)
- Prior wave: [`../wave-11/integration-brief.md`](../wave-11/integration-brief.md)
- Roadmap: [`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md)
