# Extension DAG

Linear parent: [PER-1007](https://linear.app/gradschool/issue/PER-1007/nlfr-9-follow-on-evidence-proof-drawer-and-agent-simulation)

## Objective

Extend NLFR past the MVP with:

1. real NativeLink/Bazel artifact ingest hardening;
2. a canvas proof drawer fed by `proof.json`;
3. a controlled agent simulation wrapper with provenance;
4. final integration proof.

## Children

- PER-1008: real NativeLink/Bazel artifact ingest hardening. Done.
- PER-1009: canvas proof drawer fed by `proof.json`. Done.
- PER-1010: agent simulation wrapper and provenance. Done.
- PER-1011: extension integration proof and completion review. Done.

## Implemented Extensions

- `nlfr ingest <artifact_root>` now reads `run.json` metadata so parsed Bazel
  BEP/profile/execution-log evidence attaches to the original recorder run.
- `scripts/cold-warm-cache-proof.sh` ingests cold and warm run artifacts before
  exporting `run_group=cold-warm` projections.
- Canvas proof mode fetches `/projections/proof.json` and renders a proof drawer
  from packet blocks, metrics, claims, truth labels, and evidence refs.
- `nlfr simulate` copies the demo monorepo, applies deterministic simulated-agent
  scenario patches, records patch/run provenance, and writes DB proof blocks.

## Proof Gates

```bash
uv run pytest tests -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh
```

Canvas changes also require Playwright screenshot/WebM readback.

## Privacy

Use only local demo workspaces, synthetic fixtures, and generated build evidence.
Do not ingest secrets, raw prompts, customer logs, or private source material.

## Stop Conditions

- Parser would need to guess unsupported cache/action truth.
- Canvas proof UI invents claims not present in `proof.json`.
- Agent simulation mutates the source demo workspace instead of a temp copy.
- Real-tool blockers are hidden or softened.
