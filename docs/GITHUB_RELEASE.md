# GitHub Release Hygiene

## Recommended default branch

Point evaluators at a branch containing commit `635ee36` or later (NativeLink
1.3.2 + Bazel 9 proof paths) plus vision DAG doc updates.

Current integration branch: `codex/per-998-nlfr-mvp`.

## Pre-release checklist

1. `uv run pytest tests -q` — 41 passed
2. `npm --prefix apps/canvas run build`
3. `scripts/verify-demo.sh`
4. Inside `nix develop`:
   - `scripts/cold-warm-cache-proof.sh`
   - `scripts/local-exec-proof.sh`
   - `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh`
5. `npm --prefix apps/canvas run capture` (with preview on :5174)

## Tag message template

```
NLFR tryout kit — NativeLink 1.3.2 + Bazel 9 proof

- Cold/warm cache proof (nix develop)
- Local-exec smoke (worker_endpoints_ready)
- Truth-labeled Action Graph + Proof Packet canvas
- See docs/TRYOUT_PACKET.md and docs/ONE_PAGER.md
```

## What not to commit

- `data/` proof runs (gitignored)
- `output/playwright/` captures (gitignored)
- Secrets, raw logs, customer data

## Redacted proof samples

For release notes, cite sanitized excerpts from `data/*/summary.json` or add
`docs/proof-samples/` with redacted JSON snippets — not full artifact trees.
