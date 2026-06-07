# T1-BUGFIX fixtures/tests — Provenance

**Worker:** `t1-bugfix-fixtures-tests` (parent broker rescue)  
**Date:** 2026-06-06  
**Status:** `DONE`

## Deliverables

- `tests/fixtures/agent-scenarios/bugfix/`
- `tests/test_tier1_bugfix.py`

## Proof

`uv run pytest tests/test_tier1_bugfix.py -q` — 5 passed

## Kind contract

`cursor_adapter_v1` + `collectable_v1`; prompt hash matches `prompt-bugfix.txt`.
