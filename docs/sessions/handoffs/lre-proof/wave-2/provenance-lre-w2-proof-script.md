# LRE proof script — Wave 2 provenance

**Worker:** `lre-w2-proof-script`  
**Coordinator:** `coord-lre-proof`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Status:** `DONE`

---

## Executive summary

Verified `scripts/lre-proof.sh` implements the full honest LRE proof path: probe → blocker or local-exec delegation on LRE ports (50071) → `summary.json` with `status: lre_substrate_ready` and `claim_boundary`. Synced proof samples and README. No script edits required — parent inline work was already complete.

---

## Inputs read

| Artifact | Path |
|----------|------|
| KOS routing | `docs/sessions/handoffs/unlock-wave/KOS-startup-routing.md` |
| LRE DAG | `docs/dags/lre-proof.md` |
| Coordinator charter | `docs/sessions/handoffs/unlock-wave/wave-0/coordinator-charters.md` |
| Delegate script | `scripts/local-exec-proof.sh` |
| LRE config (read-only) | `demo/nativelink/lre.json5` |
| Existing test | `tests/test_lre_proof.py` |

---

## Deliverables written

| File | Action |
|------|--------|
| `scripts/lre-proof.sh` | Verified — no changes |
| `docs/proof-samples/lre-proof-summary-sample.json` | Synced — added `recorded_at` |
| `docs/proof-samples/lre-proof-blocker-sample.json` | Verified — already matches script |
| `docs/proof-samples/README.md` | Updated — added summary sample row |
| This file | Created |

---

## Script flow verified

1. **Probe** — writes `probe.json` with PATH/config presence (`collectable_v1`, `high`).
2. **Blockers** — missing `nativelink`, `bazel`, or `lre.json5` → `environment-blocker.json` with `claim_boundary.unsupported_until_lre_config` (exit 2).
3. **Success path** — sets `NLFR_NATIVELINK_CONFIG` to `lre.json5`, LRE cache root, and `grpc://127.0.0.1:50071` endpoints; delegates to `local-exec-proof.sh`.
4. **Summary** — merges local-exec status into `summary.json` with `status: lre_substrate_ready`, `confidence: medium`, and `claim_boundary.unsupported_until_nix_lre_toolchain`.

---

## Proof

```bash
bash -n scripts/lre-proof.sh
# exit 0

# Blocker smoke (stub bins, missing config):
TMP=$(mktemp -d)
mkdir -p "$TMP/bin"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/nativelink" "$TMP/bin/bazel"
chmod +x "$TMP/bin/nativelink" "$TMP/bin/bazel"
NLFR_LRE_OUTPUT="$TMP/lre-proof" \
NLFR_LRE_CONFIG="$TMP/missing-lre.json5" \
NLFR_NATIVELINK_BIN="$TMP/bin/nativelink" \
NLFR_BAZEL_BIN="$TMP/bin/bazel" \
  ./scripts/lre-proof.sh
# exit 2; probe.json + environment-blocker.json written

uv run pytest tests/test_lre_proof.py -q
# 1 passed
```

Full green path (`summary.json`) requires `nix develop` with live NativeLink + Bazel — not run on this host in wave-2 scope.

---

## Honesty / claim boundary

- Phase 1 claim: `lre_substrate_ready` only — **not** hermetic Nix LRE toolchain or fleet dashboards.
- Blocker path documents supported ceiling: cache-only, local-exec smoke, two-worker endpoints.
- Success path documents unsupported until Nix: `--config=lre` cache parity, queue-time correlation.

---

## Return

```json
{
  "worker_id": "lre-w2-proof-script",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-2/",
  "artifacts": {
    "provenance": "provenance-lre-w2-proof-script.md",
    "verified": ["scripts/lre-proof.sh"],
    "synced": [
      "docs/proof-samples/lre-proof-summary-sample.json",
      "docs/proof-samples/lre-proof-blocker-sample.json",
      "docs/proof-samples/README.md"
    ]
  },
  "claims_touched": ["lre_substrate_ready"],
  "blockers": []
}
```
