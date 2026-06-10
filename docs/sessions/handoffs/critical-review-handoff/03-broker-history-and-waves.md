# Broker history and waves

← [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md) · [README](README.md)

---

## Why broker waves exist

NLFR grew across **M5–M9 substrate** (milestones on `main`) and **flagship KOS cutover** (waves
1–13 on `feat/docs-wiki-wave2`). Multi-session agent work without receipts tends to:

- re-litigate scope each chat,
- merge hype with shipped code, and
- lose honest residuals.

The broker model assigns each wave an **integration brief**, **worker results**, and **spawn
ledger**. Parent chats carry JSON summaries; rich artifacts live in
`docs/sessions/handoffs/nlfr-kos-cutover/`.

**Control plane:** `kos serve` with `dag:nlfr-flagship`, `linear_authority: false`. Linear PER-*
tickets are reference mirrors — wave closure authority is local KOS.

**Cross-repo:** `knowledge-os` seeds DAG nodes; `harmony-session-fleet` dag-gui reads NLFR handoff
paths via `cutover-manifest.json`. NLFR supplies manifest + paths only.

---

## Timeline overview

```text
main: M5–M9 substrate (CI recipe, M6 canvas default, M7 worker parser, M8 agent adapter, M9 compare)
        ↓
feat/docs-wiki-wave2: docs wiki wave 2 + dag:nlfr-flagship waves 1–13
        ↓
wave-14: umbrella close packet (DONE_WITH_CONCERNS)
        ↓
PR #10 open → merge target main
        ↓
wave 14+ planning: GHA restore, fleet evidence ladder (out of umbrella)
```

**Prerequisite shipped before flagship waves:** Diátaxis wiki, proof-samples hub, adoption paths
(docs-excellence / docs-wiki-wave2 DAGs).

---

## Umbrella verdict

| Span | Status |
|------|--------|
| Waves 1–4 (cutover foundation) | DONE_WITH_CONCERNS |
| Waves 5–9 (operator bridge) | DONE_WITH_CONCERNS |
| Waves 10–13 (day-to-day workflow) | DONE_WITH_CONCERNS |
| **Umbrella 1–13** | **DONE_WITH_CONCERNS** |

**Meaning of DONE_WITH_CONCERNS:** Code, docs, and local proof gates landed; documented residuals
(GHA offline, host-gated live proofs, fleet policy block) are **not** hidden failures.

Authoritative close: [wave-14/umbrella-close-packet.md](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md).

---

## Wave outcome matrix

| Wave | `wave_id` | Status | Primary outcome | Why this wave |
|------|-----------|--------|-----------------|---------------|
| 1 | `tier1-canvas-polish` | SHIPPED | Canvas UX, run-group selector | Demo-first credibility |
| 2 | `agent-provenance-live` | DONE_WITH_CONCERNS | Agent proof path; Cursor host-gated | Non-fixture agent story |
| 3 | `lre-linux-manual-proof` | DONE_WITH_CONCERNS | LRE Linux runbook; Darwin blocker | x86_64-linux skeptic sample |
| 4 | `ci-restore-verify` | DONE_WITH_CONCERNS | GHA restore runbook; GHA offline | CI recipe when Actions returns |
| 5 | `live-proof-residual` | DONE_WITH_CONCERNS | M8/LRE blocker refresh | Honest status, no stale claims |
| 6 | `retention-policy-v1` | SHIPPED | Index-only retention; no auto-purge | M9 foundation for history |
| 7 | `cache-only-ci-gate` | DONE_WITH_CONCERNS | Gate script; GHA optional | Local substitute for CI |
| 8 | `pr-proof-attachment` | SHIPPED | Markdown PR proof exporter | Proof where review happens |
| 9 | `kos-operator-bridge` | DONE_WITH_CONCERNS | dag-gui manifest + gap honesty | Cross-repo operator GUI bridge |
| 10 | `gha-sustained-green` | DONE_WITH_CONCERNS | Local readiness; GHA blocked | Don't block ship on CI green |
| 11 | `adoption-init-path` | SHIPPED | `nlfr init`, adapter wiki, one-command record | Reduce adoption friction |
| 12 | `multi-run-history-v1` | SHIPPED | `compare history`, browse-run-history wiki | Pairwise+ history without fleet UI |
| 13 | `operator-console-ergonomics` | SHIPPED | 8-node cap, lens polish, doctor hints | Ergonomics without fleet dashboard |

---

## Honest residuals (umbrella)

| ID | Gap | Severity | Since |
|----|-----|----------|-------|
| C-UMB-1 | **GHA offline** — no sustained green on `nlfr-proof.yml` | P0 | W4 |
| C-UMB-2 | **CI promotion** — proof-sample promotion deferred | P1 | W10 |
| C-UMB-3 | **Fleet parsers blocked** — no scheduler/queue-time claims | P0 policy | W9 |
| C-UMB-4 | **M8 live Cursor** — operator-host gated | P1 | W2/W5 |
| C-UMB-5 | **LRE Linux parity** — x86_64-linux host gated | P1 | W3/W5 |
| C-UMB-6 | **Full operator console** — ergonomics only; no fleet UI | blocked | W13 |

Detail: [wave-9/gap-honesty-packet.md](../nlfr-kos-cutover/wave-9/gap-honesty-packet.md).

---

## DAG documentation map

| Waves | Roadmap doc |
|-------|-------------|
| 1–4 | [docs/dags/nlfr-kos-roadmap.md](../../../dags/nlfr-kos-roadmap.md) |
| 5–9 | [docs/dags/nlfr-kos-roadmap-waves-5-8.md](../../../dags/nlfr-kos-roadmap-waves-5-8.md) |
| 10–13 | [docs/dags/nlfr-kos-roadmap-waves-10-13.md](../../../dags/nlfr-kos-roadmap-waves-10-13.md) |

Handoff index: [nlfr-kos-cutover/README.md](../nlfr-kos-cutover/README.md).

---

## What landed — credible claims table

| Capability | Truth label | Evidence |
|------------|-------------|----------|
| Cache-only proof path | `collectable_v1` / high | `nlfr doctor`, `nlfr run`, pytest |
| Projection-only canvas | `derived_v1` / high | Canvas truth tests, sample projections |
| Multi-run history | `derived_v1` / high | `compare index`, `compare history` |
| Adoption init path | `derived_v1` / high | `nlfr init`, adapter wiki, `record-this-target.sh` |
| 8-node default cap | `derived_v1` / high | `pageModel.ts`, `test_canvas_node_cap.py` |
| PR proof attachment | `derived_v1` / high | Markdown exporter + sample |
| dag-gui handoff bridge | `collectable_v1` / high | `cutover-manifest.json`, handoff index |

---

## PR #10 in broker context

PR #10 is the **integration PR** for:

1. **docs-wiki-wave2** — contracts reference, compare samples, adoption/history how-tos.
2. **KOS cutover completion** — waves 1–13 handoffs + wave-14 umbrella close.
3. **Late-wave code** — init, compare history, canvas cap, GHA readiness scripts.

It does **not** close C-UMB-1 (GHA offline) or C-UMB-3 (fleet parsers). Merge should be evaluated
as **reference-kit ship with documented concerns**, not as **fleet/product GA**.

---

## KOS close state

Waves 10–13 nodes marked done via `seed_nlfr_flagship_waves_10_13.py --mark-done` (knowledge-os).

Verify when `kos serve` running:

```bash
curl -sS 'http://127.0.0.1:7423/v1/dag/dag%3Anlfr-flagship/frontier'
```

**Next broker action (post-umbrella):** Wave 14+ planning outside waves 1–13 — revisit GHA restore
when Actions returns; fleet evidence on
[future-execution-ladder.md](../../../dags/future-execution-ladder.md).

---

## How reviewers should use wave history

1. **Do not treat SHIPPED waves as full live proof** — check status column (`DONE_WITH_CONCERNS`
   waves often shipped docs/scripts while live path is host-gated).
2. **Trace a claim backward** — user-visible feature → projection schema → parser → proof script →
   pytest fixture.
3. **Compare wave README to ONE_PAGER** — any drift in unproven list is a defect.
4. **Weight policy blocks equally with code gaps** — C-UMB-3 is intentional; building fleet UI early
   would violate product rule.

---

## Related broker DAGs (not in umbrella 1–13)

| DAG | Role |
|-----|------|
| `m5-m9-umbrella` | Original milestone closure on main |
| `docs-excellence` | Documentation bar before wiki wave 2 |
| `docs-wiki-wave2` | Diátaxis wiki structure |
| `tier1-live-bazel` | Live Bazel agent demo proofs |
| `frontier-wave` | GHA offline proof shift |
| `future-fleet-claims` | Research matrix for unsupported claims |
| `fleet-evidence-v1` | Future parser ladder (frontier) |

Session handoff root: [docs/sessions/handoffs/README.md](../README.md).

---

← [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md) · Next: [04-drift-audit.md](04-drift-audit.md) · [README](README.md)
