# Real NativeLink Toolchain Proof DAG

> **Historical snapshot.** This planning doc records real NativeLink
> toolchain proof completion.
> For current product truth and milestone status, use **[ONE_PAGER.md](../ONE_PAGER.md)**
> and **[ARCHITECTURE_TRACK.md](../ARCHITECTURE_TRACK.md)**.
> Deep dives: **[Wiki hub](../wiki/README.md)**.

## Objective

Upgrade NLFR from fixture/blocker evidence to real NativeLink cache and
local-exec proof on a host with Bazel and NativeLink installed.

## Children

- Environment smoke (Nix/devcontainer). **Done**
- Cold/warm NativeLink cache proof. **Done**
- Local-exec smoke proof. **Done**
- Artifact preservation and tryout update. **Done**
- Real toolchain completion review. **Done**

## Result

Completed on 2026-06-06 with commit `635ee36`.

Proof pass (inside `nix develop`):

- NativeLink 1.3.2 + Bazel 9.1.1
- `scripts/cold-warm-cache-proof.sh` — cold + warm exit 0
- `scripts/local-exec-proof.sh` — exit 0, `worker_endpoints_ready`
- Summaries: `data/cold-warm-proof/summary.json`, `data/local-exec-proof/summary.json`

Unsupported claims remain explicit: worker identity is **conditional** on M7
admin stdout; scheduler assignment, queue time, action placement, and load
distribution stay unsupported.

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

- Claim worker identity without M7 admin stdout attachment and regex match.
- Claim placement, queue time, or scheduler assignment without direct evidence.
- Hide environment blockers when tools are missing.
- Linear/Git/repo state conflicts would mislead the next agent.
