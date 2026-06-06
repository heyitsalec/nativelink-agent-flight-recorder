# NativeLink Agent Flight Recorder — One Pager

## Thesis

When AI writes the code, NativeLink makes validating it fast, and NLFR makes
validating it trustworthy.

## Problem

Agentic coding multiplies build/test volume. Teams need inspectable proof of what
ran, what reused cache, what failed, and what remains unproven — without
spelunking CI logs.

## Solution

NLFR is a local-first black-box recorder for agent validation loops:

1. Agent or scenario changes a repo.
2. Bazel validates through NativeLink cache or remote execution.
3. NLFR captures immutable artifacts, ingests SQLite, exports truth-labeled JSON.
4. A sparse canvas renders Action Graph, Proof Packet, and Remote Boundary only
   from recorded projections.

## What is proven today (Nix, `635ee36`)

- Cold/warm NativeLink cache proof (exit 0).
- One-process local remote-executor smoke (`worker_endpoints_ready`).
- Two-worker config gate (configuration readiness; not worker placement).
- Deterministic simulated-agent provenance (zero LLM tokens).

## What is explicitly unproven

Worker identity, scheduler assignment, queue time, action placement, load
distribution, multi-machine fleet behavior, org-scale history.

## Evaluator paths

| Path | Time | What you see |
|------|------|--------------|
| Fixture canvas (no Nix) | ~5 min | Action Graph + Proof Drawer from `simulated_v1` fixtures |
| Real proof (Nix) | ~30+ min | Cold/warm + local-exec summaries under `data/` |

## Audience

Platform teams, NativeLink buyers, investors, and skeptical engineers evaluating
agentic validation infrastructure.

## Repo

`/Users/alecbot/Documents/nativelink-agent-flight-recorder` · Branch
`codex/per-998-nlfr-mvp` · Linear PER-1053 vision DAG
