# Docs wiki — wave 2 (excellence gap closure + KOS cutover routing)

**Status:** wave-1 SHIPPED (`DONE_WITH_CONCERNS`; waves 1.5–3 pending)  
**Branch:** `feat/docs-wiki-wave2`  
**Parent DAG:** [docs-excellence.md](docs-excellence.md) (wave-1 SHIPPED `DONE_WITH_CONCERNS`)  
**Handoffs:** `docs/sessions/handoffs/docs-wiki-wave2/wave-1/` (wave-0: `wave-0/`)  
**Next umbrella:** [nlfr-kos-roadmap.md](nlfr-kos-roadmap.md) (spawn after merge)  
**Excellence bar (inherited):** [`docs-excellence/wave-0/excellence-bar.md`](../sessions/handoffs/docs-excellence/wave-0/excellence-bar.md)

Broker contract: [knowledge-os/agent-os/harness/broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md)

Control plane: **local KOS primary** — `kos serve http://127.0.0.1:7423`, `dag_ref` **`dag:nlfr-flagship`**, `linear_authority: false`. See [`KOS-startup-routing.md`](../sessions/handoffs/docs-wiki-wave2/wave-0/KOS-startup-routing.md).

## Objective

Close the **post–docs-excellence gaps** (wave-1 reflect concerns C-1–C-5), finish
integrative review, and wire broker handoffs to the **Knowledge OS control plane
cutover** so coordinators read frontier state from `kos serve` instead of Linear
MCP as primary authority.

## North star

After wave 2 ships:

1. Legacy docs carry honest historical banners; stale proof counts removed.
2. Broker orchestration diagram exists with claim boundaries (`derived_v1` / `future`).
3. `docs/wiki/decisions/` holds ADR-lite entries linked from INDEX and architecture track.
4. Optional M9 compare proof-sample JSON is indexed or explicitly deferred with truth labels.
5. Link audit passes on `docs/INDEX.md` and `docs/wiki/**`.
6. KOS cutover routing documented in NLFR handoffs + KOS integration brief.

## Sub-DAG coordinators (parent spawns; coordinators do not spawn)

| Coordinator | Sub-DAG | write_scope |
|-------------|---------|-------------|
| `coord-historical-banners` | Historical doc hygiene | `docs/IMPLEMENTATION_DAG.md`, `docs/EXTENSION_DAG.md`, `docs/LOCAL_EXECUTION_DAG.md`, `docs/PRODUCT_FRAMING.md`, `docs/REMOTE_EXECUTION_PLAN.md`, `docs/FRAMING_DISTANCE.md`, `docs/ONE_PAGER.md`, `demo/nativelink/README.md` — **banners + stale one-liners only** |
| `coord-broker-diagram` | Broker orchestration diagram | `docs/diagrams/broker-orchestration.md`, `docs/diagrams/README.md` |
| `coord-wiki-adrs` | ADR-lite decisions | `docs/wiki/decisions/**`, cross-links in `docs/INDEX.md`, `docs/wiki/README.md` |
| `coord-compare-sample` | M9 compare proof sample | `docs/proof-samples/compare-projection.json` (or honest deferral note in `docs/proof-samples/README.md` only) |
| `coord-link-audit` | Integrative link audit | `docs/INDEX.md`, `docs/wiki/**`, `docs/CONTRIBUTING.md` — fix broken relative links only |

Disjoint `write_scope` is mandatory. Coordinators return `DispatchManifest` JSON only.

## Wave schedule

| Wave | Work | Gate |
|------|------|------|
| **0** | ARM | DAG mirror, KOS routing, spawn ledger, KOS cutover integration brief |
| 1 | Parallel sub-DAG coordinators → workers | integration brief per coordinator |
| 1.5 | Reflect | parent reads briefs vs excellence bar + wave-1 concerns |
| 2 | Rescue / cross-link fixes | link spot check |
| 3 | Integrative review | parent proof gates + ship packet |

## Inherited gaps (from docs-excellence wave-1)

| ID | Gap | Owner coordinator |
|----|-----|-------------------|
| C-1 | `historical-docs-batch` not landed | `coord-historical-banners` |
| C-2 | Missing broker-orchestration diagram | `coord-broker-diagram` |
| C-3 | Empty `docs/wiki/decisions/` | `coord-wiki-adrs` |
| C-4 | No committed M9 compare proof-sample JSON | `coord-compare-sample` |
| C-5 | Wave-3 integrative review + link audit | `coord-link-audit` (wave 1) + parent (wave 3) |

## Proof commands (local — GHA offline)

```bash
uv run pytest -q
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
```

Doc-only changes: pytest required only when Python or behavior-adjacent docs change.
No behavior changes in this DAG.

Parent proof gates substitute for CI while GHA is offline:
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

## Broker rules

| Action | Allowed |
|--------|---------|
| Add historical banners and fix stale proof counts in legacy docs | Yes |
| Add broker-orchestration mermaid with honest claim boundaries | Yes |
| Seed ADR-lite entries under `docs/wiki/decisions/` | Yes |
| Commit redacted compare proof-sample JSON or defer honestly in hub | Yes |
| Fix broken wiki/INDEX links | Yes |
| Invent worker/scheduler/queue claims | **No** |
| Change runtime behavior in `src/nlfr/**` | **No** |
| Re-open docs-excellence wave-1 scope (README rewrite, hero capture) | **No** — link only |

## Relationship to prior doc work

| Prior DAG | Relationship |
|-----------|--------------|
| [docs-excellence.md](docs-excellence.md) | Parent — wave 2 closes reflect gaps only |
| [doc-capture-pass.md](doc-capture-pass.md) | Hero media baseline — do not re-capture unless broken |
| [nlfr-doc-capture-wave2.md](nlfr-doc-capture-wave2.md) | Tier1 hero refresh — orthogonal |

## Exit criteria (wave 3 ship)

1. All seven legacy docs in `coord-historical-banners` scope carry historical banners.
2. `docs/diagrams/broker-orchestration.md` indexed from `docs/diagrams/README.md`.
3. At least one ADR-lite entry in `docs/wiki/decisions/` linked from INDEX.
4. Compare proof-sample committed **or** hub documents honest deferral with truth labels.
5. Link audit: no broken relative links in INDEX + wiki hub pages.
6. KOS cutover brief landed in both repos; spawn ledger records `dag:nlfr-flagship`.

## Handoff index

- Wave-1 integration: [`integration-brief.md`](../sessions/handoffs/docs-wiki-wave2/wave-1/integration-brief.md)
- Wave-1 spawn ledger: [`spawn-ledger.md`](../sessions/handoffs/docs-wiki-wave2/wave-1/spawn-ledger.md)
- Wave-1 worker results: [`worker-results.json`](../sessions/handoffs/docs-wiki-wave2/wave-1/worker-results.json)
- Wave-0 ARM: [`broker-arm.md`](../sessions/handoffs/docs-wiki-wave2/wave-0/broker-arm.md)
- KOS routing: [`KOS-startup-routing.md`](../sessions/handoffs/docs-wiki-wave2/wave-0/KOS-startup-routing.md)
- Wave-0 spawn ledger: [`spawn-ledger.md`](../sessions/handoffs/docs-wiki-wave2/wave-0/spawn-ledger.md)
- KOS cutover brief: [knowledge-os `nlfr-kos-cutover/wave-0/integration-brief.md`](/Users/alecbot/Documents/knowledge-os/docs/sessions/handoffs/nlfr-kos-cutover/wave-0/integration-brief.md)
