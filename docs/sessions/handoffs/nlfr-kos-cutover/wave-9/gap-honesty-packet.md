# Gap honesty packet — `dag:nlfr-flagship` umbrella 1–9

**Date:** 2026-06-06  
**Worker:** `kos-operator-bridge` (W9)  
**Status:** SHIPPED (docs-only honesty sync)  
**Branch:** `feat/docs-wiki-wave2`

This packet is the integrative honesty surface for dag-gui coupling. It does **not** claim
closure on blocked or environment-gated items.

---

## Summary

| Gap | Truth label | Status | Operator action |
|-----|-------------|--------|-----------------|
| GHA offline | `collectable_v1` / `high` (negative) | **OPEN** | Follow [`GHA_RESTORE_RUNBOOK.md`](../../../../GHA_RESTORE_RUNBOOK.md) |
| Fleet parsers blocked | `future` / `unknown` | **BLOCKED** | No implementation DAG; research sync only |
| M8 live Cursor | `collectable_v1` / `high` (blocker) | **OPERATOR-HOST** | Install Cursor CLI; run `agent-live-proof.sh` |
| LRE Linux parity | `collectable_v1` / `medium` (blocker) | **OPERATOR-HOST** | x86_64-linux Nix host; see [`LRE_LINUX_PROOF.md`](../../../../LRE_LINUX_PROOF.md) |

---

## GHA offline {#gha-offline}

| Field | Value |
|-------|-------|
| **Observation** | GitHub Actions workflows non-green / effectively offline (~1 month as of 2026-06-06) |
| **Policy** | [`gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md) |
| **Wave 4 outcome** | `DONE_WITH_CONCERNS` — runbook + promotion matrix shipped; no sustained green run |
| **What we do not claim** | CI Linux cold/warm green, `lre-cold-warm-ci` artifact promotion, tier1-bazel CI badge |

**Local substitute gates:**

```bash
uv run pytest -q
bash -n scripts/*.sh
./scripts/cache-only-ci-gate.sh   # wave 7 target; honest when script lands
```

**Revisit trigger:** first sustained green on `nlfr-proof.yml` or operator declares GHA restored.

**Evidence refs:**

- [`wave-4/integration-brief.md`](../wave-4/integration-brief.md) — concern C-W4-1
- [`docs/proof-samples/CI_PROMOTION_MATRIX.md`](../../../../proof-samples/CI_PROMOTION_MATRIX.md)
- [`docs/GHA_RESTORE_RUNBOOK.md`](../../../../GHA_RESTORE_RUNBOOK.md)

---

## Fleet parsers blocked {#fleet-parsers-blocked}

| Field | Value |
|-------|-------|
| **Policy** | [`AGENTS.md`](../../../../../AGENTS.md) v1 out-of-scope; [`future-execution-ladder.md`](../../../../dags/future-execution-ladder.md) phase-3 blocker |
| **Ceiling** | `worker_endpoints_ready` (configured endpoints) — not placement, queue time, or scheduler correlation |
| **Broker rule** | Reject `coord-fleet-ui` / new parser workers without direct-evidence ingest + SQLite rows + pytest |

**What honesty sync covers (waves 5–9):**

- Research-matrix and ladder rows stay labeled `future` / `blocked`
- dag-gui may show fleet-adjacent nodes as **non-runnable** or link to this packet
- No new `collectable_v1` fleet claims in NLFR repo from bridge wave

**Evidence refs:**

- [`future-fleet-claims.md`](../../../../dags/future-fleet-claims.md)
- [`future-execution-ladder.md`](../../../../dags/future-execution-ladder.md) — worker/scheduler dashboards section
- [`ARCHITECTURE_TRACK.md`](../../../../ARCHITECTURE_TRACK.md) Phase 3 exit criteria

---

## M8 live Cursor {#m8-live-cursor}

| Field | Value |
|-------|-------|
| **Wave** | W2 shipped script path; W5 targets residual live close |
| **Current host** | Integrate broker host — Cursor CLI **not** observed for non-dry-run chain |
| **Honest outcome** | `environment-blocker.json` + blocker sample is valid `collectable_v1` |

**Operator path (when CLI available):**

```bash
./scripts/record-agent-change.sh --dry-run   # regression
./scripts/agent-live-proof.sh                # non-dry-run or honest blocker
uv run pytest tests/test_agent_live_proof.py -q
```

**What we do not claim:**

- `chain_complete=true` from a real Cursor session on every host
- Raw prompt storage (always **blocked**)
- Live LLM reasoning as validation proof

**Evidence refs:**

- [`wave-2/integration-brief.md`](../wave-2/integration-brief.md) — concerns C-W2-1, C-W2-2
- [`adapters/cursor/README.md`](../../../../adapters/cursor/README.md)
- [`docs/proof-samples/agent-live-blocker-sample.json`](../../../../proof-samples/agent-live-blocker-sample.json)

---

## LRE Linux parity {#lre-linux-parity}

| Field | Value |
|-------|-------|
| **Wave** | W3 shipped runbook + blocker sample; W5 targets residual Linux green |
| **Current host** | aarch64-darwin integrate host — `lre_cache_parity_observed` **not** green |
| **Honest outcome** | Darwin `environment-blocker.json` (exit 2) or manual Linux `summary.json` only after real run |

**Operator path (x86_64-linux + Nix):**

```bash
nix develop --command ./scripts/lre-cold-warm-proof.sh
# Promote redacted summary only after real green run
```

**What we do not claim:**

- LRE cold/warm CI green while GHA offline
- Fleet / scheduler / queue-time correlation
- Fabricated parity metrics on Darwin

**Evidence refs:**

- [`wave-3/integration-brief.md`](../wave-3/integration-brief.md) — concerns C-W3-1, C-W3-2
- [`docs/LRE_LINUX_PROOF.md`](../../../../LRE_LINUX_PROOF.md)
- [`docs/proof-samples/lre-cold-warm-proof-linux-manual-sample.json`](../../../../proof-samples/lre-cold-warm-proof-linux-manual-sample.json)

---

## dag-gui display guidance

When Harmony NodeInspector renders `dag:nlfr-flagship` nodes:

| Node prefix | Badge | Handoff |
|-------------|-------|---------|
| `W4-*`, `W7-CACHE-GATE-WF` | `environment` | Link GHA offline section |
| `W5-M8-LIVE`, `W2-AGENT-E2E` | `operator-host` | Link M8 section + wave-2 brief |
| `W5-LRE-LINUX`, `W3-*` | `operator-host` | Link LRE section + wave-3 brief |
| Fleet-adjacent (none seeded) | `blocked` | Link fleet parsers section |

Truth vocabulary on all projected claims: `source_kind`, `confidence`, `evidence_refs`, `redaction_state`.

---

## Cross-wave dependency

Waves 1–4 closed `DONE_WITH_CONCERNS` with inherited GHA deferral. Waves 5–8 may ship independently
with the same honesty posture. Wave 9 bridge **documents** gaps; it does not close them.
