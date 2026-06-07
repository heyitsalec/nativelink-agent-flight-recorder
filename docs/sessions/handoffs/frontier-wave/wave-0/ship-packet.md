# Frontier wave — ship packet

**Date:** 2026-06-06  
**Branch:** `feat/frontier-wave`

## DAGs closed

| DAG | Ceiling | Handoffs |
|-----|---------|----------|
| `tier1-live-bazel` | live Bazel acts 1+2 | `tier1-live-bazel/wave-1/` |
| `fleet-evidence-v1` | stdout ingest on local-exec | `fleet-evidence-v1/wave-0/` |
| `lre-cache-parity` | `lre_cache_parity_observed` (Linux CI) | `lre-proof/wave-4/` |

## Key artifacts

- `scripts/tier1-live-bazel-proof.sh`
- `scripts/local-exec-proof.sh` stdout attach
- `scripts/lre-cold-warm-proof.sh`
- CI: `lre-cold-warm-ci` job
- Proof samples: agent-bugfix/feature with `bazel_validated: true`

## Honesty

- LRE cold/warm green on **x86_64-linux CI**; Darwin records blocker
- Fleet: worker_identity when stdout lines present — not scheduler UI
- Tier1: real Bazel validation leg in committed proof samples
