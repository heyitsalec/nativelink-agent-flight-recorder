# Provenance — lre-parity-handoffs

**Worker:** `lre-parity-handoffs`  
**Wave:** 4  
**Write scope:** `docs/sessions/handoffs/lre-proof/wave-4/**`, `docs/dags/lre-proof.md`, parent spawn ledger  
**Status:** `DONE`

---

## Executive summary

Closed wave-4 broker handoffs after implement workers landed: research, proof-script (upstream), tests, ci, handoffs. Updated spawn ledger, `worker-results.json`, `integration-brief.md`. Synced `docs/dags/lre-proof.md` ceiling from `lre_bazelrc_generated` to phase-4 `lre_cache_parity_observed`. Extended `demo/nativelink/README.md` with phase-4 section.

---

## Deliverables written

| File | Action |
|------|--------|
| `docs/sessions/handoffs/lre-proof/wave-4/spawn-ledger.md` | Created |
| `docs/sessions/handoffs/lre-proof/wave-4/worker-results.json` | Created |
| `docs/sessions/handoffs/lre-proof/wave-4/integration-brief.md` | Created |
| `docs/sessions/handoffs/lre-proof/spawn-ledger.md` | Updated — wave-4 DONE |
| `docs/dags/lre-proof.md` | Updated — `lre_cache_parity_observed` ceiling |
| `demo/nativelink/README.md` | Updated — phase-4 cold/warm section |
| This file | Created |

---

## Proof

```bash
grep -n 'lre_cache_parity_observed' docs/dags/lre-proof.md
uv run pytest tests/test_lre_proof.py -q
# 9 passed
bash -n scripts/lre-cold-warm-proof.sh
```

---

## Claims touched

- `lre_cache_parity_observed` — DAG and handoff docs only (documentation sync)

## Blockers

None.

---

## JSON envelope

```json
{
  "worker_id": "lre-parity-handoffs",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-4/",
  "artifacts": {
    "provenance": "provenance-lre-parity-handoffs.md",
    "created": [
      "docs/sessions/handoffs/lre-proof/wave-4/spawn-ledger.md",
      "docs/sessions/handoffs/lre-proof/wave-4/worker-results.json",
      "docs/sessions/handoffs/lre-proof/wave-4/integration-brief.md"
    ],
    "updated": [
      "docs/sessions/handoffs/lre-proof/spawn-ledger.md",
      "docs/dags/lre-proof.md",
      "demo/nativelink/README.md"
    ]
  },
  "claims_touched": ["lre_cache_parity_observed"],
  "claim_ceiling": "lre_cache_parity_observed",
  "blockers": []
}
```
