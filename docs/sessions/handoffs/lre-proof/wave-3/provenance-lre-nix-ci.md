# Wave 3 LRE Nix toolchain CI provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**When:** 2026-06-06  
**Worker:** `lre-nix-ci` (broker mode)

## Scope

| Path | Change |
|------|--------|
| `.github/workflows/nlfr-proof.yml` | `lre-nix-ci` job: Nix develop + `./scripts/lre-nix-toolchain-proof.sh` + artifact upload |

## Behavior

On `ubuntu-latest`, the job installs Nix (Determinate installer + magic cache), enters `nix develop`, syncs Python deps with `uv sync`, and runs `./scripts/lre-nix-toolchain-proof.sh`:

- **Green success path:** script exits 0 and `data/lre-nix-toolchain-proof/summary.json` exists.
- **Honest blocker path:** script exits nonzero and `data/lre-nix-toolchain-proof/environment-blocker.json` exists (`collectable_v1`).

Job display name is **LRE Nix toolchain proof**. Artifacts upload `summary.json` and `environment-blocker.json` when present (`if-no-files-found: warn`).

Depends on sibling worker `lre-nix-toolchain-probe` (or equivalent) to land `scripts/lre-nix-toolchain-proof.sh` and output directory layout before CI can go green end-to-end.

## Proof

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/nlfr-proof.yml'))"` | YAML parses |
| 2 | Section grep: `data/lre-nix-toolchain-proof/summary.json` in `lre-nix-ci` | Present in run step + upload paths |

## Honesty ceiling

| Claim | Status | Labels |
|-------|--------|--------|
| CI invokes Nix LRE toolchain proof on Linux | **Wired** (workflow only) | `collectable_v1`, `high` |
| `bazel build --config=lre` green in CI | **Not claimed** until proof script + flake/module workers land | `future` |
| Cache hit parity / fleet correlation | **Unsupported** (unchanged) | `future` |

## Summary

CI job `lre-nix-ci` proves the phase-3 Nix LRE toolchain path or records an honest environment blocker under `data/lre-nix-toolchain-proof/`, publishing `summary.json` when the proof script succeeds.

---

## JSON envelope

```json
{
  "worker_id": "lre-nix-ci",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-3/",
  "artifacts": {
    "provenance": "provenance-lre-nix-ci.md",
    "updated": [
      ".github/workflows/nlfr-proof.yml"
    ]
  },
  "ci_job": "lre-nix-ci",
  "proof_script": "scripts/lre-nix-toolchain-proof.sh",
  "output_dir": "data/lre-nix-toolchain-proof",
  "upload_artifacts": [
    "data/lre-nix-toolchain-proof/summary.json",
    "data/lre-nix-toolchain-proof/environment-blocker.json"
  ],
  "yaml_validates": true,
  "blockers": [
    "lre-nix-toolchain-probe"
  ]
}
```
