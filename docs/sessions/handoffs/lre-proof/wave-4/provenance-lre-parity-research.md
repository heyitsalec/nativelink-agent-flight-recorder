# Provenance — lre-parity-research (wave-4)

**Worker:** `lre-parity-research` (readonly)  
**Wave:** 4  
**Coordinator:** `coord-lre-cache-parity`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Decision:** `IMPLEMENT_MINIMAL_LINUX`

---

## Executive summary

Wave-3 landed Nix LRE toolchain wiring (`flake.nix` + `MODULE.bazel` + `lre-nix-toolchain-proof.sh`). The next honest claim is **observed LRE cold/warm cache economics** on x86_64-linux inside `nix develop`, mirroring the proven `cold-warm-cache-proof.sh` pattern with `lre.json5` endpoints and `--config=lre`. Full hermetic container-image parity and `lre-cc` cross-machine claims remain blocked.

---

## Inputs read

| Artifact | Role |
|----------|------|
| `scripts/cold-warm-cache-proof.sh` | Proven cold/warm template: NL server → `nlfr run` cold/warm legs → ingest → `cache_economics` in proof export |
| `demo/nativelink/lre.json5` | LRE substrate: ports `50071`/`50081`, one local worker, filesystem stores under `/tmp/nlfr-nativelink/lre` |
| `docs/sessions/handoffs/lre-proof/wave-3/provenance-lre-nix-research.md` | TraceMachina flake-parts LRE module pattern; Darwin = rust-only env |
| `docs/sessions/handoffs/lre-proof/wave-3/integration-brief.md` | Ceiling `lre_bazelrc_generated`; cache parity explicitly unsupported post-wave-3 |
| `docs/sessions/handoffs/lre-proof/wave-3/worker-results.json` | All wave-3 workers DONE |
| `scripts/lre-proof.sh` | Delegates to `local-exec-proof.sh` on LRE ports |
| `scripts/lre-nix-toolchain-proof.sh` | Phase-2 probe; copies `lre.bazelrc` into monorepo |
| `docs/sessions/handoffs/frontier-wave/wave-0/broker-arm.md` | Frontier intent: cold/warm LRE parity probe, Linux-CI-gated |

---

## Gap analysis

### What exists (sufficient to implement)

1. **Cache-only cold/warm proof** — `cold-warm-cache-proof.sh` runs `cold-cache` / `warm-cache` scenarios, exports `cache_economics` with `hit_rate` delta (`collectable_v1`, `high`).
2. **LRE substrate** — `lre.json5` with dedicated ports; `lre-proof.sh` → `lre_substrate_ready`.
3. **Nix LRE toolchain** — `flake.nix` `flakeModules.lre`, generated `lre.bazelrc`, `MODULE.bazel` `@local-remote-execution`, CI job `lre-nix-ci`.
4. **NLFR ingest/projector path** — `proof.py` `_cold_warm_comparison` keys on `cold-cache` / `warm-cache` scenarios regardless of `mode`.
5. **Demo target** — `//tasks:priority_test` is `py_test`; does not require `lre-cc` container image.
6. **CI host** — `ubuntu-latest` + Nix in `nlfr-proof.yml` (`linux-nix-toolchain`, `lre-proof-probe`, `lre-nix-ci`).

### What is missing (implement scope)

| Gap | Implement fix |
|-----|---------------|
| No LRE cold/warm script | `scripts/lre-cold-warm-proof.sh` (new) |
| `cold-warm-cache-proof.sh` uses `cache-only.json` / port `50051` | New script uses `lre.json5` / ports `50071`/`50081` |
| No `--config=lre` on proof runs | Require `nix develop`; copy `lre.bazelrc` to monorepo; pass `--bazel-arg=--config=lre` |
| No `--mode local-exec` on cold/warm legs | `nlfr run --mode local-exec --remote-executor grpc://127.0.0.1:50071` |
| No wave-4 claim / tests / CI | Extend `tests/test_lre_proof.py`, proof samples, `lre-cold-warm-ci` job |
| `local-exec-proof.sh` hardcodes port wait `50051`/`50061` | **Do not delegate** from new script; inline LRE port readiness (`50071`/`50081`) or parameterize ports in a follow-up fix |

### What stays unsupported (honest ceiling)

- Hermetic **container-image** parity across distinct worker images (`lre.json5` local worker uses empty `OSFamily` / `container-image`)
- `lre-cc` / C++ LRE builds as parity target
- `aarch64-darwin` full LRE cold/warm green path (record `environment-blocker.json`)
- Fleet dashboards, queue-time / action-placement correlation
- Claim that remote worker ran in a **different** Nix store than the client

**Proposed claim ceiling:** `lre_cache_parity_observed` (`collectable_v1`, `medium`) — same-host local worker + Nix-generated `lre.bazelrc`, cold `hit_rate` 0 → warm `hit_rate` 1 on `//tasks:priority_test`.

---

## Implementation blueprint (minimal Linux)

Mirror `cold-warm-cache-proof.sh` with these deltas:

```bash
# Env overrides
CONFIG=demo/nativelink/lre.json5
REMOTE_CACHE=grpc://127.0.0.1:50071
REMOTE_EXECUTOR=grpc://127.0.0.1:50071
CACHE_ROOT=/tmp/nlfr-nativelink/lre
OUT=data/lre-cold-warm-proof

# Preconditions (blocker exit 2)
# - nativelink + bazel on PATH (nix develop)
# - lre.bazelrc present (flake installationScript)
# - platform != x86_64-linux → optional blocker or skip with honest reason

# Per leg:
nlfr run \
  --scenario cold-cache|warm-cache \
  --run-group lre-cold-warm \
  --mode local-exec \
  --skip-nativelink \
  --remote-cache grpc://127.0.0.1:50071 \
  --remote-executor grpc://127.0.0.1:50071 \
  --bazel-arg=--config=lre \
  --bazel-startup-arg=--output_base=... \
  //tasks:priority_test
```

Port readiness: poll `127.0.0.1:50071` and `127.0.0.1:50081` (not `50051`/`50061`).

---

## Why not BLOCKER_MANIFEST

| Considered blocker | Verdict |
|--------------------|---------|
| Worker image alignment missing | **Partial** — empty `container-image` blocks *hermetic cross-image* claims, not same-host local-worker `py_test` parity inside `nix develop` |
| Wave-3 incomplete | **False** — `lre_bazelrc_generated` shipped |
| No template for cold/warm ingest | **False** — `cold-warm-cache-proof.sh` is canonical |
| Darwin dev host | **Environmental** — scripts must write `environment-blocker.json`; CI owns green path |
| `local-exec-proof.sh` port bug | **Fixable** in implement scope; not a research stop |

BLOCKER_MANIFEST is reserved if **implement worker** runs green path on `ubuntu-latest` + `nix develop` and Bazel LRE cold/warm still fails after script lands.

---

## Implement worker dispatch

| Worker | Write scope |
|--------|-------------|
| `lre-parity-proof-script` | `scripts/lre-cold-warm-proof.sh`, proof samples |
| `lre-parity-tests` | `tests/test_lre_proof.py`, `docs/proof-samples/README.md` |
| `lre-parity-ci` | `.github/workflows/nlfr-proof.yml` (`lre-cold-warm-ci` job) |
| `lre-parity-handoffs` | `docs/sessions/handoffs/lre-proof/wave-4/**`, `docs/dags/lre-proof.md` |

**Proof gates:**

```bash
uv run pytest tests/test_lre_proof.py -q
bash -n scripts/lre-cold-warm-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh  # x86_64-linux only
```

---

## Claims touched (post-implement)

- **New:** `lre_cache_parity_observed`
- **Preserved:** `lre_substrate_ready`, `lre_bazelrc_generated`
- **Still future:** hermetic container parity, fleet correlation

---

## Critical finding for implement worker

`scripts/local-exec-proof.sh` waits for ports **50051/50061** hardcoded, but `lre.json5` binds **50071/50081**. `lre-proof.sh` delegates to this script — the new `lre-cold-warm-proof.sh` implements its own LRE port readiness rather than reusing that delegation unchanged.
