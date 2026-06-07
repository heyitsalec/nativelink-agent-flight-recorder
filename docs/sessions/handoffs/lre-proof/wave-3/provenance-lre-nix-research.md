# Provenance — lre-nix-research (wave-3 input)

**Worker:** `lre-nix-research` (synthesized for flake-wire implement)  
**Wave:** 3  
**Purpose:** Research input for `lre-nix-flake-wire` — TraceMachina Nix LRE flake integration pattern

---

## Source of truth

TraceMachina `nativelink` at pinned rev `946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4` (matches pre-migration `flake.lock`).

Key upstream artifacts:

| Path | Role |
|------|------|
| `flake.nix` | flake-parts root; exports `flakeModules.lre`, `overlays.lre` |
| `local-remote-execution/flake-module.nix` | LRE flake module — `config.lre.installationScript` writes `lre.bazelrc` |
| `templates/bazel/flake.nix` | Minimal consumer pattern for Bazel + LRE |
| `tools/installation-script.nix` | Idempotent repo-root `lre.bazelrc` generator |

---

## Integration pattern (consumer flake)

1. **Inputs:** Pin `nativelink` to explicit rev; `follows` for `flake-parts`, `nixpkgs`, `rust-overlay` from nativelink (avoids duplicate nixpkgs drift).
2. **Outputs:** `flake-parts.lib.mkFlake` with `imports = [ nativelink.flakeModules.lre ]`.
3. **pkgs overlay:** `_module.args.pkgs` with `nativelink.overlays.lre` + `rust-overlay.overlays.default` (required for `pkgs.lre.*`).
4. **LRE config:** Set `lre.Env` from toolchain meta:
   - Linux: `lre-cc.meta.Env ++ lre-rs.meta.Env`
   - Darwin: `lre-rs.meta.Env` only (C++ LRE not on Darwin yet)
5. **Prefix:** Use `prefix = "lre"` so Bazel enables via `--config=lre` (matches NLFR README phase-2 command).
6. **shellHook:** `${config.lre.installationScript}` before other exports — generates/updates `lre.bazelrc` at repo root.

Reference consumer (upstream template):

```nix
imports = [ git-hooks.flakeModule nativelink.flakeModules.lre ];
lre = { inherit (pkgs.lre.lre-cc.meta) Env; };
shellHook = '' ${config.lre.installationScript} '';
```

NLFR extends this with existing devShell packages (nativelink bin, bazel shim, uv, python313, node, jq, etc.) and `NLFR_*` env vars.

---

## Remaining phase-3 gaps (honest)

| Gap | Owner | Notes |
|-----|-------|-------|
| `MODULE.bazel` `@local-remote-execution` dep | separate worker | Required for Bazel to resolve LRE toolchains |
| `.bazelrc` `try-import %workspace%/lre.bazelrc` | separate worker | Wires generated file into Bazel |
| Hermetic cache-hit parity proof | `lre-proof.sh` / pytest | Not claimed by flake-wire alone |
| Linux x86_64 full LRE (lre-cc) | host-dependent | Darwin gets rust-only LRE env |

---

## Claim boundary

**Research enables:** Nix devShell generates `lre.bazelrc` with `--config=lre` flags and nix store PATH pins.

**Does not claim:** End-to-end `bazel --config=lre` cache parity, MODULE.bazel wiring, or fleet correlation.
