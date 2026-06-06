# Host Toolchain Assessment

Date: 2026-06-06 (updated after PER-1019 proof pass)

## Toolchain-Ready Host (Nix develop)

| Tool | Status |
|------|--------|
| Nix (Determinate) | Installed; `nix develop` available |
| NativeLink | 1.3.2 (from flake) |
| Bazel | 9.1.1 via Bazelisk shim |
| Disk | ~82GB free after cleanup (required for first proof run) |

## Proof Results (commit `635ee36`)

| Script | Result |
|--------|--------|
| `scripts/cold-warm-cache-proof.sh` | Exit 0 — cold + warm completed |
| `scripts/local-exec-proof.sh` | Exit 0 — `worker_endpoints_ready` |

Summary artifacts (ignored under `data/`):

- `data/cold-warm-proof/summary.json`
- `data/local-exec-proof/summary.json`

## Fixes in `635ee36`

- `demo/nativelink/cache-only.json` updated to NativeLink 1.3.x `stores` array schema
- Bazel 9 runner/ingest compatibility fixes

## Outside Nix Shell

Bazel/NativeLink are not on bare PATH outside `nix develop`. Run proof scripts
inside the dev shell or devcontainer per `docs/DEV_ENVIRONMENT.md`.

## Next Host Work

- Two-worker gate (`NLFR_EXPECTED_WORKERS=2`) when config supports it
- Full LRE on Linux/x86_64-style environment
- Direct worker/admin/log evidence before claiming worker identity, queue time,
  scheduler assignment, action placement, or load distribution
