# Architecture diagrams

**Audience:** contributors and operators who need a visual map of the evidence-first spine before reading adoption docs or running proof scripts.

**Quadrant:** Explanation (understanding-oriented). Pair with how-to docs (`docs/CI_RECIPE.md`, `docs/WALKTHROUGH.md`) and reference (`docs/wiki/`).

These diagrams describe **recorded facts and projection boundaries** — not live scheduler queues, worker dashboards, or fleet placement. Every caption states which `source_kind` values the diagram may imply.

## Diagram index

| Diagram | File | Primary `source_kind` |
|---------|------|------------------------|
| Evidence loop | [evidence-loop.md](evidence-loop.md) | `collectable_v1` → `derived_v1` |
| Truth label ladder | [truth-label-ladder.md](truth-label-ladder.md) | all four kinds |
| Execution ladder | [execution-ladder.md](execution-ladder.md) | `collectable_v1` per step; `future` above ceiling |
| Agent loop provenance | [agent-loop-provenance.md](agent-loop-provenance.md) | `collectable_v1` chain |
| Compare projection flow | [compare-projection-flow.md](compare-projection-flow.md) | `derived_v1` |
| Canvas projection boundary | [canvas-projection-boundary.md](canvas-projection-boundary.md) | projection JSON only |
| CI proof lane | [ci-proof-lane.md](ci-proof-lane.md) | `collectable_v1` when green; honest blocker otherwise |
| Broker orchestration | [broker-orchestration.md](broker-orchestration.md) | maintainer-only; disjoint `write_scope` + local proof gates |

## Canonical flow (one sentence)

Run Bazel through a NativeLink-backed mode → capture SHA-256 artifacts → ingest SQLite → export versioned projection JSON → render canvas from projection JSON only. See [AGENTS.md](../../AGENTS.md).

## Local proof (GHA offline tolerated)

While GitHub Actions may be non-green, validate diagram claims locally:

```bash
uv run pytest -q
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
./scripts/record-proof.sh
```

See [gha-offline-proof-shift.md](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

---

See docs/diagrams/
