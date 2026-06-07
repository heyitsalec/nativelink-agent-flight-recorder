# Provenance — lre-nix-proof (wave-3)

**Worker:** `lre-nix-proof`  
**Wave:** 3  
**Write scope:** `scripts/lre-nix-toolchain-proof.sh`, `scripts/lre-proof.sh` (minimal), `tests/test_lre_proof.py`, `docs/proof-samples/`, `demo/nativelink/README.md`  
**Coordinator:** `coord-lre-nix-phase3`

---

## Summary

Added phase-3 Nix LRE toolchain proof script that probes repo-root `lre.bazelrc`
after `nix develop`, optionally attempts `bazel build --config=lre` on
x86_64-linux, and writes `data/lre-nix-toolchain-proof/summary.json` with
`status: lre_bazelrc_generated` or honest `environment-blocker.json`. Extended
pytest fixtures, proof samples, and README phase-2 honesty. Does **not** claim
cache parity.

---

## Changes

| File | Change |
|------|--------|
| `scripts/lre-nix-toolchain-proof.sh` | New probe → `summary.json` / blocker |
| `scripts/lre-proof.sh` | One-line pointer to phase-3 probe |
| `tests/test_lre_proof.py` | +3 tests (blocker, summary shape, stub success) |
| `docs/proof-samples/lre-nix-toolchain-proof-*-sample.json` | Schema mirrors script output |
| `docs/proof-samples/README.md` | Table entries for new samples |
| `demo/nativelink/README.md` | Phase-2 wiring + probe (replaces “Future full-LRE”) |

---

## Proof commands (worker run)

```bash
bash -n scripts/lre-nix-toolchain-proof.sh
uv run pytest tests/test_lre_proof.py -q
# 7 passed

# Green path (requires nix develop):
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
# → data/lre-nix-toolchain-proof/summary.json status: lre_bazelrc_generated
```

---

## Honesty ceiling

| Claim | Status | Labels |
|-------|--------|--------|
| Nix devShell generates `lre.bazelrc` | **Proven** (when script runs inside `nix develop`) | `collectable_v1`, `medium` |
| `--config=lre` Bazel build on x86_64-linux | **Optional probe** — recorded in `build_config_lre` | `collectable_v1` when attempted |
| Cache hit parity local↔remote | **Not claimed** | — |
| `lre_substrate_ready` regression | **Not re-run** — out of write scope | — |

---

## Blockers

| Blocker | When |
|---------|------|
| `lre.bazelrc` missing | Script run outside `nix develop` → `environment-blocker.json` |
| `PLATFORM_DARWIN` / non-x86_64-linux | Optional build skipped with `skip_reason` |

---

## Depends on

- `lre-nix-flake-wire` — flake-parts + LRE module + `installationScript`
- `lre-nix-bazel-wire` — `MODULE.bazel`, `.bazelrc` try-import

---

## JSON envelope

```json
{
  "worker_id": "lre-nix-proof",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-3/",
  "artifacts": {
    "provenance": "provenance-lre-nix-proof.md",
    "created": [
      "scripts/lre-nix-toolchain-proof.sh",
      "docs/proof-samples/lre-nix-toolchain-proof-summary-sample.json",
      "docs/proof-samples/lre-nix-toolchain-proof-blocker-sample.json"
    ],
    "updated": [
      "scripts/lre-proof.sh",
      "tests/test_lre_proof.py",
      "docs/proof-samples/README.md",
      "demo/nativelink/README.md"
    ]
  },
  "claims_touched": ["lre_bazelrc_generated"],
  "claim_ceiling": "lre_bazelrc_generated",
  "blockers": ["CACHE_HIT_PARITY", "PLATFORM_DARWIN", "NLFR_RUN_CONFIG_LRE"]
}
```
