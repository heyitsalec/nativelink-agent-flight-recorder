# NativeLink Agent Flight Recorder — One Pager

← [Docs index](INDEX.md)

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

## What is proven today (Nix, tag `v0.2.0-mvp`)

- Cold/warm NativeLink cache proof (exit 0; cold `hit_rate` 0.0 / 8.17s vs warm
  `hit_rate` 1.0 / 5.48s — `collectable_v1`).
- One-process local remote-executor smoke (`worker_endpoints_ready`).
- Two-worker live endpoint readiness in Nix (`worker_endpoints_ready`,
  `expected_workers=2`, `configured_workers=2`, no environment blocker;
  `collectable_v1`). This is two workers configured AND endpoints opened live —
  not work distributed across two workers.
- Worker identity from NativeLink admin stdout when `nativelink.stdout.txt` is
  attached pre-ingest **and** admin lines match the M7 parser (`worker_admin_stdout`,
  `scripts/worker-evidence-proof.sh`, `worker_identity_observed: true`,
  `collectable_v1`, `high`). Observed worker names appear in the action graph —
  not scheduler assignment, queue time, placement, or fleet ops UI.
- Deterministic simulated-agent provenance (zero LLM tokens).
- Agent loop closure: a deterministic bounded-agent patch validates through the chain
  `agent → change → run → target → action → cache_event`
  (`scripts/agent-loop-proof.sh`, `chain_complete=true`). The validation/cache
  leg is `collectable_v1` (ingested Bazel evidence); the `agent` and `change`
  provenance nodes stay `simulated_v1` (deterministic patch, no live LLM). The
  patch carries a `model` label and a SHA-256 prompt hash only — the raw prompt
  is never stored or exported.
- **Two-act live spark with verifiable agent receipts**
  (`scripts/two-act-spark-proof.sh`): a real Claude (server-resolved
  `claude-opus-4-8`) authored a failing patch from an underspecified spec —
  real Bazel through NativeLink caught the hidden requirement (act 1 red,
  attributed to the hidden target, cold cache) — then fixed it from the
  recorder's own failure evidence (act 2 green, warm cache hits). Agent legs
  carry `receipt_verified_v1` receipts: CLI-resolved model id, session id,
  token usage, prompt/response SHA-256 — never the raw prompt
  ([live summary](proof-samples/two-act-spark-live-summary-sample.json)).
- Agent receipt provenance ladder on every agent node: `receipt_verified_v1`
  (parsed live-CLI receipt) > `stub_receipt_v1` (deterministic stub, CI
  mechanics gate) > `operator_asserted_v1` (claim without a receipt).

## What is explicitly unproven

Scheduler assignment, queue time, action placement, load distribution,
multi-machine fleet behavior, org-scale history.

Worker identity is **conditional**, not globally proven: only when NativeLink admin
stdout is attached pre-ingest and M7 regex matches (`collectable_v1`). Runs without
captured stdout or matching lines do not carry this claim. No scheduler/fleet
dashboard UI — queue time, placement, and work distribution remain unproven.

*Research matrix:* [`docs/dags/future-fleet-claims.md`](dags/future-fleet-claims.md) · run `./scripts/fleet-claims-audit.sh` → `data/fleet-claims-audit/claim-matrix.json`.

## Evaluator paths

| Path | Time | What you see |
|------|------|--------------|
| Canvas, no Nix | ~5 min | Default view is `canvas-dev` — a real `collectable_v1` record of NLFR building its own GUI; `?view=two-act-spark` shows the live fail→fix run with `receipt_verified_v1` agent receipts |
| Real proof (Nix) | ~30+ min | Cold/warm + local-exec + two-act summaries under `data/` |

## Audience

Platform teams, NativeLink buyers, investors, and skeptical engineers evaluating
agentic validation infrastructure.

## Repo

[heyitsalec/nativelink-agent-flight-recorder](https://github.com/heyitsalec/nativelink-agent-flight-recorder) ·
Branch `main` · Tag `v0.2.0-mvp` · architecture track M-series

← [Docs index](INDEX.md)
