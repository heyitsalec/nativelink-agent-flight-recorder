# ci-bazel-tier1 — spawn ledger

| worker | status | artifact |
|--------|--------|----------|
| ci-bazel-script | DONE | `scripts/tier1-bazel-ci-proof.sh` |
| ci-bazel-workflow | DONE | `.github/workflows/nlfr-proof.yml` job `tier1-bazel` |
| ci-bazel-tests | DONE | `tests/test_tier1_bazel_ci.py` |

Gate: `nix develop --command ./scripts/tier1-bazel-ci-proof.sh`
