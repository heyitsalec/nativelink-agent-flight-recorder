# T1-BUGFIX setup — Provenance

**Worker:** `t1-bugfix-setup` (parent broker rescue)  
**Date:** 2026-06-06  
**Status:** `DONE`

## Deliverable

`scripts/tier1-bugfix-setup.sh` — `--state broken|fixed`, `--check`, `--restore`

- **broken:** wrong backlog assertion (pytest fails)
- **fixed:** correct backlog test (llm-bounded-patch hunk)
- **restore:** baseline two-test file (no git dependency)

## Proof

```bash
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state broken --check  # exit != 0
NLFR_SKIP_BAZEL=1 ./scripts/tier1-bugfix-setup.sh --state fixed --check   # exit 0
```
