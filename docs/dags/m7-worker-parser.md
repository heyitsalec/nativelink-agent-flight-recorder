# M7 — One direct worker-evidence parser

Milestone: architecture track M7. Status: **landed**.

## Objective

Promote exactly one currently-unsupported remote claim with direct evidence parser + fixture tests.

## Design gate

Pick one claim from worker-readiness `UNSUPPORTED_CLAIMS`. Default lean: worker admin stdout → new proof_block kind.

## Deliverables

- Parser under `src/nlfr/ingest/`
- Projector nodes only when SQLite has direct rows
- `scripts/worker-evidence-proof.sh` + `summary.json`
