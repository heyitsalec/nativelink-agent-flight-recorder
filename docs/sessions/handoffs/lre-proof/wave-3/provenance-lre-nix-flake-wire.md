# Provenance — lre-nix-flake-wire

**Worker:** `lre-nix-flake-wire`  
**Wave:** 3  
**Write scope:** `flake.nix`, `flake.lock`  
**Coordinator:** `coord-lre-nix-phase3`

---

## Summary

Migrated NLFR `flake.nix` from plain `outputs` to **flake-parts**, importing TraceMachina `nativelink.flakeModules.lre`. Dev shell `shellHook` now runs `config.lre.installationScript`, which generates repo-root `lre.bazelrc` with `build:lre` Bazel flags. Preserved NLFR devShell packages and env vars (`NLFR_NATIVELINK_BIN`, `NLFR_BAZEL_BIN`, `PYTHONPATH`, `BAZELISK_HOME`). Pinned `nativelink` input to `946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4` (synced with `flake.lock`).

---

## Changes

| File | Change |
|------|--------|
| `flake.nix` | flake-parts + LRE module import; `lre.Env`/`prefix`; shellHook LRE install |
| `flake.lock` | Added `flake-parts`, `rust-overlay` follows; `nixpkgs` follows nativelink; nativelink rev pinned |

---

## Proof commands (worker run)

```bash
nix flake lock
nix develop --command bash -lc 'test -f lre.bazelrc || ls -la'
# exit 0 — lre.bazelrc present with build:lre flags

nix develop --command bash -lc 'command -v nativelink && command -v bazel && python3 --version'
# nativelink + bazel from nix; Python 3.13.12
```

### `lre.bazelrc` sample (first flags)

```
build:lre --define=EXECUTOR=remote
build:lre --extra_execution_platforms=@local-remote-execution//rust/platforms:...
build:lre --extra_toolchains=@local-remote-execution//rust:rust-aarch64-darwin
build:lre --platforms=@local-remote-execution//rust/platforms:aarch64-apple-darwin
```

---

## Honesty ceiling

| Claim | Status | Labels |
|-------|--------|--------|
| Nix devShell generates `lre.bazelrc` | **Proven** (local `nix develop`) | `collectable_v1`, `high` |
| `--config=lre` Bazel cache parity | **Not claimed** — needs `MODULE.bazel` + `.bazelrc` import | `future` |
| Full hermetic LRE on Darwin | **Partial** — rust-only Env (upstream limitation) | `derived_v1`, `medium` |
| `lre_substrate_ready` regression | **Not re-run** — out of write scope | — |

Phase-3 flake wiring unblocks follow-up workers for `MODULE.bazel`, `.bazelrc` try-import, and proof script claim boundary update.

---

## Blockers

None for this worker packet.

---

## Research input

Created `provenance-lre-nix-research.md` (was missing at worker start) from TraceMachina upstream flake + bazel template analysis.
