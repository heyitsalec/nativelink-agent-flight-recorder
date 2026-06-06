# Real NativeLink Toolchain Proof DAG

Linear parent: [PER-1019](https://linear.app/gradschool/issue/PER-1019/nlfr-20-real-nativelink-toolchain-proof)

## Objective

Upgrade NLFR from fixture/blocker evidence to real NativeLink cache and
local-exec proof on a host with Bazel and NativeLink installed.

## Children

- PER-1020: Environment smoke (Nix/devcontainer). **Done**
- PER-1021: Cold/warm NativeLink cache proof. **Done**
- PER-1022: Local-exec smoke proof. **Done**
- PER-1023: Artifact preservation and tryout update. **Done**
- PER-1024: Real toolchain completion review. **Done**

## Result

PER-1019 completed on 2026-06-06 with commit `635ee36` on `codex/per-998-nlfr-mvp`.

Proof pass (inside `nix develop`):

- NativeLink 1.3.2 + Bazel 9.1.1
- `scripts/cold-warm-cache-proof.sh` — cold + warm exit 0
- `scripts/local-exec-proof.sh` — exit 0, `worker_endpoints_ready`
- Summaries: `data/cold-warm-proof/summary.json`, `data/local-exec-proof/summary.json`

Unsupported claims remain explicit: worker identity, scheduler assignment, queue
time, action placement, load distribution.

## Proof Gates

```bash
nix develop
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
