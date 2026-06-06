# Real NativeLink Toolchain Proof DAG

Linear parent: [PER-1019](https://linear.app/gradschool/issue/PER-1019/nlfr-20-real-nativelink-toolchain-proof)

## Objective

Upgrade NLFR from fixture/blocker evidence to real NativeLink cache and
local-exec proof on a host with Bazel and NativeLink installed.

## Children

- PER-1020: Environment smoke (Nix/devcontainer). **Blocked** on this host — see
  [TOOLCHAIN_ASSESSMENT.md](TOOLCHAIN_ASSESSMENT.md).
- PER-1021: Cold/warm NativeLink cache proof. Blocked by PER-1020.
- PER-1022: Local-exec smoke proof. Blocked by PER-1020.
- PER-1023: Artifact preservation and tryout update.
- PER-1024: Real toolchain completion review.

## Current State

Coordinator takeover (2026-06-06):

- Git baseline reconciled: commit `e1e9070` on `codex/per-998-nlfr-mvp`.
- Knowledge OS project pack: `knowledge-os/projects/nlfr/pack.md`.
- This Mac host lacks Nix, Bazel, NativeLink, and Docker. Real toolchain proof
  scripts record truth-labeled `environment_blocker` evidence.

## Proof Gates

```bash
nix develop  # or devcontainer
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
uv run pytest tests -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh
npm --prefix apps/canvas run capture
```

## Stop Conditions

- Claim worker identity/placement/queue time without direct evidence.
- Hide environment blockers when tools are missing.
- Linear/Git/repo state conflicts would mislead the next agent.
