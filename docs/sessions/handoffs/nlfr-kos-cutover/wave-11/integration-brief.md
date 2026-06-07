# Wave 11 Integration Brief — adoption-init-path

**Date:** 2026-06-07  
**Worker:** `adoption-init-path` (W11)  
**Status:** SHIPPED  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 10 `W10-INTEGRATE` — closed 2026-06-07

---

## Wave-11 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-nlfr-init` | `adoption-init-path` | `W11-NLFR-INIT` | SHIPPED | `nlfr init` scaffold + doctor hook + adoption guide sync |
| `coord-adapter-pattern` | `adoption-init-path` | `W11-ADAPTER-PATTERN` | SHIPPED | Monorepo adapter wiki + CLI reference |
| `coord-one-command` | `adoption-init-path` | `W11-ONE-COMMAND` | SHIPPED | `record-this-target.sh` one-command record path |
| `w11-integrate` | `adoption-init-path` | `W11-INTEGRATE` | DONE | This brief; KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Init command | `src/nlfr/commands/init_cmd.py`, `src/nlfr/config.py` (`scaffold_workspace`) |
| Doctor hooks | `src/nlfr/commands/doctor.py` (`ADOPTION_HINT`, `TOOL_ADOPTION_HINTS`) |
| Adoption guide | `docs/ADOPTION_GUIDE.md` (init-first path) |
| Adapter wiki | `docs/wiki/how-to/adopt-existing-bazel-monorepo.md` |
| CLI reference | `docs/wiki/reference/cli.md` (`init` section) |
| One-command path | `scripts/record-this-target.sh`, `scripts/record-proof.sh` |
| Tests | `tests/test_init_cmd.py` |

---

## Claim boundary

**Supported:** idempotent `nlfr init` on fresh clone; documented adapter pattern for existing Bazel monorepos; one-command record to proof packet + run JSON (`derived_v1` / `high`).

**Out of scope:** full monorepo CI migration, auto-discovery of all targets — labeled `future`.

**Environment:** live NativeLink/Bazel still required for non-cache-only proof; doctor reports blockers honestly.

---

## Proof (local)

```bash
PYTHONPATH=src uv run python -m nlfr init --help
uv run pytest tests/test_init_cmd.py -q
./scripts/record-this-target.sh
bash -n scripts/record-this-target.sh
```

---

## KOS close

Wave 11 closes USEFULNESS_ROADMAP Gap 1 adoption friction for v1 scope. KOS nodes `W11-*` marked done via
`seed_nlfr_flagship_waves_10_13.py --mark-done`. Proof gate: **140 passed, 3 skipped** (`uv run pytest -q`).

**Next broker action:** ARM wave 12 `multi-run-history-v1` per
[`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md).

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
- Adapter wiki: [`adopt-existing-bazel-monorepo.md`](../../../../wiki/how-to/adopt-existing-bazel-monorepo.md)
- Prior wave: [`../wave-10/integration-brief.md`](../wave-10/integration-brief.md)
- Roadmap: [`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md)
