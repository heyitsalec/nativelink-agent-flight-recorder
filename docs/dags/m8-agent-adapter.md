# M8 — Real agent adapter (thin, bounded)

Milestone: architecture track M8. Status: **landed**.

## Objective

One real Cursor/CLI adapter emitting `model` + `prompt_sha256` provenance (never raw prompt).

## Deliverables

- `adapters/cursor/` or `scripts/record-agent-change.sh`
- Wire to `nlfr run --mode generic` / ingest path
- One real change recorded end-to-end
- `summary.json`
