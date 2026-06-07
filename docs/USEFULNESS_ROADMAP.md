# Making NLFR actually useful

← [Docs index](INDEX.md) · [Architecture track](ARCHITECTURE_TRACK.md) ·
[Contributing](CONTRIBUTING.md) · [Implementation DAG (historical)](IMPLEMENTATION_DAG.md)

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

### 4. Comparing run groups (M9 — shipped)

`nlfr compare export|index`, `scripts/compare-proof.sh`, and the canvas compare
lens export `derived_v1` deltas between two SQLite run groups (for example
`record-proof` vs `canvas-dev`). Dimensions include cache economics, proof
status, and `worker_identity_observed` when M7 evidence exists per side.

Compare does **not** invent queue time, placement, or scheduler claims. Retention
is index-only (`compare index` lists run groups; no auto-purge).

### 5. Conditional worker identity (M7 — shipped)

When NativeLink admin stdout is attached pre-ingest, the `worker_admin_stdout`
parser promotes `worker_identity` (`collectable_v1`, `high`). Proof:
`scripts/worker-evidence-proof.sh` → `data/worker-evidence-proof/summary.json`
with `worker_identity_observed: true` on the fixture-replay path.

This is **conditional** — not a blanket remote-execution proof. Without stdout
attachment, worker identity stays unsupported.

### 6. Being honest about remote execution

The MVP shows configuration and endpoint readiness boundaries, while explicitly
refusing unsupported claims:

- scheduler assignment
- action placement
- queue time
- load distribution

Worker identity is **not** in this list when M7 stdout is captured; it is a
separate, conditional claim with its own proof script.

This honesty is product value. It prevents the canvas from becoming a plausible
but false dashboard.

### 7. Serving as a demo/reference kit

The current repo now has:

- [`README.md`](../README.md)
- [`ONE_PAGER.md`](ONE_PAGER.md)
- [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)
- [`WALKTHROUGH.md`](WALKTHROUGH.md)
- [`IMPLEMENTATION_WALKTHROUGH.md`](IMPLEMENTATION_WALKTHROUGH.md)
- [`apps/canvas/README.md`](../apps/canvas/README.md)
- [`proof-samples/`](proof-samples/)
- screenshots and video in [`images/`](images/) and [`media/`](media/)

That makes the MVP legible to a buyer, investor, or skeptical engineer.

## Not useful enough yet

The current MVP is not yet a product someone would run every day because it is
missing adoption, deeper history, workflow integration, and enough direct
evidence for full operator-console claims.

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

### Gap 2: multi-run history (partially closed by M9)

M9 shipped compare export, run-group indexing, and a canvas compare lens.
**V1 retention policy is explicit** (`index_only` discovery, `no_auto_purge`,
`operator_managed` lifecycle) in `src/nlfr/retention_policy.py`, proof packet
`retention` blocks, and `compare index --limit`. Still missing for day-to-day
operator use:

- trends across many runs (not just pairwise compare).
- proof packet history browser.
- agent/change history over time.
- automatic artifact purge / TTL jobs (explicitly out of scope for v1).

Needed next:

- Run-group browser/exporter beyond `compare index`.
- Multi-run projection views.
- Redaction rules beyond the existing truth-label model.

### Gap 3: CI/PR attachment

To be useful in real engineering workflows, proof needs to show up where review
happens.

Needed:

- CI recipe that runs NLFR around Bazel (workflow exists; see M5).
- Generated proof packet artifact in PR comments.
- Markdown PR comment summary.
- Links to JSON projections and artifact manifest.
- Exit-code policy: fail on validation failure, not on unsupported claims.

Do not make unsupported claims look like failures. They are boundary labels.

**Note:** GitHub Actions may be offline — local proof gates substitute per
[GHA offline proof shift](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).
Do not block ship on CI green until workflows recover.

### Gap 4: direct remote-execution evidence (beyond M7)

M7 proves conditional worker identity from admin stdout. Still unproven:

- scheduler assignment events.
- action placement evidence.
- queue timing evidence.
- direct correlation keys between Bazel action and NativeLink execution.
- work distribution across workers.

Until those exist, operator-console remote views stay gated.

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
- diff between two runs (compare lens is a start).
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

- multi-run store/query (M9 index is a foundation).
- run-group browser.
- cache economics over time.
- read-only canvas improvements.
- team workflow exports.

Evidence needed first:

- stable repeated run ingestion.
- more robust run comparison beyond pairwise.
- clear unsupported-claim handling.

Do not build worker dashboards until direct worker/action evidence exists beyond
M7 stdout identity.

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
environment blocker, per the [architecture track](ARCHITECTURE_TRACK.md) ladder.

### M5: Real proof on a clean Linux/x86_64 CI host

Goal: remove the "only works on the author's Mac in Nix" objection.

Status: **landed** — [`.github/workflows/nlfr-proof.yml`](../.github/workflows/nlfr-proof.yml), [`CI_RECIPE.md`](CI_RECIPE.md), [`ADOPTION_GUIDE.md`](ADOPTION_GUIDE.md). CI artifact promotion to [`proof-samples/`](proof-samples/) is **deferred** while GitHub Actions are offline; use local proof gates per [GHA offline proof shift](sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

Deliverables:

- CI job that runs cold/warm and agent-loop proofs on Linux/x86_64.
- Redacted proof samples from that host (pending first sustained green run).
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

Status: **shipped** — `src/nlfr/ingest/worker_admin_stdout.py` promotes
`worker_identity` when admin stdout is attached pre-ingest and regex matches;
`scripts/worker-evidence-proof.sh` → `data/worker-evidence-proof/summary.json`.

Deliverables:

- Parser for NativeLink worker/admin stdout or logs.
- New proof-block kinds backed by SQLite rows.
- Graph nodes only when direct evidence exists.
- Promote exactly one currently-unsupported claim, with fixture tests.

Success test:

Either one stronger remote claim is proven with direct evidence, or the repo
documents exactly why it cannot be yet. **Met:** conditional `worker_identity`
when stdout captured; scheduler/queue/placement remain unsupported.

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

### M9: Multi-run retention and read query

Goal: foundation for operator console or provenance layer forks.

Status: **shipped** — `nlfr compare export|index`, compare projection
(`derived_v1`), canvas compare lens, `scripts/compare-proof.sh`. Retention is
index-only (`index_only`), no auto-purge (`no_auto_purge`), operator-managed
(`operator_managed`); proof packets export a `retention` block.

Deliverables:

- Cross-run indexing and explicit v1 retention policy.
- `nlfr compare export` between two run groups.
- Projection JSON for compare views.
- PR/CI proof attachment recipe (workflow exists; PR comment exporter still open).

Success test:

Compare cold vs warm or before/after an agent patch without inventing queue,
worker placement, or scheduler claims. **Met** for pairwise compare with honest
`derived_v1` dimensions.

## What not to build yet

Do not build these until the evidence spine supports them:

- worker/scheduler dashboard (beyond M7 conditional identity).
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

- Promote Linux CI summaries to `docs/proof-samples/` after GHA green.
- Add a `make demo` or script alias for the no-Nix path.
- Add a proof packet markdown exporter for PR comments.
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

The MVP answers many of these for one local proof path. M9 compare and M7
conditional worker identity close questions 8 and 10 for bounded cases. The
roadmap above is how to make those answers repeatable for real teams.

← [Docs index](INDEX.md)
