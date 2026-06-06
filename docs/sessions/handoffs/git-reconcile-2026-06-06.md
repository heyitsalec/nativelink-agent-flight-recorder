# Git Reconcile — 2026-06-06

## Branch state

| Branch | HEAD | Remote |
|--------|------|--------|
| `codex/per-998-nlfr-mvp` | `e90e5f4` | **No upstream** (local only) |
| `fix/nativelink-1.3-bazel9-proofs` | `635ee36` | `origin/fix/nativelink-1.3-bazel9-proofs` |
| `main` | `290a670` | `origin/main` |

`codex/per-998-nlfr-mvp` contains `635ee36` proof fixes via merge history (`e90e5f4` is ahead of `main`).

Remote: `git@github.com:heyitsalec/nativelink-agent-flight-recorder.git`

## Drift flagged (Sub-DAG A scope)

1. **README.md** lines 75–77: still says bare-Mac cache-only is blocked — correct for outside Nix, but omits Nix-first success path from PER-1019.
2. **TRYOUT_PACKET.md** lines 46–48: stale "not on PATH" paragraph contradicts PER-1019 real-tool section below.
3. **codex/per-998-nlfr-mvp** not pushed — GitHub visitors see older `main` without `635ee36`.

## Action

Sub-DAG A-I1/I3 addresses README + GitHub hygiene.
