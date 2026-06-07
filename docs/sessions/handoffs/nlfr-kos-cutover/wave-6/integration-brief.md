# Wave 6 Integration Brief — retention-policy-v1

**Date:** 2026-06-06  
**Worker:** `waves-5-8-integrate-close`  
**Status:** SHIPPED  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 5 `W5-INTEGRATE` done

---

## Wave-6 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-retention-policy-core` | `retention-policy-core` | `W6-RETENTION-POLICY` | SHIPPED | `src/nlfr/retention_policy.py`, proof packet retention block |
| `coord-retention-cli` | `retention-cli` | `W6-RETENTION-CLI` | SHIPPED | `compare index --limit`, honest CLI messaging |
| `coord-retention-wiki` | `retention-wiki` | `W6-RETENTION-WIKI` | SHIPPED | Diátaxis retention docs + USEFULNESS_ROADMAP Gap 2 rows |
| `w6-integrate` | `waves-5-8-integrate-close` | `W6-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Policy module | `src/nlfr/retention_policy.py` |
| Proof packet hook | `src/nlfr/projectors/proof_packet.py` (retention block) |
| CLI | `src/nlfr/commands/compare_cmd.py` (`index --limit`) |
| Wiki | `docs/wiki/how-to/export-and-compare-run-groups.md`, `docs/wiki/reference/contracts/compare-projection-v1.md` |
| Roadmap | `docs/USEFULNESS_ROADMAP.md` (Gap 2) |
| Tests | `tests/test_retention_policy.py`, `tests/test_compare.py` |

---

## Claim boundary

**Supported:** index-only discovery, explicit no-auto-purge policy, `compare index --limit` as `derived_v1` / `high`.

**Blocked (honest):** auto-purge/TTL deletion, multi-run trend dashboards — labeled `future`.

---

## Proof (local)

```bash
uv run pytest tests/test_retention_policy.py tests/test_compare.py -q
PYTHONPATH=src uv run python -m nlfr compare index --help
PYTHONPATH=src uv run python -m nlfr compare index --db data/record-proof/nlfr.sqlite --limit 5
```

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Four-wave plan: [`../wave-5/four-wave-plan-5-8.md`](../wave-5/four-wave-plan-5-8.md)
