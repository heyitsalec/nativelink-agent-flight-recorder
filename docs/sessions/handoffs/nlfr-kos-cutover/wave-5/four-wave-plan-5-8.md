# Four-wave plan — NLFR KOS cutover (waves 5–8)

**Date:** 2026-06-06  
**Worker:** `four-wave-planner` (`coord-roadmap`)  
**Branch:** `feat/docs-wiki-wave2`  
**Status:** SHIPPED  
**Canonical DAG:** [`docs/dags/nlfr-kos-roadmap-waves-5-8.md`](../../../../dags/nlfr-kos-roadmap-waves-5-8.md)

---

## Control plane

| Field | Value |
|-------|-------|
| **dag_ref** | `nlfr-flagship` |
| **Authority** | KOS local primary |
| **linear_authority** | `false` |
| **Serve** | `kos serve` (kos-mcp) |
| **Seed** | `tools/orchestrator/scripts/seed_nlfr_flagship_waves_5_8.py` (Knowledge OS) |

PER-* Linear issues are reference mirrors only. Wave authority lives on kos-mcp frontier.

---

## Prerequisite

Waves 1–4 closed `DONE_WITH_CONCERNS` (GHA offline, M8 Cursor blocker, LRE Darwin blocker).
Waves 5–8 do **not** block on full CI restore or fleet parsers.

---

## Wave summary

| # | Wave id | Objective (one line) | Integrate node |
|---|---------|----------------------|----------------|
| 5 | `live-proof-residual` | M8/LRE residual live or honest blocker refresh | `W5-INTEGRATE` |
| 6 | `retention-policy-v1` | Index-only retention policy + `compare index --limit` | `W6-INTEGRATE` |
| 7 | `cache-only-ci-gate` | PR-safe `nlfr doctor --mode cache-only` gate | `W7-INTEGRATE` |
| 8 | `pr-proof-attachment` | Redacted markdown proof summary for PR comments | `W8-INTEGRATE` |

**Continuation:** wave 9 `kos-operator-bridge` (dag-gui coupling) — see canonical DAG § Wave 9.

---

## Handoff index

| Wave | Integration brief |
|------|-------------------|
| 5 | [`integration-brief.md`](integration-brief.md) |
| 6 | [`../wave-6/integration-brief.md`](../wave-6/integration-brief.md) |
| 7 | [`../wave-7/integration-brief.md`](../wave-7/integration-brief.md) |
| 8 | [`../wave-8/integration-brief.md`](../wave-8/integration-brief.md) |

Prior umbrella (waves 1–4): [`../wave-0/four-wave-plan.md`](../wave-0/four-wave-plan.md)
