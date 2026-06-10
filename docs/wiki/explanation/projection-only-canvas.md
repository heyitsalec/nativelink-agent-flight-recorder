# Explanation: projection-only canvas

**Quadrant:** Explanation · **Audience:** frontend contributors, demo reviewers

The NLFR canvas is a read-only lens on exported projection JSON. It does not
poll NativeLink, reconstruct scheduler state, or synthesize nodes from narrative.

← [Wiki hub](../README.md) · [Design routing](../../design/routing.md)

## Core rule

From [AGENTS.md](../../../AGENTS.md):

> The canvas is a projection of recorded facts. It must not invent backend state.

If a node is not in `graph-projection.json`, `proof-packet.json`,
`runway-projection.json`, or `compare-projection.json`, it must not appear in the UI.

## Data flow

```text
SQLite (ingested evidence)
        ↓
nlfr graph|proof|runway|compare export
        ↓
apps/canvas/public/projections/*.json
        ↓
Canvas modes (local UI state only)
```

Export commands: [CLI reference](../reference/cli.md).  
Compare path (M9): [export and compare run groups](../how-to/export-and-compare-run-groups.md).

## View spec and modes

Normative routing lives in [design routing](../../design/routing.md) and
[view-spec.v1.schema.json](../../design/view-spec.v1.schema.json).

| Mode | Binding | Primary projection |
|------|---------|-------------------|
| Action Graph | — | `graph-projection.json` |
| Validation Runway | — | `runway-projection.json` |
| Proof Packet | `proof_packet` | `proof-packet.json` |
| Remote Boundary | `proof_packet` (join) | remote section of proof packet |
| Compare Runs | `compare` (optional) | `compare-projection.json` |

Mode switches are **local UI state**. They do not mutate SQLite or re-ingest.

Component inventory: [component catalog](../../design/component-catalog.md).

## Truth labels in the UI

Every rendered node, edge, and metric should surface [truth labels](../reference/truth-labels.md).
Truth-guard tests (`npm --prefix apps/canvas run test:truth`) enforce schema and
visibility — not live backend correctness.

| `source_kind` | UI expectation |
|---------------|----------------|
| `collectable_v1` | Show evidence refs; prefer high-confidence styling |
| `derived_v1` | Label as computed (e.g. compare deltas) |
| `simulated_v1` | Visible fixture/sim banner where applicable |
| `future` | Do not render without explicit fixture |

## What the canvas must not show

- Live worker queues or scheduler assignment (unsupported — [One pager](../../ONE_PAGER.md))
- Raw prompts or env vars (privacy — M8 uses hashes only)
- Dollar savings without artifact-backed economics
- Cross-run worker graph merge (M9 is summary-level `derived_v1` only)

## M9 compare lens

Compare mode loads `compare-projection.json` only. It shows deltas across run
groups — not a unified fleet graph. Dimensions are documented in the
[compare projection contract](../reference/contracts/compare-projection-v1.md).

## M7 / M8 presentation

- **M7:** Worker nodes appear when SQLite has `worker_admin_identity_v1` rows from
  stdout ingest — conditional, not global fleet proof.
- **M8:** Agent nodes derive from `agent_provenance` proof blocks and `changes`
  table — [Cursor adapter](../../../adapters/cursor/README.md).

## Media and demos

Hero GIFs must come from fixture projections or labeled dry-run output —
[Media capture](../../MEDIA_CAPTURE.md). Tier1 and Nix demos export real
projections first, then capture.

## Local proof gates

Canvas build and truth tests are local gates:

```bash
npm --prefix apps/canvas run build
npm --prefix apps/canvas run test:truth
```

## Related

- [Evidence-first architecture](evidence-first-architecture.md)
- [First evidence loop](../tutorial/first-evidence-loop.md)
- [Architecture track § Principle 1](../../ARCHITECTURE_TRACK.md)
