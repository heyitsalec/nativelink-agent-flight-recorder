# M8 — Real agent adapter (thin, bounded)

Linear: PER-1068 (proposed) · Parent: PER-1058

## Objective

One real Cursor/CLI adapter emitting `model` + `prompt_sha256` provenance (never raw prompt).

## Deliverables

- `adapters/cursor/` or `scripts/record-agent-change.sh`
- Wire to `nlfr run --mode generic` / ingest path
- One real change recorded end-to-end
- `summary.json`

Blocked by: Wave 1.5 completion. Parallel with M7 after 1.5.
