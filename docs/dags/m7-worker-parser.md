# M7 — One direct worker-evidence parser

Linear: PER-1067 (proposed) · Parent: PER-1058

## Objective

Promote exactly one currently-unsupported remote claim with direct evidence parser + fixture tests.

## Design gate (Wave 2 brief from 1.5)

Pick one claim from worker-readiness `UNSUPPORTED_CLAIMS`. Default lean: worker admin stdout → new proof_block kind.

## Deliverables

- Parser under `src/nlfr/ingest/`
- Projector nodes only when SQLite has direct rows
- `scripts/worker-evidence-proof.sh` + `summary.json`

Blocked by: Wave 1.5 completion.
