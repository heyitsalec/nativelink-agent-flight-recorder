# Wave 1 Integration Brief — Tier1 live Bazel proof

**Date:** 2026-06-06  
**Coordinator:** `coord-tier1-live-bazel`  
**Status:** DONE  
**Ceiling:** live tier1 Acts 1+2 with Bazel (`collectable_v1`, `high`)

---

## Landed

| Layer | Artifact | Claim |
|-------|----------|-------|
| Script | `scripts/tier1-live-bazel-proof.sh` | Acts 1+2 via agent demo + live Bazel |
| Tests | `tests/test_tier1_live_bazel.py` | Blocker smoke + optional live gate |
| DAG | `docs/dags/tier1-live-bazel.md` | Broker mirror + proof commands |
| Demo | `docs/DEMO_SCRIPT.md` | Primary path via live Bazel proof script |

---

## Proof

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
# 1 passed, 1 skipped (blocker smoke only outside nix)

bash -n scripts/tier1-live-bazel-proof.sh
grep -n 'tier1-live-bazel-proof.sh' docs/DEMO_SCRIPT.md
```

Nix green path (CI or local when toolchain available):

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
# → data/tier1-live-bazel/summary.json with status: completed
```

Optional live test gate:

```bash
NLFR_RUN_TIER1_LIVE_BAZEL=1 nix develop --command uv run pytest tests/test_tier1_live_bazel.py -q
```

---

## Honesty / claim boundary

**Supported:**

- Tier1 Act 1 (`agent-bugfix-1`) and Act 2 (`agent-feature-compare`) with real Bazel validation
- Blocker recording when Bazel or demo monorepo unavailable

**Unsupported:**

- LRE / remote execution placement
- Worker queue-time or action correlation
- Act 3 compare triple (separate scripts)

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-tier1-tests-handoffs.md`
- DAG mirror: `docs/dags/tier1-live-bazel.md`
