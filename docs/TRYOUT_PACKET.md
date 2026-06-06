# NLFR Tryout Packet

Date: 2026-06-06

Linear parent: [PER-1013](https://linear.app/gradschool/issue/PER-1013/nlfr-14-local-remote-execution-worker-proof)

## One-Liner

NativeLink Agent Flight Recorder is a local-first proof recorder for agentic
engineering loops: NativeLink makes repeated validation cheap, fast, and
reproducible; NLFR makes that validation inspectable.

## What This Shows

AI coding agents make code generation abundant. The scarce operational resource
becomes validation: every patch still needs to build, test, reuse prior work,
fail clearly, and leave a trustworthy record.

This repo demonstrates a NativeLink-first answer:

1. Deterministic agents or scenarios create repeatable repo changes.
2. Bazel validates those changes through a NativeLink-backed cache or executor
   path.
3. NLFR captures immutable artifacts, hashes them, and ingests them into
   SQLite.
4. NLFR exports truth-labeled Action Graph, Validation Runway, and Proof Packet
   projections.
5. The canvas renders only those projections, including what remains unproven.

The demo is intentionally worker-first and token-light. It proves the validation
substrate before spending tokens on many real LLM agents.

## NativeLink Surface Area

The current repo covers three NativeLink-adjacent layers:

- Cache-only baseline: prove repeated validation can reuse prior work when
  NativeLink/Bazel are installed, or record a durable blocker when they are not.
- Local remote-executor smoke: prove Bazel was configured with
  `--remote_executor`, capture NativeLink config/readiness evidence, and export
  remote-execution proof blocks.
- Future worker fleet path: keep the model ready for direct worker evidence
  without claiming scheduler assignment, queue time, action placement, worker
  identity, or load distribution prematurely.

On this host, Bazel/Bazelisk and NativeLink are not on PATH. That means the real
tool paths produce truth-labeled `environment_blocker` evidence instead of fake
success.

## Zero-LLM Strategy

The tryout-grade version should use deterministic simulated agents as the
backbone:

- repeatable patches;
- stable build/test workload;
- no token burn for load generation;
- reproducible proof artifacts;
- easy before/after cache and remote-execution comparisons.

One real LLM-generated patch can be added later as a narrative spark, after the
NativeLink worker proof is stable. It should not be the backbone of the demo.

## Operator Experience

The canvas is not a generic dashboard. It is a wide action graph with a small
operator command surface.

The important views are:

- Action Graph: runs, invocations, artifacts, cache/execution evidence, and
  proof blocks.
- Validation Runway: which validations are proven, blocked, failed, or future.
- Proof Packet: claim-by-claim evidence, source kind, confidence, refs, and
  redaction state.
- Remote Boundary: whether remote execution was configured and which worker
  claims remain unsupported.

The Remote Boundary lens is deliberately conservative. It can show that a Bazel
invocation used remote execution configuration and that a NativeLink config
declared worker readiness, but it does not claim direct worker execution until
direct evidence exists.

## Current Proof

Fresh commands from the PER-1018 review pass:

```bash
uv run pytest tests -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh
npm --prefix apps/canvas run capture
```

Observed result:

- Python tests: 41 passed.
- Canvas production build: passed.
- Demo verifier: passed.
- Host real-tool paths: recorded missing Bazel/NativeLink blockers.
- Browser QA: page identity, blank-page, framework overlay, console health,
  remote-lens interaction, operator command, and mobile viewport passed.

Visual proof artifacts:

- `output/playwright/canvas-desktop.png`
- `output/playwright/canvas-proof.png`
- `output/playwright/canvas-remote-boundary.png`
- `output/playwright/canvas-failure-focus.png`
- `output/playwright/canvas-mobile.png`
- `output/playwright/canvas-operator-flow.webm`

## Coordinator Takeover (PER-1019)

Date: 2026-06-06

Cursor coordinator reconciled Git baseline (`e1e9070` on `codex/per-998-nlfr-mvp`),
added Knowledge OS project pack (`knowledge-os/projects/nlfr/pack.md`), and armed
Linear parent [PER-1019](https://linear.app/gradschool/issue/PER-1019) for real
toolchain proof.

Host toolchain assessment ([docs/TOOLCHAIN_ASSESSMENT.md](TOOLCHAIN_ASSESSMENT.md)):

- Nix, Bazel/Bazelisk, NativeLink, and Docker are not on PATH on this Mac host.
- `scripts/cold-warm-cache-proof.sh` recorded `environment_blocker` at
  `data/cold-warm-proof/environment-blocker.json` (missing NativeLink).
- `scripts/local-exec-proof.sh` recorded `worker-readiness.json` and
  `environment_blocker` at `data/local-exec-proof/` (missing NativeLink).

These blockers are valid collectable evidence. Real cache and local-exec proof
require `nix develop` or the devcontainer on a toolchain-ready host. See
[docs/REAL_TOOLCHAIN_DAG.md](REAL_TOOLCHAIN_DAG.md).

## What Remains Unproven

These are explicit follow-ups, not implied claims:

- direct worker identity;
- scheduler assignment;
- queue time;
- action placement;
- load distribution;
- multi-machine worker execution;
- full NativeLink Local Remote Execution on a supported Linux/x86_64-style
  environment.

The next best technical step is to run the Nix/devcontainer path on a host where
Bazel/Bazelisk and NativeLink are installed, then capture a real cold/warm cache
proof and a one-process local remote-executor smoke.

## Why It Fits NativeLink

This is a bet on the validation substrate, not on one vertical app category.

In an AI-heavy engineering org, code generation volume rises. That increases
pressure on build/test infrastructure, cache reuse, remote execution, and proof
of what happened. NativeLink sits underneath that whole loop. NLFR makes that
value visible to platform teams, buyers, investors, and skeptical engineers.

The end-state sentence:

> When AI writes the code, NativeLink makes validating it fast, and NLFR makes
> validating it trustworthy.
