# NLFR documentation index

**Quadrant:** Reference (router) · **Audience:** evaluators, operators, contributors

Start here to route by intent. The root [README](../README.md) is the product
entry; this index is the Diátaxis hub. Deep pages live under
[`docs/wiki/`](wiki/README.md).

## Choose your path

| I want to… | Go to |
|------------|-------|
| Run my first fixture-backed evidence loop (~5 min) | [Tutorial: first evidence loop](wiki/tutorial/first-evidence-loop.md) |
| Run real Nix proof on an independent host (~30+ min) | [Tutorial: first Nix proof](wiki/tutorial/first-nix-proof.md) |
| Export projections or compare run groups (M9) | [How-to: export and compare](wiki/how-to/export-and-compare-run-groups.md) |
| Run the tier1 live Bazel demo | [How-to: tier1 live Bazel](wiki/how-to/run-tier1-live-bazel-demo.md) |
| Look up CLI flags or truth-label fields | [Reference: CLI](wiki/reference/cli.md) · [Truth labels](wiki/reference/truth-labels.md) |
| See which proof script proves what | [Reference: proof scripts matrix](wiki/reference/proof-scripts-matrix.md) |
| Understand why evidence comes before the canvas | [Explanation: evidence-first architecture](wiki/explanation/evidence-first-architecture.md) |
| Understand projection-only canvas rules | [Explanation: projection-only canvas](wiki/explanation/projection-only-canvas.md) |
| See architecture as mermaid diagrams | [Architecture diagrams](diagrams/README.md) |

## Diátaxis quadrants

### Tutorial — learning-oriented, first success

Guided paths that assume little context. Goal: one honest win end-to-end.

- [First evidence loop](wiki/tutorial/first-evidence-loop.md) — fixture canvas, no Nix
- [First Nix proof](wiki/tutorial/first-nix-proof.md) — cold/warm cache economics
- [Walkthrough](WALKTHROUGH.md) — legacy guided tour (adoption paths may overlap)
- [Tryout packet](TRYOUT_PACKET.md) — evaluator quick path when present

### How-to — task-oriented recipes

Solve a specific problem when you already know the goal.

- [Export and compare run groups](wiki/how-to/export-and-compare-run-groups.md) — M9 compare lens
- [Run tier1 live Bazel demo](wiki/how-to/run-tier1-live-bazel-demo.md)
- [Adoption guide](ADOPTION_GUIDE.md) — 5-minute fixture vs 30-minute Nix paths
- [CI recipe](CI_RECIPE.md) — GitHub Actions proof jobs
- [Demo script](DEMO_SCRIPT.md) — Tier 1/2/3 rehearsal paths
- [Dev environment](DEV_ENVIRONMENT.md) — local toolchain setup
- [Media capture](MEDIA_CAPTURE.md) — hero GIF regeneration

### Reference — accurate, complete, constraint-focused

Lookup tables and contracts. No narrative detours.

- [CLI reference](wiki/reference/cli.md)
- [Truth labels](wiki/reference/truth-labels.md)
- [Proof scripts matrix](wiki/reference/proof-scripts-matrix.md)
- [JSON contracts](wiki/reference/contracts/README.md) — artifact manifest, proof packet, canvas, compare (M9)
- [One pager](ONE_PAGER.md) — proven vs unproven claims
- [Design: view routing](design/routing.md) · [view spec schema](design/view-spec.v1.schema.json)
- [Design: component catalog](design/component-catalog.md) · [view composer protocol](design/view-composer-protocol.md)
- [Proof samples](proof-samples/README.md) — redacted `summary.json` excerpts
- [Cursor adapter](../adapters/cursor/README.md) — bounded agent change recording (M8)

### Explanation — understanding-oriented background

Why the system is shaped this way. Not step-by-step commands.

- [Evidence-first architecture](wiki/explanation/evidence-first-architecture.md)
- [Projection-only canvas](wiki/explanation/projection-only-canvas.md)
- [How this repo was built](METHOD.md) — contracts-first, agent-coordinated development
- [Architecture track](ARCHITECTURE_TRACK.md) — L0–L2 spine, milestone gates
- [Usefulness roadmap](USEFULNESS_ROADMAP.md) — MVP scope and next bets
- [Contributing](CONTRIBUTING.md) · [Implementation DAG](IMPLEMENTATION_DAG.md)
- [Architecture diagrams](diagrams/README.md) — mermaid maps with honest `source_kind` captions

## Architecture diagrams

Visual maps of the evidence-first spine and projection boundaries. Pair with
[Explanation](wiki/explanation/evidence-first-architecture.md) pages; diagrams
do not imply live scheduler or fleet state.

| Diagram | Topic |
|---------|-------|
| [Evidence loop](diagrams/evidence-loop.md) | record → ingest → export → canvas |
| [Truth label ladder](diagrams/truth-label-ladder.md) | `source_kind` × confidence × redaction |
| [Execution ladder](diagrams/execution-ladder.md) | cache-only through LRE ceiling |
| [Agent loop provenance](diagrams/agent-loop-provenance.md) | M8 bounded provenance chain |
| [Compare projection flow](diagrams/compare-projection-flow.md) | M9 `derived_v1` compare |
| [Canvas projection boundary](diagrams/canvas-projection-boundary.md) | projection JSON only |
| [CI proof lane](diagrams/ci-proof-lane.md) | CI jobs and local proof gates |

Index: [diagrams/README.md](diagrams/README.md).

## Product anchors

| Doc | Role |
|-----|------|
| [One pager](ONE_PAGER.md) | Thesis, proven claims, explicit unproven boundaries |
| [Architecture track](ARCHITECTURE_TRACK.md) | M1–M4 done; M7/M8/M9 ladder; execution ceiling |
| [AGENTS.md](../AGENTS.md) | Canonical evidence flow and truth-label rules |

## Milestone and frontier pointers

| Track | What it proves | Where to read |
|-------|----------------|---------------|
| **M7** worker identity | Conditional `worker_identity` when admin stdout attached pre-ingest + M7 regex | [Architecture track § Phase 3](ARCHITECTURE_TRACK.md), `scripts/worker-evidence-proof.sh` |
| **M8** agent adapter | Bounded provenance (`model` + `prompt_sha256` only) | [Cursor adapter](../adapters/cursor/README.md), `scripts/record-agent-change.sh` |
| **M9** multi-run compare | `derived_v1` deltas across run groups; compare lens | [How-to: export and compare](wiki/how-to/export-and-compare-run-groups.md), `scripts/compare-proof.sh` |
| **Tier1 live Bazel** | Acts 1+2 with real Bazel via `tier1-agent-demo.sh` | [How-to: tier1](wiki/how-to/run-tier1-live-bazel-demo.md), `scripts/tier1-live-bazel-proof.sh` |
| **LRE proof** | LRE substrate, Nix toolchain, cold/warm parity (x86_64-linux) | [Dev environment § LRE](DEV_ENVIRONMENT.md#lre-proof-ladder), `scripts/lre-cold-warm-proof.sh` |
| **Fleet evidence v1** | Stdout ingest breadth for M7 parser; not fleet dashboards | [future fleet claims](dags/future-fleet-claims.md), [proof scripts matrix](wiki/reference/proof-scripts-matrix.md) |

## Canonical evidence flow

Every operator-facing doc should preserve this order (from [AGENTS.md](../AGENTS.md)):

1. Run a Bazel workload through a NativeLink-backed mode.
2. Capture immutable artifacts with SHA-256 hashes.
3. Ingest evidence into SQLite.
4. Export versioned projection JSON.
5. Render the canvas from projection JSON only.

## Local proof gates

Host-local verification gates:

```bash
uv run pytest -q
bash -n scripts/*.sh
```

Optional when Nix is available: `nix develop --command ./scripts/lre-proof.sh`.

## Milestone planning records

Short planning records for shipped milestones live under
[`docs/dags/`](dags/README.md). How this repo was built:
[METHOD.md](METHOD.md).

## Wiki hub

Full quadrant map and cross-links:
[`docs/wiki/README.md`](wiki/README.md).
