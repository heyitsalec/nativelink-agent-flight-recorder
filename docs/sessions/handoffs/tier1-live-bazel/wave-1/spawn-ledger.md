# Spawn ledger — tier1-live-bazel wave-1

**Coordinator:** `coord-tier1-live-bazel`  
**DAG:** `docs/dags/tier1-live-bazel.md`  
**Branch:** `feat/frontier-wave`  
**KOS:** `docs/sessions/handoffs/frontier-wave/wave-0/KOS-startup-routing.md`

| worker_id | type | write_scope | status | provenance |
|-----------|------|-------------|--------|------------|
| tier1-live-bazel-proof-script | worker | `scripts/tier1-live-bazel-proof.sh` | DONE | (pre-landed) |
| tier1-tests-handoffs | worker | `tests/test_tier1_live_bazel.py`, `docs/sessions/handoffs/tier1-live-bazel/wave-1/**`, `docs/dags/tier1-live-bazel.md`, `docs/dags/README.md`, `docs/DEMO_SCRIPT.md` | DONE | `provenance-tier1-tests-handoffs.md` |

**Ceiling:** live tier1 Acts 1+2 with Bazel validation (`collectable_v1`, `high`) — not LRE or worker placement.

**Proof gate:**

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
nix develop --command ./scripts/tier1-live-bazel-proof.sh   # when Nix toolchain available
```
