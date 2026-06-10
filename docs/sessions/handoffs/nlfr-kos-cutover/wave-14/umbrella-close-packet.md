# Umbrella close packet — `dag:nlfr-flagship` waves 1–13

**Date:** 2026-06-07  
**Worker:** `waves-10-13-integrate-close`  
**Status:** DONE_WITH_CONCERNS  
**Branch:** `feat/docs-wiki-wave2`  
**Authority:** KOS local primary (`kos serve`, `linear_authority: false`)

This packet closes the NLFR flagship broker umbrella through wave 13. It reflects on waves 1–13
outcomes, honest residuals, and what the operator can credibly claim today.

---

## Umbrella verdict

| Span | Status | Proof |
|------|--------|-------|
| Waves 1–4 (cutover foundation) | **DONE_WITH_CONCERNS** | Canvas polish, agent/LRE/CI paths with host + GHA blockers |
| Waves 5–9 (operator bridge) | **DONE_WITH_CONCERNS** | Retention, cache gate, PR attachment, dag-gui manifest |
| Waves 10–13 (day-to-day workflow) | **DONE_WITH_CONCERNS** | GHA offline residual; adoption, history, canvas ergonomics shipped |
| **Umbrella 1–13** | **DONE_WITH_CONCERNS** | 140 passed, 3 skipped; local gates substitute for CI |

A skeptic can run the cache-only proof kit locally, browse multi-run history, adopt via `nlfr init`,
and operate a capped canvas projection — without fleet claims or invented backend state.

---

## Wave outcome matrix

| Wave | `wave_id` | Status | Primary outcome |
|------|-----------|--------|-----------------|
| 1 | `tier1-canvas-polish` | SHIPPED | Canvas UX, run-group selector |
| 2 | `agent-provenance-live` | DONE_WITH_CONCERNS | Agent proof path; Cursor CLI host-gated |
| 3 | `lre-linux-manual-proof` | DONE_WITH_CONCERNS | LRE Linux runbook; Darwin blocker |
| 4 | `ci-restore-verify` | DONE_WITH_CONCERNS | GHA restore runbook; GHA offline |
| 5 | `live-proof-residual` | DONE_WITH_CONCERNS | M8/LRE honest blockers refreshed |
| 6 | `retention-policy-v1` | SHIPPED | Index-only retention; no auto-purge |
| 7 | `cache-only-ci-gate` | DONE_WITH_CONCERNS | Gate script; GHA job optional |
| 8 | `pr-proof-attachment` | SHIPPED | Markdown PR proof exporter |
| 9 | `kos-operator-bridge` | DONE_WITH_CONCERNS | dag-gui manifest + gap honesty |
| 10 | `gha-sustained-green` | DONE_WITH_CONCERNS | Local readiness; GHA sustained green blocked |
| 11 | `adoption-init-path` | SHIPPED | `nlfr init`, adapter wiki, one-command record |
| 12 | `multi-run-history-v1` | SHIPPED | `compare history`, browse-run-history wiki |
| 13 | `operator-console-ergonomics` | SHIPPED | 8-node canvas cap, lens polish, doctor hints |

---

## What landed (credible claims)

| Capability | Truth label | Evidence |
|------------|-------------|----------|
| Cache-only proof path | `collectable_v1` / `high` | `nlfr doctor`, `nlfr run`, pytest |
| Projection-only canvas | `derived_v1` / `high` | Canvas truth tests, sample projections |
| Multi-run history | `derived_v1` / `high` | `compare index`, `compare history` |
| Adoption init path | `derived_v1` / `high` | `nlfr init`, adapter wiki, `record-this-target.sh` |
| 8-node default cap | `derived_v1` / `high` | `pageModel.ts`, `test_canvas_node_cap.py` |
| PR proof attachment | `derived_v1` / `high` | Markdown exporter + sample |
| dag-gui handoff bridge | `collectable_v1` / `high` | `cutover-manifest.json`, handoff index |

---

## Honest residuals (not closed)

| ID | Gap | Severity | Since |
|----|-----|----------|-------|
| C-UMB-1 | **GHA offline** — no sustained green on `nlfr-proof.yml` | P0 | W4 |
| C-UMB-2 | **CI promotion** — proof-sample promotion deferred | P1 | W10 |
| C-UMB-3 | **Fleet parsers blocked** — no scheduler/queue-time claims | P0 policy | W9 |
| C-UMB-4 | **M8 live Cursor** — operator-host gated | P1 | W2/W5 |
| C-UMB-5 | **LRE Linux parity** — x86_64-linux host gated | P1 | W3/W5 |
| C-UMB-6 | **Full operator console** — ergonomics only; no fleet UI | blocked | W13 |

See [`../wave-9/gap-honesty-packet.md`](../wave-9/gap-honesty-packet.md) for truth-labeled detail.
Wave 10 adds [`../wave-10/integration-brief.md`](../wave-10/integration-brief.md) GHA readiness substitute.

---

## Cross-repo coupling

| Repo | Role | Artifact |
|------|------|----------|
| knowledge-os | KOS control plane | `seed_nlfr_flagship_waves_10_13.py`, `dag:nlfr-flagship` |
| harmony-session-fleet | dag-gui NodeInspector | Reads NLFR handoff paths via manifest |
| nativelink-agent-flight-recorder | Evidence source | Handoffs, projections, proof samples |

NLFR supplies manifest + handoff paths only. Harmony/Electron implementation is **cross-repo**.

---

## Proof (local — umbrella close)

```bash
uv run pytest -q
bash -n scripts/*.sh
./scripts/verify-gha-readiness.sh
./scripts/cache-only-ci-gate.sh
PYTHONPATH=src uv run python -m nlfr init --help
PYTHONPATH=src uv run python -m nlfr compare history --help
npm --prefix apps/canvas run test:truth
# When kos serve running:
python3 tools/orchestrator/scripts/seed_nlfr_flagship_waves_10_13.py --mark-done   # knowledge-os
curl -sS 'http://127.0.0.1:7423/v1/dag/dag%3Anlfr-flagship/frontier'
```

**Result:** 140 passed, 3 skipped (`uv run pytest -q`, 2026-06-07).

---

## KOS close

All W10–W13 nodes marked done via `seed_nlfr_flagship_waves_10_13.py --mark-done`.
Roadmap [`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) status: **SHIPPED**.

**Next broker action:** Wave 14+ planning outside this umbrella — revisit GHA restore when Actions
returns; fleet evidence remains on [`future-execution-ladder.md`](../../../../dags/future-execution-ladder.md).

---

## Handoff index

| Span | Integration brief | Worker results |
|------|-------------------|----------------|
| Waves 1–4 | [`nlfr-kos-roadmap.md`](../../../../dags/nlfr-kos-roadmap.md) | `wave-{1,2,3,4}/` |
| Waves 5–9 | [`nlfr-kos-roadmap-waves-5-8.md`](../../../../dags/nlfr-kos-roadmap-waves-5-8.md) | `wave-{5,6,7,8,9}/` |
| Waves 10–13 | [`nlfr-kos-roadmap-waves-10-13.md`](../../../../dags/nlfr-kos-roadmap-waves-10-13.md) | `wave-{10,11,12,13}/` |
| Gap honesty | [`../wave-9/gap-honesty-packet.md`](../wave-9/gap-honesty-packet.md) | — |
| Handoff index | [`../README.md`](../README.md) | — |
