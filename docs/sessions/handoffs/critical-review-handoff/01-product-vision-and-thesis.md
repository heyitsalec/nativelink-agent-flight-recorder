# Product vision and thesis

← [00-executive-summary.md](00-executive-summary.md) · [README](README.md)

---

## Problem

Agentic coding multiplies build and test volume. Teams validating AI-generated changes face:

- Truth scattered across chat threads, CI logs, cache behavior, and memory.
- Pressure to **trust** green checks without inspectable artifacts.
- Remote execution products that are easy to **over-interpret** (scheduler fantasy UIs).

NLFR targets the gap between "Bazel passed" and "here is labeled proof of what ran, what reused
cache, what failed, and what we cannot yet prove."

---

## Solution shape

NLFR is a **local-first black-box recorder** for agent validation loops:

```text
Agent/scenario changes repo
        ↓
Bazel validates via NativeLink (cache or local-exec path)
        ↓
NLFR captures immutable artifacts (BEP, stdout, profile, execution log, NL config/logs)
        ↓
SHA-256 manifest → SQLite ingest (idempotent, truth-labeled rows)
        ↓
Projection JSON + proof packet export
        ↓
Sparse canvas renders Action Graph, Proof Packet, Remote Boundary, Compare — projection only
```

**Product rule (non-negotiable):** Build an evidence-first recorder, not a UI-first dashboard.
The canvas must not invent backend state. See [AGENTS.md](../../../../AGENTS.md).

---

## NativeLink showcase demo

### Fit narrative

NLFR does **not** patch NativeLink or replace its scheduler/worker UI. It wraps the stack teams
already use:

| NativeLink story | NLFR contribution |
|------------------|-------------------|
| Faster validation via cache | Cold/warm `collectable_v1` economics in proof samples |
| Remote execution readiness | Endpoint readiness + conditional worker identity (M7) |
| Enterprise trust | Truth labels, proof packets, redacted public samples |
| Agentic future | Agent-loop graph linking change → validation → cache event |

**Recommended demo:** [docs/DEMO_SCRIPT.md](../../../DEMO_SCRIPT.md) **Tier 2** (~15 min) for
NativeLink team — canvas preview, proof-samples JSON, explicit unproven list, optional Tier 3 Nix.

**Closing line (approved):** "When AI writes the code, NativeLink makes validating it fast, and NLFR
makes validating it trustworthy — with every claim labeled by how it was proven."

### What the demo must never imply

- Work distributed across a worker fleet (two-worker proof = endpoints ready only).
- Scheduler assignment, queue time, or placement maps.
- Live LLM reasoning stored or exported (prompt hash + model label only).
- Dollars saved or org-wide performance (cache deltas are local measured facts).

---

## Truth labels as product feature

Honesty is not disclaimers buried in README — it is structural:

| Label | Meaning |
|-------|---------|
| `collectable_v1` | Direct artifact or process output captured by recorder |
| `derived_v1` | Computed from ingested evidence (e.g. compare deltas, profile metrics) |
| `simulated_v1` | Fixture or deterministic scenario (no live LLM / no live Bazel) |
| `future` | Roadmap capability without evidence |

Every projected node, edge, metric, and proof claim also carries `confidence`, `evidence_refs`, and
`redaction_state`. Privacy rule: no secrets, raw prompts, or private logs in public exports.

This model exists because **plausible false dashboards** are the main competitor to NLFR's value.

---

## Usefulness today vs tomorrow

From [docs/USEFULNESS_ROADMAP.md](../../../USEFULNESS_ROADMAP.md):

### Useful today

1. Proving the full evidence path end-to-end.
2. Showing cache economics from real evidence (Nix path).
3. Showing bounded agent-validation chain (with label discipline).
4. Pairwise run compare (M9) without fleet claims.
5. Conditional worker identity when stdout evidence exists (M7).
6. Demo/reference kit for buyers, investors, skeptical engineers.

### Not useful enough yet

1. **Adoption friction** — partially addressed by `nlfr init` (wave 11); still Nix/Bazel literacy.
2. **Multi-run trends** — index + pairwise compare only; no operator history browser at scale.
3. **CI/PR attachment** — workflow + markdown exporter exist; GHA offline blocks sustained proof.
4. **Direct RBE evidence** — beyond M7 stdout identity.
5. **Live agent provenance** — adapter exists; operator-host gated.
6. **Full operator console** — ergonomics shipped (wave 13); fleet UI explicitly blocked.

### Product-shape fork (default recommendation)

**Option A: Reference architecture** — best default now. Polished docs, adoption guide, proof
samples, reproducible demo. Turns MVP into something others can rerun without the author narrating.

Options B (operator console) and C (provenance/audit layer) require more direct evidence first.

---

## Career and AI-job goals framing (honest)

### What NLFR demonstrates

| Signal | Evidence in repo |
|--------|------------------|
| Systems thinking | Evidence spine, SQLite schema, idempotent ingest, versioned projections |
| Agentic infra | Broker waves, KOS `dag:nlfr-flagship`, handoff discipline |
| Build/remote exec domain | Bazel parsers, NativeLink cache/LRE scripts, truth-labeled remote boundary |
| Frontend restraint | Canvas reads JSON only; truth tests + Playwright |
| Technical writing | Diátaxis wiki, ONE_PAGER, DEMO_SCRIPT, proof-samples hub |
| Integrity under hype | Gap honesty packet, fleet claims audit, explicit `future` labels |

### What NLFR does not demonstrate (yet)

- Running a production SaaS or multi-tenant platform.
- Shipping fleet scheduler dashboards with correlated worker/action evidence.
- Sustained CI green on Linux x86_64 (blocked externally).
- Commercial traction, revenue, or team adoption metrics.
- Full live agent integration on every developer machine.

### How to talk about it in interviews

**Strong framing:** "I built an evidence contract layer for agent validation loops on top of Bazel
and NativeLink — every UI claim is backed by `source_kind` and fixture or Nix proof scripts."

**Weak framing:** "I built an AI devops platform with worker dashboards and fleet observability."

The first is accurate. The second is what the codebase **refuses** to claim.

### Portfolio positioning

- **Primary:** Reference implementation + demo kit for NativeLink-aligned platform story.
- **Secondary:** Personal lab showing broker-orchestrated multi-wave delivery (KOS CP).
- **Tertiary:** Foundation if a buyer later pulls toward operator console or provenance layer —
  only after evidence ladder extends.

---

## Audience map

| Audience | Entry path | Success criterion |
|----------|------------|-------------------|
| Quick evaluator | README Path A, Tier 1 demo | Understands truth labels in 5 min |
| NativeLink team | DEMO_SCRIPT Tier 2 | Sees cache proof + honesty without Rust |
| Skeptical engineer | pytest + proof-samples + ONE_PAGER | Can re-derive claims without author |
| Investor / buyer | ONE_PAGER + hero GIFs | Understands wedge (trust layer), not TAM fantasy |
| Contributor | AGENTS.md + ARCHITECTURE_TRACK | Can extend parsers without breaking labels |

---

## Vision guardrails (for reviewers)

Approve direction if:

- New features add **collectable** or **derived** evidence, or document blockers honestly.
- Canvas changes remain projection-only.
- Public repo stays credential-free and fixture-safe.

Challenge or reject if:

- UI implies scheduler/queue/placement without new parsers and tests.
- Compare or history features invent correlation across workers.
- Docs outrun proof scripts or pytest coverage.
- "Ship" depends on CI green while GHA is offline without local gate equivalence.

---

← [00-executive-summary.md](00-executive-summary.md) · Next: [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md)
