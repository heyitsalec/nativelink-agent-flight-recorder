# M8 E2E run provenance (wave-2)

- **Date:** 2026-06-06
- **Branch:** `feat/m5-m9-umbrella`
- **Scenario / run group:** `agent-change`
- **Change path:** `docs/M8_E2E_MARKER.md`
- **Model:** `composer-2.5`
- **Prompt file:** `README.md` (hashed only; `prompt_sha256=917ae32f1e248c9ebca349d0e85741147559062e940ea9ddbf3f294758b43288`)

## Commands

```bash
./scripts/record-agent-change.sh \
  --change-path docs/M8_E2E_MARKER.md \
  --model composer-2.5 \
  --prompt-file README.md \
  --command "uv run pytest tests/test_record_agent_change.py -q --tb=no"

PYTHONPATH=src uv run python -m nlfr graph export \
  --db data/agent-change-proof/nlfr.sqlite \
  --run-group agent-change \
  --output data/agent-change-proof/projections/action-graph.json

PYTHONPATH=src uv run python -m nlfr proof export \
  --db data/agent-change-proof/nlfr.sqlite \
  --run-group agent-change \
  --output data/agent-change-proof/projections/proof.json
```

## Outcome

- **Run ID:** `run_07d0c4e74edd2396d639ccf4`
- **Validation status:** `completed`
- **Summary path:** `data/agent-change-proof/summary.json`
- **Truth labels:** `source_kind=collectable_v1`, `confidence=high`, `redaction_state=safe`
- **Agent source kind:** `collectable_v1`

## Agent chain (projection)

Latest run agent node in `action-graph.json`:

- `agent:proof_blocks_fa9171835bcf6110a77eede4` — label `cursor-agent-change`, `source_kind=collectable_v1`

Graph totals for run group `agent-change`: 27 `agent` nodes, 27 runs (includes prior local attempts in `data/agent-change-proof/`).

## Notes

- E2E execution required a **local-only** fix to `scripts/record-agent-change.sh` `mktemp` suffix (`.json` after `XXXXXX` caused sidecar collisions with in-run pytest dry-run tests). That script change was **not** committed; only this provenance file and `docs/M8_E2E_MARKER.md` are committed per scope.
- `data/` artifacts remain untracked/uncommitted.
