# Wave 2 LRE CI probe provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Worker:** `lre-w2-ci-probe` (broker mode)

## Scope

| Path | Change |
|------|--------|
| `.github/workflows/nlfr-proof.yml` | `lre-proof-probe` job: substrate proof step + `summary.json` artifact |

## Behavior

With `demo/nativelink/lre.json5` in the repo, the job runs `nix develop` and `./scripts/lre-proof.sh`:

- **Green success path:** script exits 0 and `data/lre-proof/summary.json` exists (`status: lre_substrate_ready`).
- **Honest blocker path:** script exits nonzero and `data/lre-proof/environment-blocker.json` exists (`collectable_v1`).

Job display name is **LRE substrate proof** (replaces “honest blocker” wording). Artifacts upload `summary.json`, `probe.json`, and `environment-blocker.json` when present.

## Proof

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/nlfr-proof.yml'))"` | YAML parses |
| 2 | Section grep: `data/lre-proof/summary.json` in `lre-proof-probe` | Present in run step + upload paths |

## Summary

CI `lre-proof-probe` now proves LRE substrate readiness or records an honest environment blocker, and publishes `summary.json` when the config path is green.
