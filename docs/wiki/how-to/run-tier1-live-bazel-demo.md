# How-to: run tier1 live Bazel demo

**Quadrant:** How-to · **Audience:** demo operators, NativeLink evaluators  
**Track:** Tier1 live Bazel (Acts 1+2)

Prove tier1 Acts 1 and 2 with **real Bazel validation** via `tier1-agent-demo.sh`,
not pytest fallback alone.

← [Wiki hub](../README.md) · [Demo script](../../DEMO_SCRIPT.md)

## Scope boundary

| In scope | Out of scope |
|----------|--------------|
| Live Bazel validation for tier1 Acts 1+2 | LRE cold/warm parity |
| `collectable_v1` on successful live acts | Worker placement, queue time |
| `data/tier1-live-bazel/summary.json` | Act 3 compare (M9 separate path) |

## Prerequisites

```bash
nix develop
```

Tier1 green path expects Nix-wired Bazel and demo workspace. Read
[Dev environment](../../DEV_ENVIRONMENT.md) if toolchain is missing.

## Run live proof

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

Output:

- Success: `data/tier1-live-bazel/summary.json` (gitignored)
- Blocker: `environment-blocker.json` with honest probe metadata

## Fixture-backed tests (no live Bazel)

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
```

Blocker smoke runs without Bazel installed.

## Live test gate

```bash
NLFR_RUN_TIER1_LIVE_BAZEL=1 nix develop --command \
  uv run pytest tests/test_tier1_live_bazel.py -q
```

## Relation to ci-bazel-tier1

| DAG | Scope |
|-----|-------|
| ci-bazel-tier1 (`scripts/tier1-bazel-ci-proof.sh`) | Isolated `//tasks:priority_test` per act setup |
| tier1-live-bazel | Full `tier1-agent-demo.sh` acts 1+2 |

Both require `nix develop` for the green path.

## Truth labels

Successful live acts use `collectable_v1` on ingested Bazel evidence. Simulated
demo legs remain `simulated_v1` where fixtures apply.

Reference: [truth labels](../reference/truth-labels.md).

## Local proof gates

Tier1 proof is validated locally:

```bash
uv run pytest -q tests/test_tier1_live_bazel.py
bash -n scripts/tier1-live-bazel-proof.sh
```

## Related

- [First Nix proof](../tutorial/first-nix-proof.md) — cache economics baseline
- [Architecture track § Phase 4](../../ARCHITECTURE_TRACK.md) — agent loop bridge
- [One pager](../../ONE_PAGER.md) — proven vs unproven
