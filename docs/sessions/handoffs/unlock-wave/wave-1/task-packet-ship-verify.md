# Unlock wave Wave 1 — Task Packet: ship-verify

## KOS arming (mandatory)

Read before acting: [`../KOS-startup-routing.md`](../KOS-startup-routing.md)

**Role:** worker · **Do not spawn subagents.**

Coordinator: `coord-unlock-ship` · Phase: verify

---

## Task

| Field | Value |
|-------|-------|
| worker_id | `ship-verify` |
| coordinator_id | `coord-unlock-ship` |
| dag_ref | `unlock-wave` / wave-1 |
| objective | Execute parent ship proof gates and record pass counts + stale-doc grep |
| expected_output | Handoff provenance + task packet with proof results |
| repo_path | `/Users/alecbot/Documents/nativelink-agent-flight-recorder` |
| write_scope | `docs/sessions/handoffs/unlock-wave/wave-1/provenance-ship-verify.md`, `task-packet-ship-verify.md` |
| no_touch | `src/**`, `tests/**`, `scripts/**` (execute only) |
| proof_commands | See **Proof results** below |
| privacy_tier | `private_internal` |
| stop_conditions | Any proof command non-zero exit → FAIL |
| return_status | **DONE** |

---

## Proof results (2026-06-06)

```bash
uv run pytest -q
# 92 passed, 1 skipped in 7.80s — exit 0

uv run pytest tests/test_lre_proof.py -q
# 4 passed in 0.19s — exit 0

uv run pytest tests/test_fleet_claims_audit.py -q
# 4 passed in 0.06s — exit 0

bash -n scripts/lre-proof.sh
# exit 0

./scripts/fleet-claims-audit.sh
# exit 0 — claim-matrix.json refreshed
```

| Metric | Count |
|--------|-------|
| `pytest -q` passed | 92 |
| `pytest -q` skipped | 1 |
| `test_lre_proof.py` passed | 4 |
| `test_fleet_claims_audit.py` passed | 4 |
| Shell checks passed | 2 (`bash -n`, fleet audit) |

---

## Stale doc check

```bash
rg "Not proven in NLFR yet" .
```

**1 hit:** `docs/dags/future-execution-ladder.md:17` — ladder sync still required.

---

## Deliverables

- Provenance: `docs/sessions/handoffs/unlock-wave/wave-1/provenance-ship-verify.md`
- This task packet (with embedded results)
