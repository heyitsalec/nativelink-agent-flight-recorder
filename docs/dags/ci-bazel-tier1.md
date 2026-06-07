# CI Bazel Tier1 — broker DAG

**Linear:** PER-TIER1-AGENT (validation leg)  
**Handoffs:** `docs/sessions/handoffs/ci-bazel-tier1/`

## Objective

Prove tier1 Act 1+2 validation commands with real Bazel (`//tasks:priority_test`), not pytest fallback.

## Proof script

```bash
nix develop --command ./scripts/tier1-bazel-ci-proof.sh
```

Output: `data/tier1-bazel-ci/summary.json` (gitignored) or `environment-blocker.json`.

## CI

Job `tier1-bazel` in `.github/workflows/nlfr-proof.yml` (Nix shell).

## Truth labels

`collectable_v1` on successful Bazel runs. Does not claim LRE or worker placement.
