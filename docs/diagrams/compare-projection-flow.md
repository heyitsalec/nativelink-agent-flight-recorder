# Compare projection flow

**Caption:** Multi-run compare is a `derived_v1` projection built from two proof packets — not a new truth source. The canvas Compare lens loads `compare-projection.json` only.

```mermaid
flowchart TB
    subgraph left["Left run group"]
        LR["runs + artifacts\nSQLite"]
        LP["proof-packet.json\nleft_run_group"]
        LR --> LP
    end

    subgraph right["Right run group"]
        RR["runs + artifacts\nSQLite"]
        RP["proof-packet.json\nright_run_group"]
        RR --> RP
    end

    subgraph compare["Compare projector — derived_v1"]
        EXP["export_compare_projection()"]
        DIM["dimensions:\n• run counts\n• cache metrics\n• worker identity\n• agent_provenance\n• status delta"]
        LP & RP --> EXP --> DIM
        DIM --> CJ["compare-projection.json"]
    end

    subgraph consume["Canvas Compare lens"]
        LENS["Compare Runs scene\ntest:truth guard"]
        CJ --> LENS
    end

    style compare fill:#e8eef8
    style consume fill:#e8eef8
```

## Honesty notes

| Output | `source_kind` | `confidence` | Claim boundary |
|--------|---------------|--------------|----------------|
| `compare-projection.json` | `derived_v1` | `medium` | Deltas between two exported proof packets |
| Dimension: cache metrics | `derived_v1` | `medium` | Reflects collectable cache blocks in each packet |
| Dimension: worker identity | `derived_v1` | `medium` | Presence/absence only — not placement correlation |
| Dimension: agent_provenance | `derived_v1` | `medium` | Block presence — not raw prompt or model reasoning |
| Compare lens UI | `derived_v1` | `medium` | Renders exported JSON; empty state if file missing |

**Not invented:** cross-run scheduler correlation, queue-time deltas, or fleet placement — compare dimensions mirror what each proof packet already collected.

**Testable commands:**

```bash
python3 -m nlfr compare export \
  --left-run-group <left> \
  --right-run-group <right> \
  --output apps/canvas/public/projections/compare-projection.json
./scripts/compare-proof.sh
./scripts/compare-agent-runs.sh --dry-run
npm --prefix apps/canvas run test:truth
```

**Evidence refs:** `run_group:<left>`, `run_group:<right>`, `src/nlfr/projectors/compare.py`, `apps/canvas/public/projections/compare-projection.json`.
