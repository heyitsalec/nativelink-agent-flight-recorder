# Coordinator charters — Unlock wave

**KOS:** [`../KOS-startup-routing.md`](../KOS-startup-routing.md)

Return `DispatchManifest` JSON only. Write `integration-brief.md` at reflect gates.

---

## coord-lre-proof

**DAG:** `lre-proof` wave-2  
**Deliverables:**

- `demo/nativelink/lre.json5` (dedicated ports 50071/50081)
- `scripts/lre-proof.sh` → `lre_substrate_ready` summary with `claim_boundary`
- `demo/nativelink/README.md` LRE substrate section
- `tests/test_lre_proof.py` — config valid + blocker path
- `.github/workflows/nlfr-proof.yml` — probe expects `summary.json` when config exists
- `docs/proof-samples/lre-proof-summary-sample.json`
- `docs/sessions/handoffs/lre-proof/wave-2/` provenance + spawn ledger

**Proof:** `uv run pytest tests/test_lre_proof.py -q`

**Honesty:** Do not claim hermetic Nix `--config=lre` until flake + MODULE.bazel wired.

---

## coord-future-fleet-claims

**DAG:** `future-fleet-claims` wave-1 (research only)  
**Deliverables:**

- `scripts/fleet_claims_audit.py` + `scripts/fleet-claims-audit.sh`
- `docs/dags/future-fleet-claims.md`
- `tests/test_fleet_claims_audit.py`
- `docs/sessions/handoffs/future-fleet-claims/wave-1/` claim-matrix + integration brief

**Proof:** `./scripts/fleet-claims-audit.sh` + `uv run pytest tests/test_fleet_claims_audit.py -q`

**Broker rule:** No canvas fleet dashboard workers.
