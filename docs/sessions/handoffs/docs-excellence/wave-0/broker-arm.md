# Docs excellence — broker ARM

**Date:** 2026-06-06  
**Branch:** `feat/docs-excellence`  
**Status:** ARMED

## Operator intent

Broker a **flagship OSS documentation** pass across seven disjoint sub-DAGs.
Evidence-first product rules and truth labels apply to all prose and diagrams.

## Parent actions (ARM only)

- Created branch `feat/docs-excellence` from `main`
- Created DAG mirror: [`docs/dags/docs-excellence.md`](../../../dags/docs-excellence.md)
- Created excellence bar: [`excellence-bar.md`](excellence-bar.md)
- Created KOS routing: [`KOS-startup-routing.md`](KOS-startup-routing.md)
- Initialized spawn ledger: [`spawn-ledger.md`](spawn-ledger.md)
- Re-armed broker mode — **no wave-1 coordinator spawn in this ARM worker**

## Wave-1 dispatch (next)

Parent spawns coordinators in parallel (disjoint `write_scope`):

1. **coord-readme-flagship** — Harmony-style `README.md`
2. **coord-wiki-hub** — `docs/INDEX.md` + `docs/wiki/**` hub pages
3. **coord-adoption-paths** — adoption, walkthrough, demo, CI, dev env
4. **coord-diagrams** — mermaid under `docs/diagrams/**`
5. **coord-proof-samples-hub** — proof samples README + tryout packet
6. **coord-code-polish** — docstrings / naming / dead imports in `src/nlfr/**` only
7. **coord-contributing** — CONTRIBUTING + roadmap + IMPLEMENTATION_DAG cross-links

## Proof gates (parent at ship)

`uv run pytest -q` (required if `coord-code-polish` lands) · `bash -n scripts/*.sh` ·
`npm --prefix apps/canvas run test:truth` · manual link audit on `docs/INDEX.md`

GHA offline: local gates substitute per
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md).
