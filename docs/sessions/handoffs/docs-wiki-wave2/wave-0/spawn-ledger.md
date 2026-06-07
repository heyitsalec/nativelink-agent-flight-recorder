# Spawn ledger — docs-wiki-wave2 wave-0

**DAG:** `docs/dags/docs-wiki-wave2.md`  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship` · `linear_authority: false`  
**KOS:** `docs/sessions/handoffs/docs-wiki-wave2/wave-0/KOS-startup-routing.md`

| agent | type | write_scope | status |
|-------|------|-------------|--------|
| broker-parent | parent | — | ARMED |
| wiki-wave2-arm | worker | `docs/dags/docs-wiki-wave2.md`, `docs/dags/README.md` (active row), `docs/sessions/handoffs/docs-wiki-wave2/wave-0/**` | DONE |
| coord-historical-banners | coordinator | 7 legacy docs + `demo/nativelink/README.md` | pending |
| coord-broker-diagram | coordinator | `docs/diagrams/broker-orchestration.md`, `docs/diagrams/README.md` | pending |
| coord-wiki-adrs | coordinator | `docs/wiki/decisions/**`, INDEX + wiki cross-links | pending |
| coord-compare-sample | coordinator | `docs/proof-samples/compare-projection.json` or hub deferral | pending |
| coord-link-audit | coordinator | `docs/INDEX.md`, `docs/wiki/**`, `docs/CONTRIBUTING.md` | pending |

**Wave-0 ceiling:** ARM complete — DAG mirror, KOS routing, spawn ledger, KOS cutover brief cross-linked.

**Wave-1 next:** parent spawns five coordinators in parallel after `kos serve` health + `dag:nlfr-flagship` cutover check.
