# Canvas projection boundary

**Caption:** The canvas is a read-only consumer of exported projection JSON. It must not invent backend state, poll live schedulers, or treat UI state as source of truth.

```mermaid
flowchart TB
    subgraph truth["Source of truth (not the canvas)"]
        SQL["SQLite evidence store"]
        ART["SHA-256 artifacts"]
        SQL --- ART
    end

    subgraph allowed["Allowed canvas inputs — derived_v1"]
        GJ["graph-projection.json"]
        PJ["proof-packet.json"]
        CJ["compare-projection.json\n(optional)"]
        VS["view-spec.json\n(layout only)"]
    end

    subgraph projectors["Projectors (only writers)"]
        GP["graph projector"]
        PP["proof projector"]
        CP["compare projector"]
        SQL --> GP & PP & CP
        GP --> GJ
        PP --> PJ
        CP --> CJ
    end

    subgraph canvas["Canvas — consume only"]
        TT["test:truth guard\nschema + label checks"]
        REN["Sparse TS render\nnodes / edges / lenses"]
        GJ & PJ & CJ & VS --> TT --> REN
    end

    subgraph forbidden["Forbidden — future / invented"]
        LIVE["Live scheduler API"]
        QUEUE["Queue depth / placement UI"]
        INVENT["Default nodes without projection"]
    end

    forbidden -.->|must not feed| canvas

    style truth fill:#e8f4e8
    style allowed fill:#e8eef8
    style forbidden fill:#f8e8e8
```

## Honesty notes

| Boundary | Rule | `source_kind` on canvas claims |
|----------|------|--------------------------------|
| Input files | Canvas reads projection JSON from `public/projections/` or fetch path only | Inherits `derived_v1` from projectors |
| Truth labels | Every rendered node/edge must expose four fields | Same as projection payload |
| View spec | Layout and lens routing — not evidentiary claims | `derived_v1` or layout metadata; no collectable claims |
| Screenshots / demos | Must come from fixture projection or labeled dry-run | `simulated_v1` when fixture; label explicitly |
| Operator panel | Shows export hints and empty states — not live fleet | `derived_v1` |

**Anti-pattern:** Canvas as source of truth. If a node is visible, it must exist in projection JSON with `evidence_refs` pointing to collectable or derived sources.

**Guard command:**

```bash
npm --prefix apps/canvas run test:truth
```

**Evidence refs:** `apps/canvas/src/App.tsx`, `apps/canvas/src/panels/OperatorPanel.tsx`, `AGENTS.md` product rule, `docs/ARCHITECTURE_TRACK.md` Principle 1 gate "Consume".
