# Host Toolchain Assessment

Date: 2026-06-06

Coordinator: Cursor takeover session

## This Host (macOS darwin 25.4.0)

| Tool | Status |
|------|--------|
| Nix | Not on PATH |
| Bazel / Bazelisk | Not on PATH |
| NativeLink / native-link | Not on PATH |
| Docker | Not on PATH |

## Implication

Phase B (real NativeLink toolchain proof) cannot execute on this host without
installing Nix (recommended per `docs/DEV_ENVIRONMENT.md`), enabling Docker for
the devcontainer path, or moving proof to a Linux/WSL2 machine with the toolchain
installed.

Current proof remains fixture-backed and truth-labeled `environment_blocker`
evidence. That is valid evidence, not a failed MVP.

## Recommended Next Host

1. **Nix with flakes** — `nix develop` in this repo provides pinned Bazelisk and
   NativeLink from `flake.nix` (supports `aarch64-darwin`).
2. **Devcontainer** — requires Docker; `.devcontainer/devcontainer.json` enters
   `nix develop` automatically.
3. **Linux/WSL2** — for full LRE and multi-worker experiments later.

## Proof Commands When Ready

```bash
nix develop
uv sync
npm --prefix apps/canvas install
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
```

See Linear parent **NLFR-20 Real NativeLink Toolchain Proof** for the armed DAG.
