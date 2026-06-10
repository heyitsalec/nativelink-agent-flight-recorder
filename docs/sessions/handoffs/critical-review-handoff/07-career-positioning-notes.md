# Career positioning notes — honest portfolio framing

**Audience:** Author preparing for AI/platform engineering interviews  
**Repo:** NativeLink Agent Flight Recorder (NLFR)  
**Tag:** `v0.2.0-mvp` · Branch `feat/docs-wiki-wave2`  
**Not legal advice — engineering honesty for storytelling**

---

## One-line pitch (use verbatim)

> I built a local-first **evidence recorder** for AI-agent validation loops: Bazel + NativeLink produce immutable artifacts, NLFR ingests them into SQLite, exports truth-labeled projection JSON, and a sparse canvas renders **only** what was recorded — with explicit labels for what is proven vs simulated vs future.

---

## What to emphasize (strong, defensible)

### 1. Systems thinking — evidence-first architecture

- Designed the canonical loop **record → ingest → export → project** before UI polish.
- Every node carries `source_kind`, `confidence`, `evidence_refs`, `redaction_state`.
- Proof packet surfaces **unsupported claims** instead of hiding them.
- Good fit for: platform engineering, developer infrastructure, observability-minded AI tooling.

### 2. Integration depth (without claiming you wrote NativeLink)

- Wired **real Bazel** evidence parsers (BEP, execution log, profile) against fixture and live paths.
- Proved **cold/warm cache economics** through NativeLink with measured `hit_rate` and duration deltas.
- Local remote-executor smoke: `worker_endpoints_ready` with honest two-worker endpoint proof.
- Tier1 path: **live agent adapter** (`cursor_adapter_v1`) + **real Bazel validation** (`bazel_validated: true`).
- Good fit for: build systems, remote execution, CI/platform adjacent roles.

### 3. Test and proof discipline

- Pytest suite exercises SQLite, serializers, parsers, projection contracts, canvas truth tests.
- Proof scripts emit `summary.json` with SHA-256 manifests — not screenshot-driven demos.
- GHA-offline policy: local gates documented instead of pretending CI is green.
- Good fit: teams that value operability, SRE-minded platform work, "show me the artifact."

### 4. Frontend with constraints (not generic React)

- Canvas is a **projection consumer** — deliberately no invented scheduler/worker state.
- View composer / view-spec protocol for operator-driven layouts without backend coupling.
- Truth-label legend and mode rail (Action Graph, Proof Packet, Remote Boundary, Compare).
- Good fit: internal tools, devtools, platform UI where correctness > polish.

### 5. Documentation and orchestration maturity

- Diátaxis wiki, ADR-lite, proof-sample honesty hub, broker-coordinated doc waves.
- DAG-tracked milestones (M7 worker parser, M8 agent adapter, M9 compare, Tier1 live Bazel).
- Good fit: tech lead / staff-track conversations about how you ship complex surfaces incrementally.

### 6. Privacy-by-design for agent tooling

- Stores `model` + `prompt_sha256` — never raw prompts in exports.
- Redacted paths in proof samples; blocker JSON as valid negative evidence.
- Good fit: enterprise AI platform, compliance-aware internal agent platforms.

---

## What NOT to claim (common overreach traps)

| Do not say | Say instead |
|------------|-------------|
| "Built a distributed build scheduler" | "Recorded Bazel/NativeLink artifacts and labeled what the recorder actually observed" |
| "Proved work runs on two workers" | "Proved two workers configured and endpoints opened live — not load distribution" |
| "Full agent observability platform" | "Validation-loop recorder with conditional agent provenance via adapter sidecar" |
| "Production-ready fleet dashboard" | "Sparse canvas + proof packet; fleet ops explicitly `future` / unproven" |
| "CI-green production system" | "Local proof lane with honest GHA-offline policy; promotion matrix ready for restore" |
| "Replaced NativeLink" | "Black-box recorder around NativeLink/Bazel — no fork, no patch" |
| "Live LLM agent always proven" | "Bounded loop uses `simulated_v1` agent leg; live Cursor path is operator-gated (M8)" |
| "Worker identity always known" | "M7 promotes identity only when admin stdout attached pre-ingest and regex matches" |
| "Compare proves causality" | "M9 compare is `derived_v1` diff across run groups — no scheduler correlation" |

---

## Role-specific framing

### AI platform / agent infrastructure

**Lead with:** Truth-labeled validation spine for agent-written code; adapter hook (`cursor_adapter_v1`) without storing raw prompts.  
**Show:** Tier1 live Bazel proof samples, agent-loop chain diagram, proof packet unsupported claims.  
**Avoid:** Claiming multi-tenant agent orchestration, billing, auth, or fleet scheduling (all out of v1 scope per `AGENTS.md`).

### Developer platform / build systems

**Lead with:** Bazel evidence ingest, cache economics proof, remote-executor readiness ladder, Nix-pinned toolchain.  
**Show:** `cold-warm-summary.json`, `local-exec-proof` summaries, `nlfr doctor` blocker honesty.  
**Avoid:** Implying LRE Linux parity is green on all hosts (darwin may emit blockers).

### Frontend / devtools

**Lead with:** Projection-only canvas, truth legend, view-spec composer, stable test selectors.  
**Show:** `apps/canvas` truth tests, `tier1-demo` view, hero GIF capture pipeline.  
**Avoid:** Calling it a "real-time build dashboard" — it's a proof inspector.

### Staff / architect interviews

**Lead with:** Explicit claim ladder (`collectable_v1` → `derived_v1` → `simulated_v1` → `future`), gap-honesty packets, broker-coordinated doc DAGs.  
**Show:** `future-fleet-claims.md`, `gap-honesty-packet.md`, ADR 001 evidence-first recorder.  
**Avoid:** Roadmap items presented as shipped (LRE phase 4, fleet parsers, GHA promotion).

---

## Proof artifacts to bring to interviews

| Artifact | Story |
|----------|-------|
| `docs/proof-samples/agent-bugfix-summary.json` | End-to-end: agent change + real Bazel validation |
| `docs/proof-samples/cold-warm-summary.json` | Cache ROI with numbers |
| `docs/proof-samples/compare-summary.json` | Derived compare without fleet claims |
| `docs/media/nlfr-evidence-loop.gif` | Evidence loop narrative (label as curated) |
| `uv run pytest -q` green | Engineering rigor |
| `nlfr doctor --json` outside Nix | Honest negative evidence |

---

## Likely skeptical questions — honest answers

**"Is this production?"**  
MVP / proof recorder for evaluation and dogfooding. No auth, billing, multi-tenancy, or fleet ops UI. Local-first with documented CI restore path.

**"Did you build NativeLink?"**  
No. NLFR records outcomes from Bazel runs configured to use NativeLink cache or local remote execution. Integration, not authorship.

**"How real is the AI agent?"**  
Tier1 uses a real adapter sidecar shape with live Bazel validation. Bounded `agent-loop-proof` uses deterministic patch (`simulated_v1`) to prove the chain without LLM tokens. Live Cursor CLI is an operator path with honest blocker samples.

**"Why should I trust the UI?"**  
Canvas reads committed projection JSON. Truth labels are on every node. Proof packet lists what we refuse to claim.

**"What's the biggest gap?"**  
Scheduler assignment, queue time, action placement, and multi-machine fleet behavior remain unproven. GHA has been offline; proof promotion to CI artifacts is documented but deferred.

---

## Differentiation vs typical portfolio projects

| Typical | NLFR |
|---------|------|
| Chat wrapper + vector DB | Build/evidence spine for code validation |
| Dashboard with mocked backend | UI forbidden from inventing backend state |
| "AI wrote tests" demo | Labeled simulated vs collectable agent legs |
| README claims | Proof samples + scripts with exit codes |

---

## Suggested resume bullets (pick 2–3)

1. Designed and implemented a truth-labeled evidence recorder (Python/SQLite) ingesting Bazel BEP, execution logs, and NativeLink artifacts with idempotent SQLite ingest and SHA-256 manifests.

2. Built a projection-only Action Graph canvas (React/TypeScript) that renders proof packets and compare lenses exclusively from exported JSON, with automated truth-label UI tests.

3. Proved cold/warm NativeLink cache economics and tier1 agent-validation loops with real Bazel, documenting explicit unsupported claims (scheduler, fleet placement) instead of overstating scope.

4. Authored an evidence-first documentation system (Diátaxis wiki, proof-sample hub, ADR-lite) coordinated via broker DAG handoffs with local proof gates during GHA outage.

---

## Tone guidance

- **Confident** about architecture discipline, test coverage, and honest labeling.
- **Humble** about scope boundaries, CI status, and fleet/LRE gaps.
- **Curious** about how this extends inside a larger platform team — not "this replaces your entire infra."

The credibility comes from **what you refuse to claim**, not from demo gloss.
