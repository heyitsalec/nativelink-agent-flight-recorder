# Wave 4 Integration Brief — LRE cold/warm cache parity

**Date:** 2026-06-06  
**Coordinator:** `coord-lre-cache-parity`  
**Status:** DONE  
**Ceiling:** `lre_cache_parity_observed` (`collectable_v1`, `medium`)

---

## Landed

| Layer | Artifact | Claim |
|-------|----------|-------|
| Research | `provenance-lre-parity-research.md` | Gap analysis + minimal Linux blueprint |
| Proof script | `scripts/lre-cold-warm-proof.sh` | LRE cold/warm → `summary.json` or blocker |
| Samples | `docs/proof-samples/lre-cold-warm-proof-*-sample.json` | Schema mirrors script output |
| Tests | `tests/test_lre_proof.py` | 9 fixture-backed contract tests (substrate + toolchain + cold/warm) |
| Docs | `demo/nativelink/README.md` | Phase-4 wiring + honest `claim_boundary` |
| CI | `.github/workflows/nlfr-proof.yml` | `lre-cold-warm-ci` uploads cold/warm proof artifacts |
| DAG | `docs/dags/lre-proof.md` | Ceiling synced to `lre_cache_parity_observed` |

---

## Proof

```bash
uv run pytest tests/test_lre_proof.py -q
# 9 passed

bash -n scripts/lre-cold-warm-proof.sh
grep -n 'lre_cache_parity_observed' docs/dags/lre-proof.md
```

Nix green path (CI or local when toolchain available on x86_64-linux):

```bash
nix develop --command ./scripts/lre-cold-warm-proof.sh
# → data/lre-cold-warm-proof/summary.json status: lre_cache_parity_observed
```

Prior phase regressions (unchanged):

```bash
nix develop --command ./scripts/lre-proof.sh
# → data/lre-proof/summary.json status: lre_substrate_ready

nix develop --command ./scripts/lre-nix-toolchain-proof.sh
# → data/lre-nix-toolchain-proof/summary.json status: lre_bazelrc_generated
```

---

## Honesty / claim boundary

**Supported (phase 4 — wave 4):**

- LRE cold/warm cache economics on x86_64-linux via `lre.json5` + `--config=lre`
- `nlfr run --mode local-exec` ingest + proof export with `cache_economics`
- Warm `hit_rate` exceeds cold on `//tasks:priority_test` through LRE endpoints

**Still unsupported:**

- Hermetic container-image parity across distinct worker images
- `lre-cc` C++ LRE builds as parity proof target
- aarch64-darwin full LRE cold/warm green path (Darwin records `environment-blocker.json`)
- Fleet dashboards, queue-time / action-placement correlation

---

## Broker rule (unchanged)

Do not spawn implement workers for fleet/scheduler UI. Fleet honesty stays in `future-fleet-claims` research DAG.

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-lre-parity-*.md`
- DAG mirror: `docs/dags/lre-proof.md`
