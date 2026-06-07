# Wave 1.5 / 2.5 — Review and reflection gate

Broker-spawned subagents run **after Wave 1** and **after Wave 2** before the next wave starts.

## Parallel review pack

| Subagent | Type | Deliverable |
|----------|------|-------------|
| Vision auditor | `explore` readonly | Built vs [`ONE_PAGER.md`](../ONE_PAGER.md) + [`ARCHITECTURE_TRACK.md`](../ARCHITECTURE_TRACK.md); drift report |
| Ticket/code drift | `explore` readonly | Linear PER-1065–1069 vs repo; requirement gaps |
| E2E verifier | `shell` + `explore` | Full proof matrix in reproducible env; honest blockers |
| Gap fixer | `generalPurpose` | Scoped fixes from audit (parent approves write scope) |
| Integration reflector | `explore` | Learnings → next-wave design brief |

## E2E proof matrix (minimum)

```bash
uv run pytest -q
./scripts/record-proof.sh
./scripts/record-canvas-build.sh
npm --prefix apps/canvas run build
npm --prefix apps/canvas run test:truth
./scripts/verify-demo.sh
# If Nix available:
./scripts/cold-warm-cache-proof.sh
./scripts/agent-loop-proof.sh
```

## Hard gates

- **Wave 2** blocked until Wave 1.5 publishes M7/M8 brief.
- **Wave 3 (M9)** blocked until Wave 2.5 publishes M9 brief.
- **Wave 4** is comprehensive superset of 1.5 + 2.5.

## Output artifacts (file-based handoff)

Per [handoffs README](../sessions/handoffs/README.md):

| Wave | Directory | Key files |
|------|-----------|-----------|
| 1.5 | `docs/sessions/handoffs/m5-m9-umbrella/wave-1.5/` | `provenance-vision-auditor.md`, `provenance-e2e-verifier.md`, `worker-results.json`, `integration-brief.md` |
| 2.5 | `docs/sessions/handoffs/m5-m9-umbrella/wave-2.5/` | same pattern |

Legacy flat files (`wave-1.5-review.md`) optional; prefer tree layout.

Review subagents return paths only in chat. Updated umbrella plan / north-star notes if vision drift found.
