# LRE proof tests — Wave 2 provenance

**Worker:** `lre-w2-tests`  
**Coordinator:** `coord-lre-proof`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Expanded `tests/test_lre_proof.py` with four fixture-backed tests: blocker path (unchanged), `lre.json5` dedicated port validation (50071/50081), probe metadata when config is present, and LRE summary shape via stubbed local-exec delegation (no live NativeLink).

---

## Inputs read

| Artifact | Path |
|----------|------|
| LRE proof script | `scripts/lre-proof.sh` |
| LRE config | `demo/nativelink/lre.json5` |
| Summary sample | `docs/proof-samples/lre-proof-summary-sample.json` |
| Blocker sample | `docs/proof-samples/lre-proof-blocker-sample.json` |
| Coordinator charter | `docs/sessions/handoffs/unlock-wave/wave-0/coordinator-charters.md` |

---

## Deliverables written

| File | Action |
|------|--------|
| `tests/test_lre_proof.py` | Expanded — 4 tests |
| This file | Created |

---

## Test matrix

| Test | Scope | Live NativeLink |
|------|-------|-----------------|
| `test_lre_proof_records_blocker_without_config` | Missing config → `environment-blocker.json` + `probe.json`, exit 2 | No |
| `test_lre_json5_port_validation` | `lre.json5` uses 50071/50081, not 50051/50061 | No |
| `test_lre_proof_probe_when_config_present` | Config present → probe records `lre_config_present: true` | No (stub bins; delegate may fail) |
| `test_lre_summary_shape_with_stubbed_delegation` | Summary writer merges stubbed `local-exec/summary.json`; shape matches sample | No |

---

## Proof

```bash
uv run pytest tests/test_lre_proof.py -q
# 4 passed in 0.27s
```

Full green `lre-proof.sh` → `summary.json` on disk still requires `nix develop` with live NativeLink + Bazel — out of wave-2 test scope.

---

## Honesty / claim boundary

- Tests validate probe/blocker/summary **contracts**, not hermetic Nix LRE or fleet dashboards.
- Summary test mirrors the inline Python from `lre-proof.sh` with fixture-backed local-exec status — does not claim end-to-end LRE smoke without nix toolchain.

---

## Return

```json
{
  "worker_id": "lre-w2-tests",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-2/",
  "artifacts": {
    "provenance": "provenance-lre-w2-tests.md",
    "modified": ["tests/test_lre_proof.py"]
  },
  "proof": {
    "command": "uv run pytest tests/test_lre_proof.py -q",
    "exit_code": 0,
    "passed": 4
  },
  "claims_touched": ["lre_substrate_ready"],
  "blockers": []
}
```
