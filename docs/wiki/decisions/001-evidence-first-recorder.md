# ADR 001 — Evidence-first recorder, not UI-first dashboard

**Status:** Accepted  
**Date:** 2026-06-06  
**Gates:** [Architecture track § Truth spine](../../ARCHITECTURE_TRACK.md), [IMPLEMENTATION_DAG](../../IMPLEMENTATION_DAG.md), all projection exporters and `apps/canvas`

← [ADR index](README.md) · [Evidence-first architecture](../explanation/evidence-first-architecture.md)

## Context

Agentic coding increases build and test volume. Teams need inspectable proof of
what ran, what reused cache, and what failed — without trusting a pretty graph or
spelunking unstructured CI logs. NLFR could have shipped as a canvas-first
demo that polled live backends and inferred scheduler state. That path optimizes
for screenshots, not auditability, and invites claims (queue time, placement,
fleet correlation) that the v1 collectors do not capture.

## Decision

NLFR is an **evidence-first recorder**. The canonical flow is fixed and ordered:

1. Run a Bazel workload through a NativeLink-backed mode.
2. Capture immutable artifacts with SHA-256 hashes.
3. Ingest evidence into SQLite with idempotent keys.
4. Export versioned projection JSON (`graph`, `proof`, optional `compare`).
5. Render the sparse TypeScript canvas **from projection JSON only**.

Every projected node, edge, metric, and proof claim carries four truth labels:
`source_kind`, `confidence`, `evidence_refs`, `redaction_state`. The canvas is
a projection of recorded facts; it must not invent backend state or poll live
scheduler APIs for v1.

## Consequences

**Positive:** Operators can diff artifacts, SQLite rows, and JSON exports without
the UI. Skeptics can verify `summary.json` and truth labels independently of
canvas screenshots. Doc and diagram work can cite honest claim boundaries
(`collectable_v1` vs `derived_v1` vs `simulated_v1` vs `future`).

**Trade-offs:** UI richness is intentionally sparse until projections exist.
Features that require live fleet dashboards, OTLP traces, or exact worker/action
correlation stay `future` until direct evidence parsers land — not stubbed in the
canvas. Later development passes must not rewrite this ordering for narrative
convenience.

**Related:** [`AGENTS.md`](../../../AGENTS.md) product rule · [Projection-only canvas](../explanation/projection-only-canvas.md) · [Truth labels](../reference/truth-labels.md)
