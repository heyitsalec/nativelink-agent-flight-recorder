# Wave 3 Integration Brief — Nix LRE toolchain proof

**Date:** 2026-06-06  
**Coordinator:** `coord-lre-nix-phase3`  
**Status:** DONE  
**Ceiling:** `lre_bazelrc_generated` (`collectable_v1`, `medium`)

---

## Landed

| Layer | Artifact | Claim |
|-------|----------|-------|
| Research | `provenance-lre-nix-research.md` | TraceMachina flake-parts + LRE module pattern |
| Nix flake | `flake.nix`, `flake.lock` | flake-parts + `flakeModules.lre`; shellHook generates `lre.bazelrc` |
| Bazel consumer | `demo/bazel-monorepo/MODULE.bazel`, `.bazelrc` | `@local-remote-execution` at pinned rev; `try-import` |
| Proof script | `scripts/lre-nix-toolchain-proof.sh` | Probe → `summary.json` or `environment-blocker.json` |
| Samples | `docs/proof-samples/lre-nix-toolchain-proof-*-sample.json` | Schema mirrors script output |
| Tests | `tests/test_lre_proof.py` | 7 fixture-backed contract tests (substrate + toolchain) |
| Docs | `demo/nativelink/README.md` | Phase-2 wiring + honest `claim_boundary` |
| CI | `.github/workflows/nlfr-proof.yml` | `lre-nix-ci` uploads toolchain proof artifacts |

---

## Proof

```bash
uv run pytest tests/test_lre_proof.py -q
# 7 passed

bash -n scripts/lre-nix-toolchain-proof.sh
grep -n 'lre_bazelrc_generated' docs/dags/lre-proof.md
```

Nix green path (CI or local when toolchain available on x86_64-linux):

```bash
nix develop --command ./scripts/lre-nix-toolchain-proof.sh
# → data/lre-nix-toolchain-proof/summary.json status: lre_bazelrc_generated
```

Wave-2 substrate regression (unchanged):

```bash
nix develop --command ./scripts/lre-proof.sh
# → data/lre-proof/summary.json status: lre_substrate_ready
```

---

## Honesty / claim boundary

**Supported (phase 2 — wave 3):**

- Nix devShell generates repo-root `lre.bazelrc` with `build:lre` flags
- Demo monorepo Bzlmod resolves `@local-remote-execution` at pinned NativeLink rev
- `.bazelrc` `try-import`s generated `lre.bazelrc`
- Optional `bazel build --config=lre` probe on x86_64-linux (recorded, not required for ceiling)

**Still unsupported:**

- Hermetic local↔remote cache hit parity via `lre.json5` local worker
- `nlfr run --bazel-arg=--config=lre` end-to-end ingest + proof export
- aarch64-darwin full `lre-cc` builds (upstream rust-only LRE env on Darwin)
- Fleet dashboards, queue-time / action-placement correlation

---

## Broker rule (unchanged)

Do not spawn implement workers for fleet/scheduler UI. Fleet honesty stays in `future-fleet-claims` research DAG.

---

## Handoff index

- Spawn ledger: `spawn-ledger.md`
- Worker results: `worker-results.json`
- Provenance: `provenance-lre-nix-*.md`
- DAG mirror: `docs/dags/lre-proof.md`
- Prior wave: `docs/sessions/handoffs/lre-proof/wave-2/`
