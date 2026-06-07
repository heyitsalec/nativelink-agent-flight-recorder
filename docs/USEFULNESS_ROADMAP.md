# Making NLFR actually useful

← [Docs index](INDEX.md)

This document answers: what does the MVP do today, what makes it useful, what is
still missing, and what should be built next?

The short answer:

NLFR is currently useful as a credible local proof kit and reference
architecture. It is not yet useful as a day-to-day platform product for a team.
The next work should make it easier to adopt, rerun, compare, and attach proof
to real engineering workflows while preserving the evidence-first spine.

## Useful today

The MVP is already useful for these jobs:

### 1. Proving the evidence path

NLFR proves that a local tool can:

1. Run a Bazel workload through NativeLink-backed modes.
2. Capture artifacts immutably.
3. Hash artifacts with SHA-256.
4. Ingest evidence into SQLite.
5. Export projection JSON.
6. Render a canvas and proof packet from projection JSON only.

That is the spine. It is the hardest part to keep honest.

### 2. Showing cache economics from real evidence

The cold/warm proof shows cache behavior with concrete numbers:

- cold hit rate
- warm hit rate
- cold duration
- warm duration
- hit-rate delta
- duration delta

It does not claim dollars saved or org-wide performance.

### 3. Showing a bounded agent-validation chain

The agent-loop path shows that deterministic agent/change provenance can be
linked to validation/cache evidence:

`agent -> change -> run -> target -> action -> cache_event`

It stores model label and prompt hash only. It does not store raw prompts and
does not call a live LLM.

### 4. Being honest about remote execution

The MVP can show configuration and endpoint readiness boundaries, while
explicitly refusing unsupported claims:

- worker identity
- action placement
- queue time
- scheduler assignment
- load distribution

This honesty is product value. It prevents the canvas from becoming a plausible
but false dashboard.

### 5. Serving as a demo/reference kit

The current repo now has:

- [`README.md`](../README.md)
- [`ONE_PAGER.md`](ONE_PAGER.md)
- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
- [`WALKTHROUGH.md`](WALKTHROUGH.md)
- [`IMPLEMENTATION_WALKTHROUGH.md`](IMPLEMENTATION_WALKTHROUGH.md)
- [`proof-samples/`](proof-samples/)
- screenshots and video in [`images/`](images/)

That makes the MVP legible to a buyer, investor, or skeptical engineer.

## Not useful enough yet

The current MVP is not yet a product someone would run every day because it is
missing adoption, history, workflow integration, and enough direct evidence for
deeper operations claims.

### Gap 1: adoption friction

Today the proof path is repo-specific. A new user needs to understand:

- Nix setup.
- Bazel/NativeLink setup.
- NLFR CLI commands.
- where output goes.
- which proof claims are fixture-backed vs real.

Needed:

- A smaller `nlfr init` path for new repos.
- A documented adapter pattern for existing Bazel monorepos.
- A one-command "record this target" path that produces proof packet + graph.
- Better failure messages when NativeLink/Bazel are missing.

### Gap 2: multi-run history

Today the app is strongest around one run group at a time. A real team needs:

- trends across many runs.
- before/after comparison.
- cache hit-rate over time.
- proof packet history.
- agent/change history.
- artifact retention policy.

Needed:

- Stable run indexing.
- Run-group browser/exporter.
- `nlfr compare` with useful summary output.
- Projection JSON for multi-run views.
- Retention/redaction rules.

### Gap 3: CI/PR attachment

To be useful in real engineering workflows, proof needs to show up where review
happens.

Needed:

- CI recipe that runs NLFR around Bazel.
- Generated proof packet artifact.
- Markdown PR comment summary.
- Links to JSON projections and artifact manifest.
- Exit-code policy: fail on validation failure, not on unsupported claims.

Do not make unsupported claims look like failures. They are boundary labels.

### Gap 4: direct remote-execution evidence

The MVP does not prove worker/action assignment. To make operator-console-style
views useful, NLFR needs direct evidence such as:

- worker logs with stable worker IDs.
- scheduler assignment events.
- action placement evidence.
- queue timing evidence.
- direct correlation keys between Bazel action and NativeLink execution.

Until those exist, the product should keep remote views gated.

### Gap 5: live agent provenance

The current agent loop is deterministic. That is correct for an MVP proof. A
real agent integration would need:

- agent run ID.
- model/provider label.
- prompt/input hash.
- patch hash.
- tool call summary.
- redaction policy.
- optional signed provenance.
- no raw prompt export by default.

The product should still treat agent reasoning as a claim source, not as proof
that validation happened.

### Gap 6: operator ergonomics

The canvas is good enough for a demo. A real operator needs:

- run selector.
- search over evidence refs.
- copyable proof packet.
- "why is this node here?" affordances.
- diff between two runs.
- export/share workflow.
- clear empty states and blocker states.

Keep this read-only. The canvas should not become the source of truth.

## Product-shape fork

Phase 5 remains buyer-signal gated. The three possible shapes are:

### Option A: Reference architecture

Best default right now.

Who it serves:

- NativeLink DevRel.
- investors.
- skeptical engineers.
- early technical buyers.

What to build:

- polished docs.
- adoption guide.
- example repo adapter.
- proof sample packet.
- CI recipe.
- reproducible demo script.

Why first:

It turns the MVP into something another person can understand and rerun without
you narrating it live.

### Option B: Operator console

Build only if platform teams ask for run history and cache economics across a
team.

What to build:

- multi-run store/query.
- run-group browser.
- cache economics over time.
- read-only canvas improvements.
- team workflow exports.

Evidence needed first:

- stable repeated run ingestion.
- more robust run comparison.
- clear unsupported-claim handling.

Do not build worker dashboards until direct worker/action evidence exists.

### Option C: Provenance layer

Build if enterprise/security buyers ask for audit trails.

What to build:

- signed proof exports.
- long-lived provenance history.
- retention/redaction policies.
- machine-readable export API.
- PR/CI proof attachment.

Evidence needed first:

- stronger artifact manifest semantics.
- predictable redaction model.
- versioned schemas.
- optional signature/verification chain.

Do not build multi-tenant SaaS/auth/billing yet unless a buyer specifically
pulls the product there.

## Recommended next milestones

Each milestone should end with a `collectable_v1` `summary.json` or an explicit
environment blocker, per the architecture track ladder.

### M5: Real proof on a clean Linux/x86_64 CI host

Goal: remove the "only works on the author's Mac in Nix" objection.

Status: **landed locally** — [`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml), [`CI_RECIPE.md`](CI_RECIPE.md), [`ADOPTION_GUIDE.md`](ADOPTION_GUIDE.md). Awaiting first green GitHub Actions run to promote CI proof samples.

Deliverables:

- CI job that runs cold/warm and agent-loop proofs on Linux/x86_64.
- Redacted proof samples from that host.
- `docs/CI_RECIPE.md`.
- `docs/ADOPTION_GUIDE.md` for cold evaluators.

Success test:

A skeptic can point at CI artifacts and independently re-derive the same proof
claims without the original builder's machine.

### M6: Default canvas renders a real projection

Goal: close the demo/proof gap where the first screenshots are fixture-backed.

Status: **done** — `canvas-dev` collectable_v1 default; fixture fallback banner in App.tsx; README/WALKTHROUGH callouts.

Deliverables:

- One committed redacted real projection under `apps/canvas/public/projections/`
  or a clearly labeled real-vs-fixture switch in docs.
- README and walkthrough call out which projection is on screen.

Success test:

The first thing an evaluator sees can be `collectable_v1` evidence, not only
`simulated_v1` fixtures.

### M7: One direct worker-evidence parser

Goal: take the first legitimate step into Ring 3 without inventing dashboard
state.

Status: **landed** — `src/nlfr/ingest/worker_admin_stdout.py` promotes `worker_identity` from admin stdout; `scripts/worker-evidence-proof.sh`.

Deliverables:

- Parser for NativeLink worker/admin stdout or logs.
- New proof-block kinds backed by SQLite rows.
- Graph nodes only when direct evidence exists.
- Promote exactly one currently-unsupported claim, with fixture tests.

Success test:

Either one stronger remote claim is proven with direct evidence, or the repo
documents exactly why it cannot be yet.

### M8: One real agent adapter (thin, bounded)

Goal: convert agent-loop framing from aspirational to demonstrated.

Status: **landed** — `scripts/record-agent-change.sh` + `adapters/cursor/README.md`; dry-run proven; full run for operator.

Deliverables:

- Documented Cursor/CLI adapter emitting the same provenance shape as
  `llm-bounded-patch`: model label + prompt hash, never raw prompt.
- One real change recorded through the adapter and validated through NLFR.

Success test:

A non-fixture agent change produces the same graph chain shape as the current
deterministic scenario.

### M9: Multi-run retention and read query (only if pulled)

Goal: foundation for operator console or provenance layer forks.

Status: **landed** — `nlfr compare export|index`, compare projection, canvas compare lens, `scripts/compare-proof.sh`. Retention is index-only (no auto-purge).

Deliverables:

- Cross-run indexing and retention policy.
- `nlfr compare --left A --right B`.
- Projection JSON for compare views.
- PR/CI proof attachment recipe.

Success test:

Compare cold vs warm or before/after an agent patch without inventing queue,
worker, or placement claims.

Do not start M9 until M5–M8 land unless a buyer explicitly pulls for history or
audit features first.

## What not to build yet

Do not build these until the evidence spine supports them:

- worker/scheduler dashboard.
- queue-time charts.
- action-placement map.
- multi-machine fleet claims.
- auth/billing/multi-tenancy.
- OTLP/Jaeger clone.
- live agent cockpit.
- generalized SaaS backend.

Those may become useful later, but building them now would pull the product away
from the proof-first differentiator.

## Practical demo improvements still available

The demo is now presentable. The next polish items should stay small:

- Add a `docs/ADOPTION_GUIDE.md`.
- Add a CI example using fixture mode first.
- Add a `make demo` or script alias for the no-Nix path.
- Add a proof packet markdown exporter.
- Add a README badge or short "proof status" block generated from samples.
- Add a small glossary for truth labels and evidence refs.

## The usefulness bar

NLFR becomes actually useful when a team can answer these questions without
asking the original author:

1. What ran?
2. Did it pass?
3. What cache behavior was observed?
4. What artifacts prove that?
5. What changed?
6. Which agent or scenario authored the change?
7. Which claims are direct, derived, simulated, or future?
8. What remains unsupported?
9. Can I attach this proof to a PR?
10. Can I compare this run to the previous run?

The MVP answers many of these for one local proof path. The roadmap above is how
to make those answers repeatable for real teams.

← [Docs index](INDEX.md)
