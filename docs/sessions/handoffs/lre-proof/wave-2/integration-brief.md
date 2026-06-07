# Wave 2 Integration Brief — LRE substrate proof

**Date:** 2026-06-06  
**Coordinator:** `coord-lre-proof`  
**Status:** DONE  
**Ceiling:** `lre_substrate_ready` (`collectable_v1`, `medium`)

---

## Landed

| Layer | Artifact | Claim |
|-------|----------|-------|
| Config | `demo/nativelink/lre.json5` | LRE ports 50071/50081, one local worker |
| Docs | `demo/nativelink/README.md` | Phase-1 substrate + `claim_boundary` |
| Script | `scripts/lre-proof.sh` | Probe → blocker or delegate → `summary.json` |
| Samples | `docs/proof-samples/lre-proof-*-sample.json` | Schema mirrors script output |
| Tests | `tests/test_lre_proof.py` | 4 fixture-backed contract tests |
| CI | `.github/workflows/nlfr-proof.yml` | `lre-proof-probe` uploads `summary.json` or blocker |

---

## Proof

```bash
uv run pytest tests/test_lre_proof.py -q
# 4 passed

bash -n scripts/lre-proof.sh
grep -n 'lre_substrate_ready' docs/dags/lre-proof.md
```

Nix green path (CI or local when toolchain available):

```bash
nix develop --command ./scripts/lre-proof.sh
# → data/lre-proof/summary.json with status: lre_substrate_ready
```

---

## Honesty / claim boundary

**Supported (phase 1):**

- LRE NativeLink server substrate configured (`lre.json5`)
- Cache-only and local-exec smoke on dedicated LRE ports
- Two-worker endpoint readiness probes

**Unsupported until Nix LRE toolchain:**

- Hermetic `bazel --config=lre` cache parity
- `lre.bazelrc` wiring via `flake.nix` + `MODULE.bazel`
- Fleet dashboards, queue-time / action correlation

Phase 2 remains blocked on TraceMachina Nix LRE wiring per README **Future full-LRE** section.

---

## Broker rule (unchanged)

Do not spawn implement workers for fleet/scheduler UI. Fleet honesty stays in `future-fleet-claims` research DAG.

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-lre-w2-*.md`
- DAG mirror: `docs/dags/lre-proof.md`
