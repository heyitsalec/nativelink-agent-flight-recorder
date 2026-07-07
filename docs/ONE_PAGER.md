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

- Cold/warm NativeLink cache proof (exit 0; cold `hit_rate` 0.0 / 9.04s vs warm
  `hit_rate` 1.0 / 6.12s — `collectable_v1`; latest CI numbers, recorded by run
  [`28862144465`](https://github.com/heyitsalec/nativelink-agent-flight-recorder/actions/runs/28862144465)
  on `main` under Bazel 7.4.1 in Nix).
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

## Shipped tooling (no Nix required)

These work against any Bazel repo, no NativeLink deployment:

- **`nlfr record -- bazel test //your:target`** — one-command evidence capture on
  any Bazel repo, no NLFR config
  ([how-to](wiki/how-to/record-your-own-build.md)).
- **Independent artifact-integrity verification** — recorded SHA-256 digests
  re-checked and surfaced as an `artifact_verification` rollup in proof packets.
- **in-toto Statement export** — `nlfr proof export --format in-toto` emits an
  unsigned, DSSE-ready in-toto v1 Statement; sign externally with cosign
  ([how-to](wiki/how-to/export-in-toto-attestation.md)). NLFR makes no claim of
  auditor acceptance — it is evidence that plugs into an existing safety case.
- **Contract-enforced projections** — projection JSON shape is CI-gated against
  committed JSON contracts ([contracts](wiki/reference/contracts/README.md)).
- **Verified receipts for the Claude and Gemini CLIs** — the Claude receipt is
  live-proven in the committed two-act run; the Gemini parser is fixture-tested
  (live validation env-gated, pending a host with that CLI).
- **`nlfr db upgrade` / `nlfr db gc`** — schema migration and
  operator-consented evidence retention ([CLI](wiki/reference/cli.md#db-upgrade)).

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

**Primary: the platform engineer on a Bazel-heavy team** (A/V, robotics,
safety-critical) who has to show *what actually ran* when an agent wrote the
code — and needs attestable, truth-labeled evidence rather than a chat
transcript.

Secondary: NativeLink buyers, investors, and skeptical engineers evaluating
agentic validation infrastructure.

## Repo

[heyitsalec/nativelink-agent-flight-recorder](https://github.com/heyitsalec/nativelink-agent-flight-recorder) ·
Branch `main` · Tag `v0.2.0-mvp` · architecture track M-series

← [Docs index](INDEX.md)
