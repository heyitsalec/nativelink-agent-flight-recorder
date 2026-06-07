# Docs excellence — broker DAG (flagship OSS documentation)

**Status:** wave-1 SHIPPED (`DONE_WITH_CONCERNS`)  
**Branch:** `feat/docs-excellence`  
**Handoffs:** `docs/sessions/handoffs/docs-excellence/wave-1/`  
**Excellence bar:** [`excellence-bar.md`](../sessions/handoffs/docs-excellence/wave-0/excellence-bar.md)

Broker contract: [knowledge-os/agent-os/harness/broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md)

## Objective

Raise NLFR documentation to **flagship open-source** quality: Diátaxis-aligned
wiki, Harmony-style README, adoption paths that match the evidence-first product
rule, architecture diagrams grounded in recorded facts, proof-sample hubs, and
contributor onboarding — without inventing backend state or claiming unproven
fleet/scheduler correlation.

## North star

A new operator can:

1. Read the README and understand the evidence loop in under five minutes.
2. Follow adoption docs to run local proof gates (GHA offline tolerated).
3. Open the wiki hub and find tutorial / how-to / reference / explanation by intent.
4. Inspect proof samples and tryout packets with truth labels intact.
5. Contribute without guessing projection vs ingest boundaries.

## Sub-DAG coordinators (parent spawns; coordinators do not spawn)

| Coordinator | Sub-DAG | write_scope |
|-------------|---------|-------------|
| `coord-readme-flagship` | README flagship | `README.md` |
| `coord-wiki-hub` | Wiki hub | `docs/INDEX.md`, `docs/wiki/**` |
| `coord-adoption-paths` | Adoption paths | `docs/ADOPTION_GUIDE.md`, `docs/WALKTHROUGH.md`, `docs/DEMO_SCRIPT.md`, `docs/CI_RECIPE.md`, `docs/DEV_ENVIRONMENT.md` |
| `coord-diagrams` | Architecture diagrams | `docs/diagrams/**` |
| `coord-proof-samples-hub` | Proof samples hub | `docs/proof-samples/README.md`, `docs/TRYOUT_PACKET.md` |
| `coord-code-polish` | Code doc polish | `src/nlfr/**` (docstrings, naming consistency, dead import cleanup **only** — no behavior change) |
| `coord-contributing` | Contributing cross-links | `docs/CONTRIBUTING.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/IMPLEMENTATION_DAG.md` |

Disjoint `write_scope` is mandatory. Coordinators return `DispatchManifest` JSON only.

## Wave schedule

| Wave | Work | Gate |
|------|------|------|
| **0** | ARM | DAG mirror, excellence bar, KOS routing, spawn ledger |
| 1 | Parallel sub-DAG coordinators → workers | integration brief per coordinator |
| 1.5 | Reflect | parent reads briefs; drift vs excellence bar |
| 2 | Fix gaps + cross-link audit | link checker / manual spot check |
| 3 | Integrative review | parent proof gates + ship packet |

## Diagram deliverables (coord-diagrams)

Mermaid sources under `docs/diagrams/`:

| Diagram | Topic |
|---------|-------|
| Evidence loop | record → ingest → export → canvas projection |
| Broker orchestration | parent → coordinators → workers → proof gates |
| Canvas projection flow | projection JSON → truth labels → sparse canvas |
| Truth label ladder | `source_kind` × `confidence` × `redaction_state` |

Every diagram caption must state claim boundary (`collectable_v1` vs `derived_v1` vs `future`).

## Proof commands (local — GHA offline)

```bash
uv run pytest -q
bash -n scripts/*.sh
npm --prefix apps/canvas run test:truth
./scripts/record-proof.sh
```

Parent proof gates substitute for CI while GHA is offline:
[`frontier-wave/wave-1/gha-offline-proof-shift.md`](../sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md).

Doc-only changes: no pytest requirement beyond sanity if no Python touched; code-polish
sub-DAG must run full pytest before ship.

## Broker rules

| Action | Allowed |
|--------|---------|
| Rewrite docs for clarity, Diátaxis structure, cross-links | Yes |
| Add mermaid diagrams with honest claim boundaries | Yes |
| Polish docstrings / remove dead imports in `src/nlfr/**` | Yes (no behavior change) |
| Invent worker/scheduler/queue claims in prose or diagrams | **No** |
| Canvas screenshots implying live backend state not in projection JSON | **No** |
| Export secrets, raw logs, credentials, or private paths | **No** |

## Relationship to prior doc work

| Prior DAG | Relationship |
|-----------|--------------|
| [doc-capture-pass.md](doc-capture-pass.md) | Hero GIFs + initial wiki — excellence wave **extends**, does not replace |
| [nlfr-doc-capture-wave2.md](nlfr-doc-capture-wave2.md) | Tier1-aligned media refresh — link from README when present |
| [m5-ci-proof.md](m5-ci-proof.md) | CI_RECIPE must stay aligned with `.github/workflows/nlfr-proof.yml` |

## Exit criteria (wave 3 ship)

1. `docs/INDEX.md` routes all four Diátaxis quadrants.
2. README passes Harmony-style scan (hero, quickstart, proof command, truth-label callout).
3. Adoption path docs share consistent command blocks and GHA-offline fallback notes.
4. Four mermaid diagrams land with captions and evidence refs.
5. `docs/proof-samples/README.md` indexes samples with truth labels.
6. CONTRIBUTING ↔ IMPLEMENTATION_DAG ↔ USEFULNESS_ROADMAP cross-linked.
7. `coord-code-polish` diff is docstring/import-only (reviewable via `git diff --stat src/nlfr`).

## Handoff index

- Wave-1 integration: [`integration-brief.md`](../sessions/handoffs/docs-excellence/wave-1/integration-brief.md)
- Wave-1 spawn ledger: [`spawn-ledger.md`](../sessions/handoffs/docs-excellence/wave-1/spawn-ledger.md)
- Wave-1 worker results: [`worker-results.json`](../sessions/handoffs/docs-excellence/wave-1/worker-results.json)
- Wave-0 ARM: `docs/sessions/handoffs/docs-excellence/wave-0/broker-arm.md`
- KOS routing: `docs/sessions/handoffs/docs-excellence/wave-0/KOS-startup-routing.md`
- Wave-0 spawn ledger: `docs/sessions/handoffs/docs-excellence/wave-0/spawn-ledger.md`
