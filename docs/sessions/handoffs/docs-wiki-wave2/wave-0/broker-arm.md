# Docs wiki wave 2 — broker ARM

**Date:** 2026-06-06  
**Branch:** `feat/docs-wiki-wave2`  
**Worker:** `wiki-wave2-arm`  
**Status:** ARMED

## Operator intent

Broker a **follow-on documentation wave** that closes docs-excellence wave-1 gaps
(C-1–C-5), runs integrative link audit, and routes broker sessions through the
**local KOS control plane** (`kos serve`, `dag:nlfr-flagship`, `linear_authority: false`).

## Parent actions (ARM only)

- Branch `feat/docs-wiki-wave2` from `main` (exists)
- Created DAG mirror: [`docs/dags/docs-wiki-wave2.md`](../../../dags/docs-wiki-wave2.md)
- Created KOS routing: [`KOS-startup-routing.md`](KOS-startup-routing.md)
- Initialized spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Added active row to [`docs/dags/README.md`](../../../dags/README.md)
- KOS cutover integration brief: [knowledge-os `nlfr-kos-cutover/wave-0/integration-brief.md`](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/nlfr-kos-cutover/wave-0/integration-brief.md)
- Re-armed broker mode — **no wave-1 coordinator spawn in this ARM worker**

## Wave-1 dispatch (next)

Parent spawns coordinators in parallel (disjoint `write_scope`):

1. **coord-historical-banners** — historical banners + stale one-liner fixes (7 legacy docs + demo README)
2. **coord-broker-diagram** — `docs/diagrams/broker-orchestration.md`
3. **coord-wiki-adrs** — ADR-lite under `docs/wiki/decisions/**`
4. **coord-compare-sample** — M9 compare proof-sample JSON or honest hub deferral
5. **coord-link-audit** — broken link fixes in INDEX + wiki

Before spawning, confirm `kos serve http://127.0.0.1:7423` is healthy and
`dag:nlfr-flagship` appears in `/v1/dags` (see KOS cutover brief).

## Proof gates (parent at ship)

`bash -n scripts/*.sh` · manual link audit on `docs/INDEX.md` + `docs/wiki/**`

GHA offline: local gates substitute per
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).

## Inherited excellence bar

All workers must read [`docs-excellence/wave-0/excellence-bar.md`](../../docs-excellence/wave-0/excellence-bar.md)
before writing. Wave 2 does not re-litigate Diátaxis structure shipped in wave 1.
