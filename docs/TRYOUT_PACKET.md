# NLFR Tryout Packet

Date: 2026-06-06 · Tag: `v0.2.0-mvp` · Branch: `main`

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

- **Cache-only baseline:** prove repeated validation can reuse prior work when
  NativeLink/Bazel are installed, or record a durable blocker when they are not.
- **Local remote-executor smoke:** prove Bazel was configured with
  `--remote_executor`, capture NativeLink config/readiness evidence, and export
  remote-execution proof blocks.
- **Future worker fleet path:** keep the model ready for direct worker evidence
  without claiming scheduler assignment, queue time, action placement, worker
  identity globally, or load distribution prematurely.

Outside `nix develop`, Bazel/Bazelisk and NativeLink are not on PATH — real-tool
scripts produce truth-labeled `environment_blocker` evidence instead of fake
success. Inside Nix, the real-toolchain pass proved exit 0 (see Real Toolchain Proof below).

## Milestone proof spine (M7 · M8 · M9 · Tier 1)

| Milestone | Script / artifact | Truth label | Claim boundary |
|-----------|-------------------|-------------|----------------|
| **M7** worker parser | `scripts/worker-evidence-proof.sh` → `data/worker-evidence-proof/summary.json` | `collectable_v1`, `high` when stdout matches | `worker_identity` is **conditional** — promoted only when `nativelink.stdout.txt` is attached pre-ingest and M7 regex matches. Not scheduler, queue, placement, or distribution. |
| **M8** agent adapter | `scripts/record-agent-change.sh`, `scripts/agent-loop-proof.sh` | mixed: `collectable_v1` validation; `simulated_v1` agent leg in bounded loop | `model` + `prompt_sha256` only — never raw prompts. Dry-run and pytest proven; live Cursor session is an operator path, not a ship gate. |
| **M9** multi-run compare | `scripts/compare-proof.sh`, `nlfr compare export` | `derived_v1` | Five-dimension compare across run groups (e.g. record-proof vs canvas-dev). No new fleet claims. |
| **Tier 1** live Bazel | `scripts/tier1-live-bazel-proof.sh` | `collectable_v1`, `high` | Acts 1+2 (`agent-bugfix-1`, `agent-feature-compare`) with `bazel_validated: true` via `cursor_adapter_v1` — not pytest fallback. Samples: [`proof-samples/agent-bugfix-summary.json`](proof-samples/agent-bugfix-summary.json), [`proof-samples/agent-feature-summary.json`](proof-samples/agent-feature-summary.json). |

Redacted JSON for evaluators without Nix: [`proof-samples/README.md`](proof-samples/README.md).

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
Tier 1 live Bazel acts demonstrate the `collectable_v1` adapter path when the
room needs a real agent record — still with hashed prompt provenance only.

## Operator Experience

The canvas is not a generic dashboard. It is a wide action graph with a small
operator command surface.

The important views are:

- **Action Graph:** runs, invocations, artifacts, cache/execution evidence, and
  proof blocks.
- **Validation Runway:** which validations are proven, blocked, failed, or future.
- **Proof Packet:** claim-by-claim evidence, source kind, confidence, refs, and
  redaction state.
- **Remote Boundary:** whether remote execution was configured and which worker
  claims remain unsupported.
- **Compare lens (M9):** `derived_v1` deltas across run groups — projection-only.

The Remote Boundary lens is deliberately conservative. It can show that a Bazel
invocation used remote execution configuration and that a NativeLink config
declared worker readiness, and — when M7 evidence exists — observed worker names.
It does not claim direct scheduler assignment, queue time, or action placement
until direct evidence exists.

## Current Proof

Fresh commands from the completion review pass (no hardcoded test counts — run and
verify locally):

```bash
uv run pytest -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh
npm --prefix apps/canvas run capture
```

Optional milestone proofs (fixture or Nix):

```bash
NLFR_WORKER_EVIDENCE_FIXTURE_ONLY=1 ./scripts/worker-evidence-proof.sh   # M7
./scripts/compare-proof.sh   # M9; needs record-proof + canvas-dev DBs
nix develop --command ./scripts/tier1-live-bazel-proof.sh   # Tier 1
```

Local gates above are the canonical verification; see the README Status
section for current CI state.

Observed expectations (not a substitute for running commands):

- `uv run pytest -q` — all tests pass.
- Canvas production build and demo verifier — pass.
- Bare-host real-tool paths: `environment_blocker` when outside Nix (expected).
- Nix real-tool paths: cold/warm + local-exec exit 0.
- Browser QA: page identity, blank-page, framework overlay, console health,
  remote-lens interaction, operator command, and mobile viewport passed.

Visual proof artifacts:

- `output/playwright/canvas-desktop.png`
- `output/playwright/canvas-proof.png`
- `output/playwright/canvas-remote-boundary.png`
- `output/playwright/canvas-failure-focus.png`
- `output/playwright/canvas-mobile.png`
- `output/playwright/canvas-operator-flow.webm`

## Real Toolchain Proof

Date: 2026-06-06

Recorded after real NativeLink proof inside `nix develop`.

Commit: `635ee36` — Unblock NativeLink 1.3.2 and Bazel 9 proof paths.

| Proof | Result |
|-------|--------|
| `scripts/cold-warm-cache-proof.sh` | Exit 0 — cold `hit_rate` 0.0 / 8.17s vs warm `hit_rate` 1.0 / 5.48s |
| `scripts/local-exec-proof.sh` | Exit 0 — `worker_endpoints_ready` |
| `NLFR_EXPECTED_WORKERS=2 … scripts/local-exec-proof.sh` | Exit 0 — `worker_endpoints_ready`, `expected_workers=2`, `configured_workers=2` |
| `scripts/agent-loop-proof.sh` | Exit 0 — `chain_complete=true` (`agent → change → run → cache`) |

Summaries: `data/cold-warm-proof/summary.json`,
`data/local-exec-proof/summary.json`, `data/local-exec-proof-2w/summary.json`,
`data/agent-loop-proof/summary.json` (all `collectable_v1`). The two-worker run
proves two workers configured AND endpoints opened live — not work distributed
across workers. The agent-loop patch stores a SHA-256 prompt hash only; the raw
prompt is never stored or exported.

Redacted copies: [`proof-samples/`](proof-samples/).

Toolchain: NativeLink 1.3.2, Bazel 9.1.1. Config fix: `cache-only.json` uses
NativeLink 1.3.x `stores` array schema.

See [docs/TOOLCHAIN_ASSESSMENT.md](TOOLCHAIN_ASSESSMENT.md) and
[docs/REAL_TOOLCHAIN_DAG.md](REAL_TOOLCHAIN_DAG.md).

## What Remains Unproven

These are explicit follow-ups, not implied claims:

- scheduler assignment;
- queue time;
- action placement;
- load distribution;
- multi-machine worker execution;
- org-scale history;
- full NativeLink Local Remote Execution on every host shape (see LRE blocker
  samples in [`proof-samples/`](proof-samples/)).

**Worker identity** is not globally proven. It is **conditional** when M7 stdout
is attached and regex matches (`collectable_v1`, `high`). Runs without captured
stdout do not carry this claim.

The next best technical step is full LRE on a supported Linux/x86_64-style host
and direct worker/admin/log evidence (placement, scheduler, queue time, load)
before expanding unsupported claims. The two-worker live endpoint proof,
agent-loop closure, M7 fixture path, M9 compare, and Tier 1 live Bazel acts are
documented above.

Fleet research matrix: [`dags/future-fleet-claims.md`](dags/future-fleet-claims.md) ·
[`proof-samples/fleet-claims-matrix-sample.json`](proof-samples/fleet-claims-matrix-sample.json).

## Why It Fits NativeLink

This is a bet on the validation substrate, not on one vertical app category.

In an AI-heavy engineering org, code generation volume rises. That increases
pressure on build/test infrastructure, cache reuse, remote execution, and proof
of what happened. NativeLink sits underneath that whole loop. NLFR makes that
value visible to platform teams, buyers, investors, and skeptical engineers.

The end-state sentence:

> When AI writes the code, NativeLink makes validating it fast, and NLFR makes
> validating it trustworthy.

## Evaluator quick paths

| Path | Time | What you see |
|------|------|--------------|
| Proof samples only | ~5 min | Redacted `collectable_v1` / `derived_v1` JSON — [`proof-samples/README.md`](proof-samples/README.md) |
| Fixture canvas (no Nix) | ~5 min | Action Graph + Proof Drawer from `simulated_v1` fixtures |
| Real proof (Nix) | ~30+ min | Cold/warm + local-exec + optional Tier 1 summaries under `data/` |

Release hygiene: [`GITHUB_RELEASE.md`](GITHUB_RELEASE.md) · One pager:
[`ONE_PAGER.md`](ONE_PAGER.md).
