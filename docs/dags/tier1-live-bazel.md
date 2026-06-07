# Tier1 live Bazel — broker DAG

**Parent:** PER-TIER1-AGENT (validation leg)  
**Handoffs:** `docs/sessions/handoffs/tier1-live-bazel/wave-1/`

## Objective

Prove tier1 Acts 1+2 end-to-end with real Bazel validation via `tier1-agent-demo.sh`, not pytest fallback.

## Proof script

```bash
nix develop --command ./scripts/tier1-live-bazel-proof.sh
```

Output: `data/tier1-live-bazel/summary.json` (gitignored) or `environment-blocker.json`.

## Tests

```bash
uv run pytest tests/test_tier1_live_bazel.py -q
```

Blocker smoke runs without Bazel. Live gate:

```bash
NLFR_RUN_TIER1_LIVE_BAZEL=1 nix develop --command uv run pytest tests/test_tier1_live_bazel.py -q
```

## Truth labels

`collectable_v1` on successful live acts. Does not claim LRE, worker placement, or Act 3 compare.

## Relation to ci-bazel-tier1

| DAG | Scope |
|-----|-------|
| [ci-bazel-tier1.md](ci-bazel-tier1.md) | Isolated `//tasks:priority_test` Bazel validation per act setup |
| tier1-live-bazel | Full `tier1-agent-demo.sh` acts 1+2 with live Bazel |

Both require `nix develop` for the green path.
