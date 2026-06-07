# Wave 2 Integration Brief — agent-provenance-live

**Date:** 2026-06-06  
**Worker:** `waves-1-4-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Prerequisite:** Wave 1 `W1-INTEGRATE` done

---

## Wave-2 coordinators

| Coordinator | Worker | KOS node | Status | Summary |
|-------------|--------|----------|--------|---------|
| `coord-agent-live-e2e` | `agent-live-e2e` | `W2-AGENT-E2E` | SHIPPED | `scripts/agent-live-proof.sh` — live wrapper over `record-agent-change.sh`; dry-run + honest blocker path |
| `coord-agent-proof-samples` | `agent-proof-samples` | `W2-AGENT-PROOF` | SHIPPED | `agent-live-blocker-sample.json`, `agent-live-summary-sample.json`; pytest fixtures |
| `coord-agent-adapter-docs` | `agent-adapter-docs` | `W2-ADAPTER-DOCS` | SHIPPED | `adapters/cursor/README.md` — live E2E runbook, scope boundary, Cursor CLI prerequisites |
| `w2-integrate` | `waves-1-4-integrate-close` | `W2-INTEGRATE` | DONE | This brief, spawn ledger, worker-results, KOS close |

---

## Landed deliverables

| Layer | Artifacts |
|-------|-----------|
| Live proof script | `scripts/agent-live-proof.sh` |
| Proof samples | `docs/proof-samples/agent-live-blocker-sample.json`, `agent-live-summary-sample.json` |
| Tests | `tests/test_agent_live_proof.py`, `tests/test_agent_live_proof_samples.py` |
| Adapter docs | `adapters/cursor/README.md` |

---

## Remaining concerns

| ID | Gap | Severity |
|----|-----|----------|
| C-W2-1 | **Cursor CLI unavailable** on host — live non-dry-run chain not observed; blocker sample is honest `collectable_v1` outcome | P1 |
| C-W2-2 | `chain_complete=true` from real Cursor session unsupported until CLI installed | P1 |
| C-W2-3 | GHA offline — dry-run path is local CI substitute | inherited |

---

## Proof (local — GHA offline)

```bash
./scripts/agent-live-proof.sh --dry-run
./scripts/record-agent-change.sh --dry-run
uv run pytest tests/test_agent_live_proof.py tests/test_agent_live_proof_samples.py -q
# 10 passed, 1 skipped at integrate close
```

---

## Honesty / claim boundary

**Supported now:**

- Dry-run adapter contract via `agent-live-proof.sh --dry-run`
- `collectable_v1` sidecar shape (model + `prompt_sha256` only)
- Honest environment-blocker when Cursor CLI missing

**Unsupported until Cursor CLI:**

- Live non-dry-run adapter invocation
- `chain_complete=true` from real session

---

## Handoff index

- Spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Worker results: [`worker-results.json`](worker-results.json)
