# Tier1 live Bazel tests + handoffs — Wave 1 provenance

**Worker:** `tier1-tests-handoffs`  
**Coordinator:** `coord-tier1-live-bazel`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Added fixture-backed blocker smoke for `tier1-live-bazel-proof.sh`, optional `NLFR_RUN_TIER1_LIVE_BAZEL=1` live gate, wave-1 broker handoffs, DAG mirror, and DEMO_SCRIPT primary path for live Bazel proof.

---

## Inputs read

| Artifact | Path |
|----------|------|
| Live proof script | `scripts/tier1-live-bazel-proof.sh` |
| CI Bazel test pattern | `tests/test_tier1_bazel_ci.py` |
| Frontier broker arm | `docs/sessions/handoffs/frontier-wave/wave-0/broker-arm.md` |
| LRE wave-2 handoff template | `docs/sessions/handoffs/lre-proof/wave-2/` |

---

## Deliverables written

| File | Action |
|------|--------|
| `tests/test_tier1_live_bazel.py` | Created — blocker smoke + live gate |
| `docs/dags/tier1-live-bazel.md` | Created |
| `docs/dags/README.md` | Updated — tier1-live-bazel entry |
| `docs/DEMO_SCRIPT.md` | Updated — primary live Bazel path |
| `docs/sessions/handoffs/tier1-live-bazel/wave-1/spawn-ledger.md` | Created |
| `docs/sessions/handoffs/tier1-live-bazel/wave-1/integration-brief.md` | Created |
| `docs/sessions/handoffs/tier1-live-bazel/wave-1/worker-results.json` | Created |
| `docs/sessions/handoffs/tier1-live-bazel/wave-1/task-packet-tier1-tests-handoffs.md` | Created |
| This file | Created |

---

## Test matrix

| Test | Scope | Live Bazel |
|------|-------|------------|
| `test_tier1_live_bazel_blocker_without_bazel` | Missing bazel → `environment-blocker.json`, exit 2 | No |
| `test_tier1_live_bazel_proof_live` | Full acts 1+2 proof → `summary.json` | Yes (`NLFR_RUN_TIER1_LIVE_BAZEL=1`) |

---

## Proof

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
```

---

## Honesty / claim boundary

- Blocker test validates environment honesty without inventing Bazel success.
- Live gate requires Nix devShell with Bazel + demo monorepo — not run in default CI pytest job.

---

## Return

```json
{
  "worker_id": "tier1-tests-handoffs",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/tier1-live-bazel/wave-1/",
  "artifacts": {
    "provenance": "provenance-tier1-tests-handoffs.md",
    "modified": [
      "tests/test_tier1_live_bazel.py",
      "docs/dags/tier1-live-bazel.md",
      "docs/dags/README.md",
      "docs/DEMO_SCRIPT.md"
    ]
  },
  "proof": {
    "command": "uv run pytest tests/test_tier1_live_bazel.py -q",
    "exit_code": 0,
    "passed": 1,
    "skipped": 1
  },
  "claims_touched": ["collectable_v1"],
  "blockers": []
}
```
