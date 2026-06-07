# Unlock wave — wave-1 ship verify provenance

**Worker:** `ship-verify`  
**Coordinator:** `coord-unlock-ship`  
**Date:** 2026-06-06  
**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/lre-fleet-unlocks`  
**Git HEAD:** `e00d057bf41cf480a608ebfcff2dd1d658c410d4`  
**Status:** `DONE`

---

## Executive summary

Ran parent proof gates for unlock-wave wave-1 ship. Full pytest suite, targeted LRE and fleet-claims audit tests, `lre-proof.sh` syntax check, and live `fleet-claims-audit.sh` emission all passed. Grep found one stale ladder doc line still claiming LRE is “Not proven in NLFR yet” — follow-up for `coord-ladder-docs-sync`.

---

## Proof commands (executed)

| Step | Command | Exit | Result |
|------|---------|------|--------|
| 1 | `uv run pytest -q` | 0 | **92 passed**, 1 skipped (7.80s) |
| 2 | `uv run pytest tests/test_lre_proof.py -q` | 0 | **4 passed** (0.19s) |
| 3 | `uv run pytest tests/test_fleet_claims_audit.py -q` | 0 | **4 passed** (0.06s) |
| 4 | `bash -n scripts/lre-proof.sh` | 0 | Syntax OK |
| 5 | `./scripts/fleet-claims-audit.sh` | 0 | `research_only` matrix → `data/fleet-claims-audit/claim-matrix.json` |

**Aggregate pytest passed (deduped suites):** 92 full-suite + 4 LRE + 4 fleet = **100 test outcomes**; unique full run = **92 passed, 1 skipped**.

---

## Fleet audit snapshot

- `status`: `research_only`
- `source_kind`: `derived_v1`
- `confidence`: `high`
- `redaction_state`: `safe`
- Claims emitted: 5 (`worker_identity` conditional; four `out_of_scope` with blockers)

---

## Stale doc grep: `Not proven in NLFR yet`

| File | Line | Note |
|------|------|------|
| `docs/dags/future-execution-ladder.md` | 17 | Still states LRE “Not proven in NLFR yet” while `tests/test_lre_proof.py` and `lre-proof` substrate work exist — **stale**; defer to ladder sync coordinator |

No other matches in repo.

---

## Deliverables

| File | Action |
|------|--------|
| `docs/sessions/handoffs/unlock-wave/wave-1/provenance-ship-verify.md` | Created (this file) |
| `docs/sessions/handoffs/unlock-wave/wave-1/task-packet-ship-verify.md` | Created |
| `data/fleet-claims-audit/claim-matrix.json` | Refreshed by proof run |

---

## Truth labels

| Claim | source_kind | confidence | redaction_state |
|-------|-------------|------------|-----------------|
| Parent pytest gate green | collectable_v1 | high | safe |
| LRE proof tests green | collectable_v1 | high | safe |
| Fleet audit tests + script green | collectable_v1 | high | safe |
| Ladder LRE “not proven” line | derived_v1 | high | safe (doc drift) |

**KOS:** [`../KOS-startup-routing.md`](../KOS-startup-routing.md)
