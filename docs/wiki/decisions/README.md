# Architecture decisions (ADR-lite)

**Quadrant:** Explanation · **Audience:** contributors and maintainers

Short records for significant choices that affect operators or contributors.
Each ADR uses **context → decision → consequences** (roughly 3–10 sentences per
section). Product truth labels and evidence boundaries still govern all prose.

← [Wiki hub](../README.md) · [Architecture track](../../ARCHITECTURE_TRACK.md) · [Evidence-first architecture](../explanation/evidence-first-architecture.md)

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [001](001-evidence-first-recorder.md) | Evidence-first recorder, not UI-first dashboard | Accepted |

## When to add an ADR

Add a new numbered ADR when a choice:

- Gates implementation work tracked in [`IMPLEMENTATION_DAG.md`](../../IMPLEMENTATION_DAG.md) or [`ARCHITECTURE_TRACK.md`](../../ARCHITECTURE_TRACK.md)
- Changes operator expectations (CLI, proof scripts, canvas contract)
- Establishes a documentation pattern reused across milestones

Skip ADRs for routine typo fixes or single-file refactors.

## Format

```text
# ADR NNN — Title

Status: Proposed | Accepted | Superseded by NNN

## Context
## Decision
## Consequences
```

Link new ADRs from this index and from the architecture track when the decision
gates downstream work.
