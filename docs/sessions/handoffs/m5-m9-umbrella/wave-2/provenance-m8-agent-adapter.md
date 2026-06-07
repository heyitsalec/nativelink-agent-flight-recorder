# Wave 2 M8 Agent Adapter Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Agent:** M8 real agent adapter

## Deliverables

| Path | Purpose |
|------|---------|
| `scripts/record-agent-change.sh` | Thin Cursor/CLI adapter: hashes prompt locally, records via `nlfr run --mode generic` |
| `adapters/cursor/README.md` | Usage guide for Cursor sessions |
| `src/nlfr/commands/generic_run.py` | `--provenance-sidecar` hook writes `agent-provenance.json` + `agent_provenance` proof block |
| `tests/test_record_agent_change.py` | Dry-run smoke, sidecar shape, generic provenance ingest (no live agent) |

## Privacy contract

- Sidecar and exports carry **`model` + `prompt_sha256` only** — mirrors `demo/scenarios/llm-bounded-patch.json`
- Raw prompt never written to artifacts, SQLite, or projection JSON
- Sidecar rejects `agent.prompt` field at load time

## Truth labels

| Leg | `source_kind` | Notes |
|-----|---------------|-------|
| Adapter metadata (script invocation) | `collectable_v1` | `record-agent-change.sh` sidecar |
| Validation command capture | `collectable_v1` | generic run process artifacts |
| Demo simulate scenarios | `simulated_v1` | unchanged; not this adapter |

## Proof matrix

| # | Command | Exit | Result | Key artifacts |
|---|---------|------|--------|---------------|
| 1 | `uv run pytest -q` | 0 | PASS | 58 passed |
| 2 | `./scripts/record-agent-change.sh --dry-run --change-path README.md --model composer-2.5 --prompt-file README.md` | 0 | PASS | stdout JSON with `prompt_sha256`, no raw prompt |

## Summary

M8 adds a real bounded-agent adapter that records Cursor-style edits through generic run with hashed-prompt provenance. Generic run accepts `--provenance-sidecar` to emit `agent-provenance.json` and graph/proof-ready `agent_provenance` blocks at `collectable_v1`.
