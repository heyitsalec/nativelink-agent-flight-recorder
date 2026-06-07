# Evidence loop

**Caption:** Canonical NLFR spine — from Bazel workload to canvas projection. Steps 1–3 produce `collectable_v1` rows; steps 4–5 produce `derived_v1` projection JSON; the canvas consumes projection only.

```mermaid
flowchart LR
    subgraph collect["1. Collect — collectable_v1"]
        BZ["Bazel workload\n(cache-only / LRE)"]
        NL["NativeLink-backed mode"]
        ART["Immutable artifacts\n+ SHA-256 manifest"]
        BZ --> NL --> ART
    end

    subgraph ingest["2. Ingest — collectable_v1"]
        MAN["Artifact manifest"]
        SQL["SQLite evidence store\nidempotent keys"]
        ART --> MAN --> SQL
    end

    subgraph export["3. Export — derived_v1"]
        GP["Graph projector"]
        PP["Proof packet projector"]
        CP["Compare projector\n(optional)"]
        SQL --> GP & PP & CP
        GP --> GJ["graph-projection.json"]
        PP --> PJ["proof-packet.json"]
        CP --> CJ["compare-projection.json"]
    end

    subgraph consume["4. Consume — derived_v1"]
        CAN["Sparse TypeScript canvas\ntest:truth guard"]
        GJ & PJ & CJ --> CAN
    end

    style collect fill:#e8f4e8
    style ingest fill:#e8f4e8
    style export fill:#e8eef8
    style consume fill:#e8eef8
```

## Honesty notes

| Stage | `source_kind` | `confidence` | Claim boundary |
|-------|---------------|--------------|----------------|
| Bazel + NativeLink capture | `collectable_v1` | `high` when proof script succeeds | Artifacts and hashes only — not scheduler placement |
| SQLite ingest | `collectable_v1` | `high` | Idempotent rows with stable keys; no invented rows |
| Projectors | `derived_v1` | `medium`–`high` | Computed from SQLite; must carry four truth labels |
| Canvas render | `derived_v1` | `medium` | Reads projection JSON files only; never polls live backend |

**Out of scope for this diagram:** worker queue time, action placement, fleet dashboards, OTLP/Jaeger clones. Those require direct evidence parsers before any node appears in projection JSON.

**Testable commands:**

```bash
python3 -m nlfr doctor --mode cache-only
./scripts/record-proof.sh
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
npm --prefix apps/canvas run test:truth
```

**Evidence refs:** `run_group:*`, `artifact:*`, `script:record-proof.sh`, projector output paths under `data/*/projections/`.
