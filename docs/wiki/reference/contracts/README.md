# Reference: JSON contracts

**Quadrant:** Reference · **Audience:** contributors, canvas authors, proof reviewers

These pages document the versioned JSON shapes NLFR exports and ingests. Each
contract is the constraint surface for one step in the evidence-first spine:

1. **Artifact manifest** — immutable files with SHA-256 before ingest.
2. **Proof packet** — structured claims per run group from SQLite.
3. **Canvas projection** — action graph nodes and edges for the UI.
4. **Compare projection** — `derived_v1` deltas across two run groups (M9).

Canonical JSON Schema files live under [`contracts/`](../../../../contracts/).
Projectors that emit projection JSON live under
[`src/nlfr/projectors/`](../../../../src/nlfr/projectors/).

← [Wiki hub](../../README.md) · [Truth labels](../truth-labels.md) · [CLI](../cli.md)

## Contract index

| Contract | `schema_version` | `projection_kind` | Schema file | Projector |
|----------|------------------|-------------------|-------------|-----------|
| [Artifact manifest v1](artifact-manifest-v1.md) | `1` | — | [`artifact_manifest.v1.json`](../../../../contracts/artifact_manifest.v1.json) | [`artifacts.py`](../../../../src/nlfr/artifacts.py) |
| [Proof packet v1](proof-packet-v1.md) | `1` | `proof_packet` | [`proof_packet.v1.json`](../../../../contracts/proof_packet.v1.json) | [`proof.py`](../../../../src/nlfr/projectors/proof.py) |
| [Canvas projection v1](canvas-projection-v1.md) | `1` | `action_graph` | [`canvas_projection.v1.json`](../../../../contracts/canvas_projection.v1.json) | [`graph.py`](../../../../src/nlfr/projectors/graph.py) |
| [Compare projection v1](compare-projection-v1.md) | `1` | `compare` | [`compare_projection.v1.json`](../../../../contracts/compare_projection.v1.json) | [`compare.py`](../../../../src/nlfr/projectors/compare.py) |

## Truth labels on every claim

Every artifact entry, proof block, graph node/edge, and compare dimension carries
four fields (see [truth labels](../truth-labels.md)):

| Field | Purpose |
|-------|---------|
| `source_kind` | How the value entered the system |
| `confidence` | Projector confidence in the label |
| `evidence_refs` | Stable pointers — not raw log bodies |
| `redaction_state` | Privacy posture of the exported span |

Compare projections are always `derived_v1` at the root and per dimension. They
summarize proof packets — they do not invent scheduler or fleet state.

## Export commands

| Output | Command |
|--------|---------|
| Action graph | `python3 -m nlfr graph export --run-group latest` |
| Proof packet | `python3 -m nlfr proof export --run-group latest` |
| Compare (M9) | `python3 -m nlfr compare export --left <group> --right <group>` |

Artifact manifests are written at record time under each run's artifact root as
`artifact_manifest.json`. Ingest reads them idempotently.

## Proof samples and fixtures

Redacted real-run excerpts: [proof samples](../../../proof-samples/README.md).

Fixture-backed shapes for tests and docs:

| Fixture | Contract |
|---------|----------|
| [`tests/fixtures/compare/compare-projection.json`](../../../../tests/fixtures/compare/compare-projection.json) | Compare projection v1 |
| [`tests/fixtures/compare/left-proof.json`](../../../../tests/fixtures/compare/left-proof.json) | Proof packet (left leg) |
| [`tests/fixtures/compare/right-proof.json`](../../../../tests/fixtures/compare/right-proof.json) | Proof packet (right leg) |

## Out of scope

These contracts do **not** define:

- Live scheduler, queue time, or worker placement (remain `future` unless M7 stdout evidence exists).
- Fleet dashboards or OTLP/Jaeger telemetry clones.
- Auth, billing, or multi-tenancy.

## Related

- [Evidence-first architecture](../../explanation/evidence-first-architecture.md)
- [Projection-only canvas](../../explanation/projection-only-canvas.md)
- [Export and compare run groups](../../how-to/export-and-compare-run-groups.md)
- [Compare projection flow diagram](../../../diagrams/compare-projection-flow.md)
