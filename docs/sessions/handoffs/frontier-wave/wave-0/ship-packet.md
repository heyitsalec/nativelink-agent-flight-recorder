# Frontier wave — ship packet

**Date:** 2026-06-06  
**Branch:** `feat/frontier-wave`

## DAGs closed

| DAG | Ceiling | Handoffs |
|-----|---------|----------|
| `tier1-live-bazel` | live Bazel acts 1+2 | `tier1-live-bazel/wave-1/` |
| `fleet-evidence-v1` | stdout ingest on local-exec | `fleet-evidence-v1/wave-0/` |
| `lre-cache-parity` | script + blocker samples; `lre_cache_parity_observed` deferred (GHA offline) | `lre-proof/wave-4/` |

## Key artifacts

- `scripts/tier1-live-bazel-proof.sh`
- `scripts/local-exec-proof.sh` stdout attach
- `scripts/lre-cold-warm-proof.sh`
- CI: `lre-cold-warm-ci` job
- Proof samples: agent-bugfix/feature with `bazel_validated: true`

## Parent proof gates (local only — GHA offline)

**Assumption (2026-06-06):** GitHub Actions non-green ~1 month. Broker must not block on CI.

```bash
cd /Users/alecbot/Documents/nativelink-agent-flight-recorder
uv run pytest -q
bash -n scripts/*.sh
```

Optional on host when Nix is available:

```bash
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

**Not a ship gate while GHA is offline:** CI job green (`lre-cold-warm-ci`, `lre-proof-probe`, or any workflow check).

Handoff: [`frontier-wave/wave-1/gha-offline-proof-shift.md`](../wave-1/gha-offline-proof-shift.md)

---

## PR merge policy (GHA offline)

- Merge when **local gates pass** + **review packet** + operator review
- **Do not** require CI green or block broker on Actions recovery

---

## Honesty

- LRE cold/warm: script/tests/samples local; **CI green not claimed** — green deferred to manual x86_64-linux host or remains blocker sample until GHA returns
- Fleet: worker_identity when stdout lines present — not scheduler UI
- Tier1: real Bazel validation leg in committed proof samples
