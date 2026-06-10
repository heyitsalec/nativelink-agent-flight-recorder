# NLFR Tryout Packet

Date: 2026-06-10 · Tag: `v0.2.0-mvp` (+ two-act spark, receipt lens) · Branch: `main`

Audience: a technical evaluator deciding in one sitting whether NLFR deserves a
deeper look. Every claim below links to committed evidence; nothing asks you to
trust prose. If a claim is unproven, this packet says so.

## One-Liner

NativeLink Agent Flight Recorder is a local-first proof recorder for agentic
engineering loops: NativeLink makes repeated validation cheap, fast, and
reproducible; NLFR makes that validation inspectable.

AI coding agents make code generation abundant. The scarce operational resource
becomes validation: every patch still needs to build, test, reuse prior work,
fail clearly, and leave a trustworthy record. NLFR captures immutable
artifacts, ingests them into SQLite, exports truth-labeled projections, and
renders a canvas from those projections only — including what remains unproven.

## Pick Your Path

| Path | Time | What you verify |
|------|------|-----------------|
| [5 minutes](#5-minute-path--no-clone) | read-only | Two-act story, agent receipts, cache numbers — committed screenshots + redacted proof JSON |
| [30 minutes](#30-minute-path--clone-no-nix) | clone, no Nix | Tests green, demo verifier, canvas rendering the two-act evidence |
| [Deep](#deep-path--nix-real-toolchain) | Nix; ~82 GB first fetch | Real NativeLink cold/warm, local-exec, two-act regeneration, full verifier |

## 5-Minute Path — no clone

1. **Hosted canvas:**
   <https://heyitsalec.github.io/nativelink-agent-flight-recorder/?view=two-act-spark>
   *(live at public release — before the flip, use the screenshots below or the
   30-minute path)*.
2. **Two-act proof JSON:**
   [`proof-samples/two-act-spark-live-summary-sample.json`](proof-samples/two-act-spark-live-summary-sample.json).
   The `checks` block is the story: `act1_validation_red`,
   `act1_red_attributed_to_hidden_target`, `act1_receipt_present`,
   `act2_validation_green`, `act2_warm_cache_hits`,
   `compare_projection_exported` — all `true`. Validation/cache legs are
   `collectable_v1` (real Bazel + NativeLink); the agent legs carry live
   `receipt_verified_v1` receipts (server-resolved `claude-opus-4-8`, session
   id, token usage, response SHA-256). The deterministic-stub variant
   ([`two-act-spark-stub-summary-sample.json`](proof-samples/two-act-spark-stub-summary-sample.json))
   is the zero-token CI mechanics gate.
3. **Cache numbers:**
   [`proof-samples/cold-warm-summary.json`](proof-samples/cold-warm-summary.json)
   — cold 8.17 s at `hit_rate` 0.0 → warm 5.48 s at `hit_rate` 1.0
   (`collectable_v1`, `high`).
4. **Claims ledger:** [`ONE_PAGER.md`](ONE_PAGER.md) — proven vs explicitly
   unproven, on one page.

Committed screenshots (rendered from committed projection JSON, not mockups):

| Frame | What it shows |
|-------|---------------|
| [Act 1 graph + receipt](../apps/canvas/baselines/screenshots/two-act-graph-receipt-badge.png) | Failed agent patch in the Action Graph, receipt badge, receipt pane open |
| [Receipt pane](../apps/canvas/baselines/screenshots/two-act-receipt-pane.png) | CLI version, session, token usage, prompt/response SHA-256, truth labels, evidence refs |
| [Compare provenance card](../apps/canvas/baselines/screenshots/two-act-compare-provenance-card.png) | Act 1 vs act 2 agent provenance in the M9 compare lens |

## 30-Minute Path — clone, no Nix

```bash
git clone https://github.com/heyitsalec/nativelink-agent-flight-recorder.git
cd nativelink-agent-flight-recorder
uv sync
uv run pytest -q                  # expected: 175 passed, 3 skipped
./scripts/verify-demo.sh          # fixture demo gates + canvas build
npm --prefix apps/canvas install
npm --prefix apps/canvas run dev  # http://127.0.0.1:5173/
```

What to check in the canvas:

- `?view=two-act-spark` renders both acts with **STUB RECEIPT** badges from
  the committed projections under `apps/canvas/public/projections/two-act/`.
- The default view banner reads **`canvas-dev`** `collectable_v1` — a real
  record of NLFR building its own GUI, not a fixture.
- Proof Packet entries carry `source_kind`, `confidence`, `evidence_refs`, and
  `redaction_state`; the Remote Boundary lens lists what is *not* claimed.
- The canvas never reads SQLite or invents backend state — projection JSON only.

This path proves mechanics and honesty, not NativeLink performance: Bazel and
NativeLink are not on PATH here, and real-tool scripts record truth-labeled
`environment_blocker` evidence instead of fake success.

## Deep Path — Nix, real toolchain

Requires Nix with flakes (~82 GB disk for the first Bazel fetch); toolchain is
NativeLink 1.3.2 + Bazel 9.1.1. See [`DEV_ENVIRONMENT.md`](DEV_ENVIRONMENT.md).

```bash
nix develop
./scripts/cold-warm-cache-proof.sh
./scripts/local-exec-proof.sh
./scripts/verify-demo.sh
# Two-act mechanics with the deterministic stub agent:
NLFR_SPARK_CLAUDE_BIN=$PWD/scripts/spark-stub-claude.sh \
  NLFR_TWO_ACT_OUTPUT=$PWD/data/two-act-spark-stub \
  NLFR_SPARK_RUN_GROUP_PREFIX=two-act-spark-stub \
  ./scripts/two-act-spark-proof.sh
```

Recorded results from this toolchain (committed, redacted; originally recorded
2026-06-06 at commit `635ee36`):

| Proof | Result |
|-------|--------|
| `scripts/cold-warm-cache-proof.sh` | Exit 0 — cold `hit_rate` 0.0 / 8.17 s vs warm `hit_rate` 1.0 / 5.48 s |
| `scripts/local-exec-proof.sh` | Exit 0 — `worker_endpoints_ready` |
| `NLFR_EXPECTED_WORKERS=2 … scripts/local-exec-proof.sh` | Exit 0 — `worker_endpoints_ready`, `expected_workers=2`, `configured_workers=2` |
| `scripts/agent-loop-proof.sh` | Exit 0 — `chain_complete=true` (`agent → change → run → cache`) |
| `scripts/two-act-spark-proof.sh` (stub CLI) | Exit 0 — act 1 red attributed to hidden target, act 2 green with warm hits, compare exported, prompt-leak scan clean |

The two-worker run proves two workers configured AND endpoints opened live —
not work distributed across workers. Redacted copies of every summary:
[`proof-samples/`](proof-samples/README.md).

**Two-act live:** the committed run IS the live run —
`./scripts/two-act-spark-proof.sh` with an authenticated `claude` CLI, agent
legs `receipt_verified_v1`
([summary](proof-samples/two-act-spark-live-summary-sample.json) ·
[receipt](proof-samples/two-act-spark-live-receipt-sample.json)). On a host
where the CLI cannot authenticate, the same script records an honest
`environment_blocker` instead of faking success
([blocker sample](proof-samples/two-act-spark-live-blocker-sample.json)).

## Agent Receipts — the honesty ladder

Every agent node in a projection carries a receipt provenance badge the canvas
renders directly:

| Badge | Meaning | Status today |
|-------|---------|--------------|
| `receipt_verified_v1` | Parsed live-CLI receipt: server-resolved model, session id, usage, response SHA-256 | Pending the live run |
| `stub_receipt_v1` | Deterministic stub CLI — mechanics proof, never presented as live | The committed two-act run |
| `operator_asserted_v1` | Operator claim without a machine receipt | Supported, labeled as such |

Raw prompts are never stored or exported — receipts carry `prompt_sha256` only,
and an in-script scan gate fails the two-act run if prompt text leaks into any
output artifact.

## Canvas Lenses

The canvas is not a generic dashboard; it is a wide action graph with a small
operator command surface, rendered from projection JSON only:

- **Action Graph:** runs, invocations, artifacts, cache/execution evidence, and
  proof blocks.
- **Two-act spark lens** (`?view=two-act-spark`): act 1 red → act 2 green with
  receipt badges and receipt detail panes.
- **Proof Packet:** claim-by-claim evidence, source kind, confidence, refs, and
  redaction state.
- **Validation Runway:** which validations are proven, blocked, failed, or future.
- **Remote Boundary:** whether remote execution was configured and which worker
  claims remain unsupported.
- **Compare lens (M9):** `derived_v1` deltas across run groups — including
  act 1 vs act 2 agent provenance.

The Remote Boundary lens is deliberately conservative: it shows that a Bazel
invocation used remote-execution configuration and that NativeLink declared
worker readiness — and, only when M7 evidence exists, observed worker names. It
does not claim scheduler assignment, queue time, or action placement.

## Proof Spine (what is proven, by which script)

| Track | Script / artifact | Truth label | Claim boundary |
|-------|-------------------|-------------|----------------|
| Cold/warm cache | `scripts/cold-warm-cache-proof.sh` → [`cold-warm-summary.json`](proof-samples/cold-warm-summary.json) | `collectable_v1`, `high` | Cache economics on a fixture workload; not org-scale benchmarks. |
| **M7** worker parser | `scripts/worker-evidence-proof.sh` | `collectable_v1`, `high` when stdout matches | `worker_identity` is **conditional** — promoted only when `nativelink.stdout.txt` is attached pre-ingest and the M7 regex matches. Not scheduler, queue, placement, or distribution. |
| **M8** agent adapter | `scripts/record-agent-change.sh`, `scripts/agent-loop-proof.sh` | mixed: `collectable_v1` validation; `simulated_v1` agent leg | `model` + `prompt_sha256` only — never raw prompts. |
| **M9** compare | `scripts/compare-proof.sh`, `nlfr compare export` | `derived_v1` | Five-dimension compare across run groups. No new fleet claims. |
| **Tier 1** live Bazel | `scripts/tier1-live-bazel-proof.sh` | `collectable_v1`, `high` | Acts 1+2 with `bazel_validated: true` via `cursor_adapter_v1` — not pytest fallback. Samples: [`agent-bugfix-summary.json`](proof-samples/agent-bugfix-summary.json) · [`agent-feature-summary.json`](proof-samples/agent-feature-summary.json). |
| **Two-act spark** | `scripts/two-act-spark-proof.sh` → [live sample](proof-samples/two-act-spark-live-summary-sample.json) · [stub sample](proof-samples/two-act-spark-stub-summary-sample.json) | live: `collectable_v1` + `receipt_verified_v1` agent legs; stub variant: `simulated_v1` agent leg | Recorded fail→fix under real Bazel + NativeLink with live Claude receipts; the stub variant is the zero-token CI mechanics gate. |

Full catalog with every redacted sample: [`proof-samples/README.md`](proof-samples/README.md).

## What Remains Unproven

These are explicit follow-ups, not implied claims:

- scheduler assignment;
- queue time;
- action placement;
- load distribution;
- multi-machine worker execution;
- org-scale history;
- live-LLM agent receipts (`receipt_verified_v1` — two-act mechanics are
  stub-verified today; live receipts pending);
- full NativeLink Local Remote Execution on every host shape (see LRE blocker
  samples in [`proof-samples/`](proof-samples/README.md)).

**Worker identity** is not globally proven. It is **conditional** when M7 stdout
is attached and the regex matches (`collectable_v1`, `high`). Runs without
captured stdout do not carry this claim.

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

One pager: [`ONE_PAGER.md`](ONE_PAGER.md) · Docs hub: [`INDEX.md`](INDEX.md).
