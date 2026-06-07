# Spawn ledger — docs-excellence wave-1

**DAG:** `docs/dags/docs-excellence.md`  
**Branch:** `feat/docs-excellence`  
**KOS:** `docs/sessions/handoffs/docs-excellence/wave-0/KOS-startup-routing.md`

## Wave-1 coordinators → workers

| worker_id | coordinator | type | write_scope | status |
|-----------|-------------|------|-------------|--------|
| readme-flagship | coord-readme-flagship | worker | `README.md` | DONE |
| wiki-hub | coord-wiki-hub | worker | `docs/INDEX.md`, `docs/wiki/**` | DONE |
| adoption-paths | coord-adoption-paths | worker | `docs/ADOPTION_GUIDE.md`, `docs/WALKTHROUGH.md`, `docs/DEMO_SCRIPT.md`, `docs/CI_RECIPE.md`, `docs/DEV_ENVIRONMENT.md` | DONE |
| diagrams | coord-diagrams | worker | `docs/diagrams/**` | DONE |
| proof-samples-hub | coord-proof-samples-hub | worker | `docs/proof-samples/README.md`, `docs/TRYOUT_PACKET.md`, `docs/GITHUB_RELEASE.md` | DONE |
| code-polish | coord-code-polish | worker | `src/nlfr/**` | DONE |
| contributing | coord-contributing | worker | `docs/CONTRIBUTING.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/IMPLEMENTATION_DAG.md`, `apps/canvas/README.md` | DONE |

## Wave-2 gap workers

| worker_id | coordinator | type | write_scope | status |
|-----------|-------------|------|-------------|--------|
| wiki-hub-integrate | coord-wiki-hub | worker | `docs/INDEX.md`, `docs/wiki/README.md`, `docs/dags/README.md`, `docs/wiki/compare-runs.md` | DONE |
| media-capture | broker-parent | worker | `docs/media/**`, `docs/images/**` | DONE |
| historical-docs-batch | broker-parent | worker | 7 legacy `docs/*.md` + `demo/nativelink/README.md` | **PENDING** |
| docs-excellence-reflect | broker-parent | worker (read-only) | — | DONE |
| docs-excellence-handoffs-close | broker-parent | worker | `docs/sessions/handoffs/docs-excellence/wave-1/**`, `wave-0/spawn-ledger.md`, `docs/sessions/handoffs/README.md`, `docs/dags/docs-excellence.md` | DONE |

**Wave-1 ceiling:** seven coordinator sub-DAGs landed on branch (uncommitted working tree at close).

**Wave-2 ceiling:** cross-link + media gaps; `historical-docs-batch` still open.

**Proof gate (local — GHA offline):**

```bash
uv run pytest -q
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
```
