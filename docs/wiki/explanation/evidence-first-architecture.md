# Explanation: evidence-first architecture

**Quadrant:** Explanation · **Audience:** architects, buyers, skeptical engineers

NLFR is a recorder, not a dashboard. The architecture optimizes for immutable
artifacts and honest projections before any UI narrative.

← [Wiki hub](../README.md) · [Architecture track](../../ARCHITECTURE_TRACK.md) · [One pager](../../ONE_PAGER.md)

## The problem

Agentic coding increases build and test volume. Teams need inspectable proof of
what ran, what hit cache, what failed, and what remains unproven — without
spelunking CI logs or trusting a pretty graph.

## Canonical flow

From [AGENTS.md](../../../AGENTS.md):

```text
Bazel workload (NativeLink-backed mode)
        ↓
Immutable artifacts (SHA-256 manifest)
        ↓
SQLite ingest (idempotent keys)
        ↓
Versioned projection JSON
        ↓
Canvas (sparse, projection-only)
```

Skipping ingest or letting the canvas invent nodes breaks the sound track.

## L0–L2 spine vs L3–L4 surface

| Layer | Role | NLFR components |
|-------|------|-----------------|
| L0 | Toolchain proof | Nix, `demo/nativelink/`, proof scripts |
| L1 | Collect + normalize | Artifact manifest, parsers, SQLite |
| L2 | Project | `graph`, `proof`, `runway`, `compare` exporters |
| L3 | Consume | `apps/canvas` — reads JSON only |
| L4 | Package | Docs, README, tryout paths |

[Architecture track](../../ARCHITECTURE_TRACK.md) runs three parallel tracks:

- **A — Truth spine:** protect L1–L2
- **B — Toolchain proof:** deepen L0
- **C — Tryout surface:** explain without rewriting proof

Never let C claim what B did not collect.

## Milestone ladder (what each ring adds)

| Milestone | Proves | Status |
|-----------|--------|--------|
| M1 | Tryout packaging | done |
| M2 | Cold/warm cache metrics in proof JSON | done |
| M3 | Two-worker live endpoint readiness | done |
| M4 | Bounded agent loop closure | done |
| M7 | Conditional worker identity from admin stdout | done |
| M8 | Real agent adapter metadata (no raw prompts) | done |
| M9 | Multi-run compare (`derived_v1`) | done |

Each milestone ends with `summary.json` + pytest — not slides.

## Execution ladder (remote leg)

Strict ordering from [Architecture track § Phase 3](../../ARCHITECTURE_TRACK.md):

```text
1-worker endpoints ready
        ↓
2-worker live endpoints
        ↓
M7 stdout ingest + worker identity (conditional)
        ↓
Action placement / scheduler / queue (only with direct evidence)
        ↓
Multi-machine LRE / fleet
```

NLFR does not skip rungs. [future fleet claims](../../dags/future-fleet-claims.md)
lists unsupported claim types.

## Frontier tracks (not alternate spines)

| Track | Adds to spine | Does not add |
|-------|---------------|--------------|
| LRE proof | LRE substrate + cache parity probes | Fleet UI |
| Fleet evidence v1 | Stdout breadth for M7 | Scheduler claims |
| Tier1 live Bazel | Live Bazel demo acts | Compare / LRE |

## Truth labels as architecture gate

Every projected claim carries `source_kind`, `confidence`, `evidence_refs`,
`redaction_state`. See [truth labels reference](../reference/truth-labels.md).

Promotion rules:

- `collectable_v1` requires parser + artifact
- `derived_v1` requires upstream collectable inputs
- `simulated_v1` for fixtures and deterministic demos only
- `future` for roadmap claims without parsers

## Anti-tracks

Out of v1 scope per [AGENTS.md](../../../AGENTS.md):

- SaaS, auth, billing, multi-tenancy
- Worker/scheduler dashboards inventing queue time
- OTLP/Jaeger clones
- Canvas as source of truth
- Fleet correlation without direct evidence

## Related

- [Projection-only canvas](projection-only-canvas.md)
- [Proof scripts matrix](../reference/proof-scripts-matrix.md)
- [Design routing](../../design/routing.md)
- [Cursor adapter](../../../adapters/cursor/README.md) — M8 reference architecture

## Maintainer-only

Broker handoffs document wave integration — not operator prerequisites:
[Docs index § Maintainer-only](../../INDEX.md#maintainer-only-broker-handoffs).
