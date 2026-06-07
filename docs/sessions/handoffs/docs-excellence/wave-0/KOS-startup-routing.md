# Knowledge OS startup routing — Docs excellence

**Mandatory read** for every coordinator and worker in the docs-excellence DAG.

| Order | Doc |
|-------|-----|
| 1 | `AGENTS.md` |
| 2 | `/Users/alecbot/Documents/knowledge-os/projects/nlfr/pack.md` |
| 3 | [`excellence-bar.md`](excellence-bar.md) |
| 4 | [`docs/dags/docs-excellence.md`](../../../dags/docs-excellence.md) |
| 5 | [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md) |

## Reference standards (read before writing)

| Standard | Use for |
|----------|---------|
| [Diátaxis](https://diataxis.fr/) | Tutorial / how-to / reference / explanation split |
| [Google eng doc style](https://google.github.io/eng-practices/docs/) | Clarity, scope, active voice |
| `/Users/alecbot/Documents/harmony/README.md` | Harmony-style README layout |
| `docs/ARCHITECTURE_TRACK.md` | Phase ladder alignment |
| Prior doc capture: `docs/dags/doc-capture-pass.md` | Hero media + wiki baseline |

## Active sub-DAGs (wave-1)

| Coordinator | DAG slice | write_scope |
|-------------|-----------|-------------|
| `coord-readme-flagship` | README flagship | `README.md` |
| `coord-wiki-hub` | Wiki hub | `docs/INDEX.md`, `docs/wiki/**` |
| `coord-adoption-paths` | Adoption paths | `docs/ADOPTION_GUIDE.md`, `docs/WALKTHROUGH.md`, `docs/DEMO_SCRIPT.md`, `docs/CI_RECIPE.md`, `docs/DEV_ENVIRONMENT.md` |
| `coord-diagrams` | Architecture diagrams | `docs/diagrams/**` |
| `coord-proof-samples-hub` | Proof samples hub | `docs/proof-samples/README.md`, `docs/TRYOUT_PACKET.md` |
| `coord-code-polish` | Code doc polish | `src/nlfr/**` (docstrings, naming, dead imports — **no behavior change**) |
| `coord-contributing` | Contributing cross-links | `docs/CONTRIBUTING.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/IMPLEMENTATION_DAG.md` |

**Branch:** `feat/docs-excellence`

## Broker rules

- Coordinators return `DispatchManifest` only — no Task spawn.
- Parent spawns workers; disjoint `write_scope` enforced.
- Every new claim in docs carries truth-label vocabulary (`source_kind`, `confidence`, `evidence_refs`, `redaction_state`).
- Canvas and README must not imply live backend state absent from projection JSON.
- GHA offline: document local proof substitutes; do not block ship on CI green.
- Privacy: no secrets, credentials, raw private logs, or customer data in docs.

## Proof posture

```bash
uv run pytest -q                    # when src/nlfr touched
bash -n scripts/*.sh                # when script examples cited
npm --prefix apps/canvas run test:truth   # when canvas/projection docs updated
```
