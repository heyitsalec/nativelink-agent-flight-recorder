# NLFR wiki hub

**Quadrant:** Reference (hub) · **Audience:** evaluators, operators, contributors

The wiki organizes NativeLink Agent Flight Recorder documentation using
[Diátaxis](https://diataxis.fr/): four quadrants for four intents. Pick the
quadrant that matches what you are trying to do — not what you think you should
read first.

← [Docs index](../INDEX.md) · [One pager](../ONE_PAGER.md) · [Architecture track](../ARCHITECTURE_TRACK.md) · [Diagrams](../diagrams/README.md)

## Quadrant map

| Quadrant | Intent | Start here |
|----------|--------|------------|
| **Tutorial** | First successful run, learning-oriented | [First evidence loop](tutorial/first-evidence-loop.md) |
| **How-to** | Task recipe for a known goal | [Export and compare run groups](how-to/export-and-compare-run-groups.md) |
| **Reference** | Accurate lookup, constraints | [CLI](reference/cli.md) · [Truth labels](reference/truth-labels.md) |
| **Explanation** | Background and design rationale | [Evidence-first architecture](explanation/evidence-first-architecture.md) |

## Tutorials

| Page | Time | Outcome |
|------|------|---------|
| [First evidence loop](tutorial/first-evidence-loop.md) | ~5 min | Fixture-backed graph + proof from `simulated_v1` / `collectable_v1` mix |
| [First Nix proof](tutorial/first-nix-proof.md) | ~30+ min | Cold/warm cache economics in `data/cold-warm-proof/summary.json` |

Also see [Walkthrough](../WALKTHROUGH.md) and [Adoption guide](../ADOPTION_GUIDE.md)
for overlapping evaluator paths.

## How-to guides

| Page | Milestone |
|------|-----------|
| [Adopt existing Bazel monorepo](how-to/adopt-existing-bazel-monorepo.md) | Wave 11 — `nlfr init` + one-command record |
| [Export and compare run groups](how-to/export-and-compare-run-groups.md) | M9 — `derived_v1` compare projection |
| [Browse run history](how-to/browse-run-history.md) | W12 — multi-run `run_history` projection |
| [Compare runs](compare-runs.md) | Alias → export and compare (README entry point) |
| [Run tier1 live Bazel demo](how-to/run-tier1-live-bazel-demo.md) | Tier1 Acts 1+2 with live Bazel |

Related operator docs: [CI recipe](../CI_RECIPE.md), [Demo script](../DEMO_SCRIPT.md),
[Dev environment](../DEV_ENVIRONMENT.md), [Media capture](../MEDIA_CAPTURE.md).

## Reference

| Page | Contents |
|------|----------|
| [CLI](reference/cli.md) | `nlfr doctor`, `run`, `graph export`, `proof export`, `compare` |
| [Truth labels](reference/truth-labels.md) | Four required fields on every projected claim |
| [Proof scripts matrix](reference/proof-scripts-matrix.md) | Script → claim → artifact path |
| [JSON contracts](reference/contracts/README.md) | Artifact manifest, proof packet, canvas projection, compare projection (M9) |

External reference anchors:

- [One pager](../ONE_PAGER.md) — proven vs unproven boundaries
- [Proof samples](../proof-samples/README.md) — redacted JSON without Nix
- [Cursor adapter](../../adapters/cursor/README.md) — M8 bounded agent recording
- [Design: routing](../design/routing.md) — canvas mode lenses and bindings

## Explanation

| Page | Topic |
|------|-------|
| [Evidence-first architecture](explanation/evidence-first-architecture.md) | Why record → ingest → export → canvas |
| [Projection-only canvas](explanation/projection-only-canvas.md) | Why the UI never invents backend state |

Background: [Architecture track](../ARCHITECTURE_TRACK.md), [Usefulness roadmap](../USEFULNESS_ROADMAP.md).

## Architecture diagrams

Mermaid maps with honest claim boundaries (`collectable_v1`, `derived_v1`, `future`).
Full index: [diagrams/README.md](../diagrams/README.md).

| Diagram | Pair with |
|---------|-----------|
| [Evidence loop](../diagrams/evidence-loop.md) | [Evidence-first architecture](explanation/evidence-first-architecture.md) |
| [Truth label ladder](../diagrams/truth-label-ladder.md) | [Truth labels](reference/truth-labels.md) |
| [Execution ladder](../diagrams/execution-ladder.md) | [Proof scripts matrix § LRE](reference/proof-scripts-matrix.md#lre-proof-ladder) |
| [Agent loop provenance](../diagrams/agent-loop-provenance.md) | [Cursor adapter](../../adapters/cursor/README.md) |
| [Compare projection flow](../diagrams/compare-projection-flow.md) | [Export and compare](how-to/export-and-compare-run-groups.md) |
| [Canvas projection boundary](../diagrams/canvas-projection-boundary.md) | [Projection-only canvas](explanation/projection-only-canvas.md) |
| [CI proof lane](../diagrams/ci-proof-lane.md) | [CI recipe](../CI_RECIPE.md) |

## Frontier tracks (pointers)

| Track | Wiki entry | DAG mirror |
|-------|------------|------------|
| M7 worker identity | [Proof scripts matrix](reference/proof-scripts-matrix.md#m7-worker-evidence) | [Architecture track § Phase 3](../ARCHITECTURE_TRACK.md) |
| M8 agent adapter | [Cursor adapter](../../adapters/cursor/README.md) | [Architecture track § Phase 4](../ARCHITECTURE_TRACK.md) |
| M9 compare | [Export and compare](how-to/export-and-compare-run-groups.md) | [m5-m9-umbrella DAG](../dags/m5-m9-umbrella.md) |
| Tier1 live Bazel | [Run tier1 demo](how-to/run-tier1-live-bazel-demo.md) | [tier1-live-bazel DAG](../dags/tier1-live-bazel.md) |
| LRE proof | [Proof scripts matrix § LRE](reference/proof-scripts-matrix.md#lre-proof-ladder) | [lre-proof DAG](../dags/lre-proof.md) |
| Fleet evidence v1 | [Proof scripts matrix § Fleet](reference/proof-scripts-matrix.md#fleet-evidence-v1) | [fleet-evidence-v1 DAG](../dags/fleet-evidence-v1.md) |

## GHA offline

GitHub Actions may be non-green. Prefer local proof gates:

```bash
uv run pytest -q
bash -n scripts/*.sh
```

See [GHA offline proof shift](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Maintainer-only

Broker handoffs under [`docs/sessions/handoffs/`](../sessions/handoffs/README.md)
are for coordinator maintainers — not required for operators. See
[Docs index § Maintainer-only](../INDEX.md#maintainer-only-broker-handoffs).
