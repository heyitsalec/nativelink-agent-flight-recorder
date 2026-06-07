# T1-BUGFIX live record — Provenance

**Worker:** `t1-bugfix-record` (parent broker)  
**Date:** 2026-06-06  
**Status:** `DONE`

## Commands

```bash
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state fixed
NLFR_SKIP_BAZEL=1 ./scripts/tier1-agent-demo.sh --act 1
./scripts/tier1-bugfix-setup.sh --restore
```

## Artifacts

| Path | Committed |
|------|-----------|
| `data/agent-bugfix-1/` | gitignored |
| `docs/proof-samples/agent-bugfix-summary.json` | yes |

**Blocker documented:** Bazel skipped via `NLFR_SKIP_BAZEL=1`; validation_fallback pytest used.

**Run ID:** `run_a62deac46fa9ee8f15c3415a` · **source_kind:** `collectable_v1`
