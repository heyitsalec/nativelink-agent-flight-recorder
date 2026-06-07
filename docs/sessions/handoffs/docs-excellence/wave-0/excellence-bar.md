# Excellence bar — docs-excellence DAG

**Date:** 2026-06-06  
**Applies to:** all coordinators, workers, and parent proof gates in `docs-excellence`

This document is the acceptance criteria for the flagship OSS documentation pass.
Workers treat it as a checklist; parent uses it at wave 1.5 reflect and wave 3 ship.

---

## Flagship OSS documentation standards

### Diátaxis (four quadrants)

Every major doc must declare its quadrant and link from `docs/INDEX.md`:

| Quadrant | Operator intent | NLFR examples |
|----------|-----------------|---------------|
| **Tutorial** | First successful run, learning-oriented | Walkthrough, tryout packet quick path |
| **How-to** | Task-oriented recipe for a known goal | CI recipe, dev environment, demo script |
| **Reference** | Accurate, complete, constraint-focused | CLI flags, projection schema, truth-label fields |
| **Explanation** | Understanding-oriented, background | Architecture track, evidence loop, broker model |

Do not mix quadrants in a single page without clear section headers and INDEX links.

### Google engineering documentation style

- **Audience first:** state who the doc is for in the opening paragraph.
- **Active voice, short sentences:** prefer "Run the proof script" over "The proof script should be run."
- **Scope boundaries:** say what is out of scope (fleet dashboards, scheduler claims, auth).
- **Testable claims:** every "works" claim names a command or artifact path.
- **Consistent terminology:** evidence loop, projection, proof packet, run group, truth label.

### Harmony-style README

Root `README.md` must include:

1. One-line value proposition (evidence-first recorder, not dashboard cosplay).
2. Hero media or placeholder with capture instructions when GIFs absent.
3. Quickstart with copy-paste proof commands (`record-proof`, `graph export`, `test:truth`).
4. Truth-label callout (four fields from `AGENTS.md`).
5. Links to wiki hub, adoption guide, and contributing.
6. Honest requirements block (Bazel, NativeLink, GHA-offline fallback).

Reference: `/Users/alecbot/Documents/harmony/README.md`

### Architecture decision records (ADR-lite)

Significant doc choices that affect operators or contributors get a short ADR in
`docs/wiki/decisions/` (created by `coord-wiki-hub`):

- Context, decision, consequences (3–10 sentences each).
- Link from IMPLEMENTATION_DAG or ARCHITECTURE_TRACK when the decision gates work.

---

## NLFR-specific bars

### Evidence-first

Documentation describes the canonical flow in order:

1. Run a Bazel workload through a NativeLink-backed mode.
2. Capture immutable artifacts with SHA-256 hashes.
3. Ingest evidence into SQLite.
4. Export versioned projection JSON.
5. Render the canvas from projection JSON only.

Prose that skips ingest or projection steps, or presents the canvas as source of truth, fails review.

### Truth labels

Every projected node, edge, metric, and proof claim referenced in docs must mention or exemplify:

- `source_kind`: `collectable_v1`, `derived_v1`, `simulated_v1`, or `future`
- `confidence`: `high`, `medium`, `low`, or `unknown`
- `evidence_refs`
- `redaction_state`: `safe`, `redacted`, `blocked`, or `unknown`

Diagram captions and proof-sample tables include at least `source_kind` and `confidence`.

### No invented backend state

- Canvas docs describe **projection JSON inputs**, not live scheduler/worker queues.
- Do not claim exact worker/action/queue-time correlation unless direct evidence exists in repo parsers and proof scripts.
- Demo scripts label simulated or fixture paths explicitly.
- README screenshots (when added) must come from fixture projection or labeled dry-run output.

### GHA offline local gates

GitHub Actions may be non-green. Documentation must:

- Show local proof commands that substitute for CI (`uv run pytest -q`, `bash -n scripts/*.sh`, proof scripts).
- Cite [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../../frontier-wave/wave-1/gha-offline-proof-shift.md) where CI is discussed.
- Never instruct operators to block on CI green for doc-only or local-proof workflows.

### Privacy

Do not export or embed: secrets, credentials, raw private logs, environment variables,
raw prompts, customer data, or private legacy GUI material. Use hashes, redacted paths,
and short evidence spans.

---

## Sub-DAG registry (disjoint write_scope)

Parent spawns one coordinator per row. Coordinators return `DispatchManifest` only.

| Coordinator ID | Primary deliverable | write_scope |
|----------------|---------------------|-------------|
| `coord-readme-flagship` | Harmony-quality root README | `README.md` |
| `coord-wiki-hub` | Diátaxis wiki hub + new pages | `docs/INDEX.md`, `docs/wiki/**` |
| `coord-adoption-paths` | Operator adoption path suite | `docs/ADOPTION_GUIDE.md`, `docs/WALKTHROUGH.md`, `docs/DEMO_SCRIPT.md`, `docs/CI_RECIPE.md`, `docs/DEV_ENVIRONMENT.md` |
| `coord-diagrams` | Mermaid architecture set | `docs/diagrams/**` |
| `coord-proof-samples-hub` | Proof sample index + tryout | `docs/proof-samples/README.md`, `docs/TRYOUT_PACKET.md` |
| `coord-code-polish` | Python docstring / import hygiene | `src/nlfr/**` (docstrings, naming consistency, dead import cleanup **only** — no behavior change) |
| `coord-contributing` | Contributor onboarding links | `docs/CONTRIBUTING.md`, `docs/USEFULNESS_ROADMAP.md`, `docs/IMPLEMENTATION_DAG.md` |

### coord-diagrams required diagrams

| File (under `docs/diagrams/`) | Subject |
|-------------------------------|---------|
| `evidence-loop.mmd` | Record → ingest → export → canvas |
| `broker-orchestration.mmd` | Parent broker → coordinators → workers |
| `canvas-projection-flow.mmd` | Projection JSON → truth labels → canvas |
| `truth-label-ladder.mmd` | source_kind × confidence × redaction_state |

Each diagram: mermaid source + short markdown wrapper with claim boundary caption.

---

## Parent acceptance checklist (wave 3)

- [ ] `docs/INDEX.md` lists all four Diátaxis quadrants with at least two links each.
- [ ] README passes Harmony-style structure (see above).
- [ ] Adoption docs share identical command blocks for core proof path where applicable.
- [ ] Four mermaid diagrams present with truth-label captions.
- [ ] `docs/proof-samples/README.md` indexes every sample JSON with labels.
- [ ] CONTRIBUTING ↔ USEFULNESS_ROADMAP ↔ IMPLEMENTATION_DAG mutually linked.
- [ ] `coord-code-polish` diff contains no logic or behavior changes (docstrings/imports only).
- [ ] No doc claims fleet scheduler, queue time, or action placement without proof block citation.

---

## Related mirrors

- DAG: [`docs/dags/docs-excellence.md`](../../../dags/docs-excellence.md)
- Product rules: `AGENTS.md`
- Prior doc capture: `docs/dags/doc-capture-pass.md`
