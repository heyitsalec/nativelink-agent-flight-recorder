# Provenance — lre-wave3-handoffs

**Worker:** `lre-wave3-handoffs`  
**Wave:** 3  
**Write scope:** `docs/sessions/handoffs/lre-proof/wave-3/**`, `docs/dags/lre-proof.md`, parent spawn ledger  
**Status:** `DONE`

---

## Executive summary

Closed wave-3 broker handoffs after five implement workers landed: research, flake-wire, bazel-wire, nix-proof, nix-ci. Updated spawn ledger, `worker-results.json`, `integration-brief.md`. Synced `docs/dags/lre-proof.md` ceiling from `lre_substrate_ready`-only to phase-2 `lre_bazelrc_generated`.

---

## Deliverables written

| File | Action |
|------|--------|
| `docs/sessions/handoffs/lre-proof/wave-3/spawn-ledger.md` | Updated — all workers DONE |
| `docs/sessions/handoffs/lre-proof/wave-3/worker-results.json` | Created |
| `docs/sessions/handoffs/lre-proof/wave-3/integration-brief.md` | Created |
| `docs/sessions/handoffs/lre-proof/spawn-ledger.md` | Updated — wave-3 DONE |
| `docs/dags/lre-proof.md` | Updated — `lre_bazelrc_generated` ceiling |
| This file | Created |

---

## Proof

```bash
grep -n 'lre_bazelrc_generated' docs/dags/lre-proof.md
uv run pytest tests/test_lre_proof.py -q
# 7 passed
```

---

## Claims touched

- `lre_bazelrc_generated` — DAG and handoff docs only (documentation sync)

## Blockers

None.
