# Spawn ledger — lre-proof wave-3 (Nix LRE toolchain)

**Coordinator:** `coord-lre-nix-phase3`  
**DAG:** `docs/dags/lre-proof.md`  
**Branch:** `feat/lre-fleet-unlocks`  
**KOS:** `docs/sessions/handoffs/unlock-wave/KOS-startup-routing.md`  
**Research:** `provenance-lre-nix-research.md` → **IMPLEMENT_MINIMAL_LINUX**

| worker_id | type | write_scope | status | provenance |
|-----------|------|-------------|--------|------------|
| lre-nix-research | worker | research only | DONE | `provenance-lre-nix-research.md` |
| lre-nix-flake-wire | worker | `flake.nix`, `flake.lock` | DONE | `provenance-lre-nix-flake-wire.md` |
| lre-nix-bazel-wire | worker | `demo/bazel-monorepo/MODULE.bazel`, `.bazelrc`, `.gitignore` | DONE | `provenance-lre-nix-bazel-wire.md` |
| lre-nix-proof | worker | `scripts/lre-nix-toolchain-proof.sh`, tests, proof samples | DONE | `provenance-lre-nix-proof.md` |
| lre-nix-ci | worker | `.github/workflows/nlfr-proof.yml` | DONE | `provenance-lre-nix-ci.md` |
| lre-wave3-handoffs | worker | `wave-3/**`, `docs/dags/lre-proof.md` | DONE | `provenance-lre-wave3-handoffs.md` |

**Ceiling:** `lre_bazelrc_generated` (`collectable_v1`, `medium`) on x86_64-linux — not cache parity or Darwin full `lre-cc`.

**Blocked categories:** `PLATFORM_DARWIN`, `WORKER_TOOLCHAIN_MISMATCH`, `CONTAINER_RUNTIME`, `CACHE_HIT_PARITY`, `DEMO_TARGET_LANGUAGE`, `NLFR_RUN_CONFIG_LRE`

**Proof gate:**

```bash
uv run pytest tests/test_lre_proof.py -q
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
# → data/lre-nix-toolchain-proof/summary.json status: lre_bazelrc_generated
```
