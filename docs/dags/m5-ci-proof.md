# M5 — CI proof on Linux/x86_64

Linear: PER-1065 (proposed) · Parent: PER-1058

## Objective

Remove "only works on author's Mac in Nix" objection. Independent `collectable_v1` proof artifacts.

## Deliverables

- `.github/workflows/nlfr-proof.yml` (or chosen CI host from R-wave)
- Redacted proof samples from CI run
- `docs/CI_RECIPE.md`, `docs/ADOPTION_GUIDE.md`
- `summary.json` gate

## Proof commands

```bash
uv run pytest -q
scripts/cold-warm-cache-proof.sh   # inside nix develop on Linux
scripts/agent-loop-proof.sh
```

## Handoff checklist

- [x] Collect gate: CI workflow + local proof scripts emit `summary.json`
- [x] Normalize gate: idempotent ingest unchanged
- [x] Project gate: truth labels on exported JSON
- [x] Ship gate: ADOPTION_GUIDE skeptic path documented
- [ ] CI promotion: redacted samples from first green GHA run → `docs/proof-samples/`

Blocked by: nothing. Blocks: Wave 1.5 e2e credibility.
