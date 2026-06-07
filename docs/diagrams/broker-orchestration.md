# Broker orchestration

**Caption:** Knowledge OS parent-broker pattern for multi-DAG milestones (e.g. docs excellence, frontier wave). Coordinators return `DispatchManifest` JSON only; workers own disjoint `write_scope` paths. Proof gates at ship are **host-local** when GHA is offline — not live scheduler or fleet claims.

```mermaid
flowchart TB
    subgraph operator["Operator intent"]
        OP["Implement the plan\n(branch + DAG mirror)"]
    end

    subgraph wave0["Wave 0 — ARM"]
        ARM["Parent broker ARM"]
        DAG["DAG mirror\n+ excellence bar / spawn ledger"]
        OP --> ARM --> DAG
    end

    subgraph wave1["Wave 1 — parallel coordinators"]
        C1["coord-readme-flagship"]
        C2["coord-wiki-hub"]
        C3["coord-adoption-paths"]
        C4["coord-diagrams"]
        C5["coord-proof-samples-hub"]
        C6["coord-code-polish"]
        C7["coord-contributing"]
        DAG --> C1 & C2 & C3 & C4 & C5 & C6 & C7
    end

    subgraph workers["Workers — disjoint write_scope"]
        W1["README.md"]
        W2["docs/INDEX.md\n+ docs/wiki/**"]
        W3["ADOPTION_GUIDE\n+ walkthrough suite"]
        W4["docs/diagrams/**"]
        W5["proof-samples hub"]
        W6["src/nlfr/**\ndocstrings only"]
        W7["CONTRIBUTING\n+ roadmap links"]
        C1 --> W1
        C2 --> W2
        C3 --> W3
        C4 --> W4
        C5 --> W5
        C6 --> W6
        C7 --> W7
    end

    subgraph integrate["Wave 1.5–2 — parent integrate"]
        BRIEF["integration brief\n+ link audit"]
        W1 & W2 & W3 & W4 & W5 & W6 & W7 --> BRIEF
    end

    subgraph gates["Wave 3 — proof gates (local when GHA offline)"]
        PG["uv run pytest -q\nbash -n scripts/*.sh\ntest:truth · record-proof"]
        SHIP["ship packet\n+ spawn ledger SHIPPED"]
        BRIEF --> PG --> SHIP
    end

    style wave0 fill:#f5f0e8
    style wave1 fill:#e8eef8
    style workers fill:#e8f4e8
    style gates fill:#f0e8f4
```

## Honesty notes

| Stage | What is orchestrated | What is **not** orchestrated |
|-------|----------------------|------------------------------|
| Parent broker | Parallel doc/code polish sub-DAGs with disjoint paths | Live NativeLink scheduler, worker placement, queue time |
| Coordinators | Spawn workers; collect manifests | Rewrite product truth labels or invent fleet claims |
| Workers | Files in `write_scope` only | Cross-scope edits without parent merge |
| Proof gates | Local pytest, shell syntax, canvas truth tests | Green CI badge as ship blocker while GHA offline |

**Contract:** [broker-dispatch-manifest](https://github.com/heyitsalec/knowledge-os/blob/main/agent-os/harness/broker-dispatch-manifest.md) (Knowledge OS). NLFR mirrors: [`docs/dags/docs-excellence.md`](../dags/docs-excellence.md), handoffs under `docs/sessions/handoffs/`.

**Maintainer-only:** Operators evaluating NLFR proof do not need this diagram. See [Evidence loop](evidence-loop.md) for the product spine.

**Evidence refs:** `docs/sessions/handoffs/docs-excellence/wave-1/integration-brief.md`, `docs/dags/docs-excellence.md`, `docs/sessions/handoffs/docs-excellence/wave-0/broker-arm.md`.
