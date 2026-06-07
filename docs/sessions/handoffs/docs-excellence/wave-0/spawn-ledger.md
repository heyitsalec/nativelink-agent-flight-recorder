# Spawn ledger — docs-excellence wave-0

**DAG:** `docs/dags/docs-excellence.md`  
**Branch:** `feat/docs-excellence`  
**KOS:** `docs/sessions/handoffs/docs-excellence/wave-0/KOS-startup-routing.md`

| agent | type | write_scope | status |
|-------|------|-------------|--------|
| broker-parent | parent | — | SHIPPED |
| docs-excellence-arm | worker | `docs/dags/docs-excellence.md`, `docs/sessions/handoffs/docs-excellence/wave-0/**` | DONE |
| coord-readme-flagship | coordinator | `README.md` | **SHIPPED** |
| coord-wiki-hub | coordinator | `docs/INDEX.md`, `docs/wiki/**` | **SHIPPED** |
| coord-adoption-paths | coordinator | `docs/ADOPTION_GUIDE.md`, `docs/WALKTHROUGH.md`, `docs/DEMO_SCRIPT.md`, `docs/CI_RECIPE.md`, `docs/DEV_ENVIRONMENT.md` | **SHIPPED** |
| coord-diagrams | coordinator | `docs/diagrams/**` | **SHIPPED** |
| coord-proof-samples-hub | coordinator | `docs/proof-samples/README.md`, `docs/TRYOUT_PACKET.md` | **SHIPPED** |
| coord-code-polish | coordinator | `src/nlfr/**` | **SHIPPED** |
| coord-contributing | coordinator | `docs/CONTRIBUTING.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/IMPLEMENTATION_DAG.md` | **SHIPPED** |

**Wave-0 ceiling:** ARM complete — DAG mirror, excellence bar, KOS routing, spawn ledger on disk.

**Wave-1 close:** all seven coordinators SHIPPED. Handoffs: [`wave-1/integration-brief.md`](../wave-1/integration-brief.md).
