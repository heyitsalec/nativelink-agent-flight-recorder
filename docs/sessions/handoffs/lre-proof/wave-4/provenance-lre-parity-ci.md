# Wave 4 LRE cold/warm CI provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Worker:** `lre-parity-ci` (broker mode)

## Scope

| Path | Change |
|------|--------|
| `.github/workflows/nlfr-proof.yml` | `lre-cold-warm-ci` job: Nix develop + `./scripts/lre-cold-warm-proof.sh` + artifact upload |

## Behavior

On `ubuntu-latest`, the job installs Nix (Determinate installer + magic cache), enters `nix develop`, syncs Python deps with `uv sync`, and runs `./scripts/lre-cold-warm-proof.sh`:

- **Green success path:** script exits 0 and `data/lre-cold-warm-proof/summary.json` exists.
- **Honest blocker path:** script exits nonzero and `data/lre-cold-warm-proof/environment-blocker.json` exists (`collectable_v1`).

Job display name is **LRE cold/warm cache parity proof**. Artifacts upload `summary.json`, `environment-blocker.json`, and `projections/` when present (`if-no-files-found: warn`).

Depends on upstream `lre-parity-proof-script` worker for `scripts/lre-cold-warm-proof.sh` and output directory layout.

## Proof

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/nlfr-proof.yml'))"` | YAML parses |
| 2 | Section grep: `data/lre-cold-warm-proof/summary.json` in `lre-cold-warm-ci` | Present in run step + upload paths |

## Honesty ceiling

| Claim | Status | Labels |
|-------|--------|--------|
| CI invokes LRE cold/warm proof on Linux | **Wired** (workflow only) | `collectable_v1`, `high` |
| `lre_cache_parity_observed` green in CI | **Not claimed** until Nix green path runs | `collectable_v1`, `medium` |
| Hermetic container parity / fleet correlation | **Unsupported** (unchanged) | `future` |

## Summary

CI job `lre-cold-warm-ci` proves the phase-4 LRE cold/warm cache parity path or records an honest environment blocker under `data/lre-cold-warm-proof/`, publishing `summary.json` when the proof script succeeds.

---

## JSON envelope

```json
{
  "worker_id": "lre-parity-ci",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-4/",
  "artifacts": {
    "provenance": "provenance-lre-parity-ci.md",
    "updated": [
      ".github/workflows/nlfr-proof.yml"
    ]
  },
  "ci_job": "lre-cold-warm-ci",
  "proof_script": "scripts/lre-cold-warm-proof.sh",
  "output_dir": "data/lre-cold-warm-proof",
  "upload_artifacts": [
    "data/lre-cold-warm-proof/summary.json",
    "data/lre-cold-warm-proof/environment-blocker.json",
    "data/lre-cold-warm-proof/projections/"
  ],
  "yaml_validates": true,
  "blockers": []
}
```
