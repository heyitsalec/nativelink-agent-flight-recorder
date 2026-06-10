# Spawn ledger — docs-wiki-wave2 wave-1

**DAG:** `docs/dags/docs-wiki-wave2.md`  
**Branch:** `feat/docs-wiki-wave2`  
**Control plane:** `kos serve http://127.0.0.1:7423` · `dag_ref` `dag:nlfr-flagship` · `linear_authority: false`  
**KOS:** `docs/sessions/handoffs/docs-wiki-wave2/wave-0/KOS-startup-routing.md`

## Wave-1 coordinators → workers

| worker_id | coordinator | type | write_scope | status |
|-----------|-------------|------|-------------|--------|
| historical-banners | coord-historical-banners | worker | 7 legacy `docs/*.md` + `demo/nativelink/README.md` — banners only | SHIPPED (partial — 5/7 + demo open) |
| broker-diagram | coord-broker-diagram | worker | `docs/diagrams/broker-orchestration.md`, `docs/diagrams/README.md` | SHIPPED |
| wiki-adrs | coord-wiki-adrs | worker | `docs/wiki/decisions/**`, cross-links in INDEX + wiki hub | SHIPPED |
| compare-sample | coord-compare-sample | worker | `docs/proof-samples/compare-projection.json` or hub deferral | SHIPPED |
| link-audit | coord-link-audit | worker | `docs/INDEX.md`, `docs/wiki/**`, `docs/CONTRIBUTING.md` — broken links only | SHIPPED |

## Handoffs close

| worker_id | coordinator | type | write_scope | status |
|-----------|-------------|------|-------------|--------|
| wiki-wave2-handoffs-close | broker-parent | worker | `docs/sessions/handoffs/docs-wiki-wave2/wave-1/**`, `wave-0/spawn-ledger.md`, `docs/sessions/handoffs/README.md`, `docs/dags/docs-wiki-wave2.md`, `docs/dags/README.md` | DONE |

**Wave-1 ceiling:** five coordinator sub-DAGs landed on branch; historical banners partial; waves 1.5–3 remain for parent.

**Proof gate (local — GHA offline):**

```bash
uv run pytest -q
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
```
