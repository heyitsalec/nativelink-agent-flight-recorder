# Provenance — lre-nix-bazel-wire (wave-3)

**Worker:** `lre-nix-bazel-wire`  
**When:** 2026-06-06  
**Coordinator:** `coord-lre-nix-phase3`  
**DAG:** `lre-proof` wave-3  
**Write scope:** `demo/bazel-monorepo/MODULE.bazel`, `demo/bazel-monorepo/.bazelrc`, `demo/bazel-monorepo/.gitignore`, `.gitignore` (lre.bazelrc entries only)  
**Branch:** `feat/lre-fleet-unlocks`  
**Status:** `DONE`

---

## Objective

Wire Bazel-side Local Remote Execution (LRE) for the demo monorepo: import
`@local-remote-execution` via Bzlmod with a `git_override` pinned to the same
NativeLink commit as `flake.lock`, hook generated `lre.bazelrc` via
`try-import`, and ignore the generated file in git.

**Depends on (parallel):** `lre-nix-flake-wire` for `lre.bazelrc` generation in
`nix develop` shellHook — this worker only adds the Bazel consumer side.

---

## flake.lock nativelink rev

| Field | Value |
|-------|-------|
| `nodes.nativelink.locked.rev` | `946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4` |
| `nodes.nativelink.locked.owner` | `TraceMachina` |
| `nodes.nativelink.locked.repo` | `nativelink` |

---

## Changes

### `demo/bazel-monorepo/MODULE.bazel`

| Check | Result |
|-------|--------|
| `bazel_dep(name = "local-remote-execution", version = "0")` | Added |
| `git_override` remote | `https://github.com/TraceMachina/nativelink` |
| `git_override` commit | `946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4` (matches `flake.lock`) |
| `strip_prefix` | `local-remote-execution` (module root at upstream subdir; not upstream README typo `nativelink`) |

### `demo/bazel-monorepo/.bazelrc`

| Check | Result |
|-------|--------|
| `try-import %workspace%/lre.bazelrc` | Added |

Tier1 targets (`//tasks:priority_test`) remain unchanged without `--config=lre`.

### `.gitignore` (repo root + demo)

| Path | Entry |
|------|-------|
| `.gitignore` | `lre.bazelrc`, `demo/bazel-monorepo/lre.bazelrc` |
| `demo/bazel-monorepo/.gitignore` | `lre.bazelrc` |

---

## Proof commands (worker run)

```bash
# Commit pin matches flake.lock
jq -r '.nodes.nativelink.locked.rev' flake.lock
grep '946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4' demo/bazel-monorepo/MODULE.bazel

# Bazel consumer wiring
grep -n 'local-remote-execution\|git_override\|try-import' \
  demo/bazel-monorepo/MODULE.bazel demo/bazel-monorepo/.bazelrc

# Generated file ignored
grep lre.bazelrc .gitignore demo/bazel-monorepo/.gitignore
```

**Post-flake-wire gates (x86_64-linux / nix develop — out of scope for this worker):**

```bash
nix develop --command bash -lc 'test -f demo/bazel-monorepo/lre.bazelrc'
nix develop --command bash -lc \
  'cd demo/bazel-monorepo && bazel build --config=lre @local-remote-execution//examples:lre-cc'
```

---

## Honesty ceiling

**This worker enables (partial phase-3):**

- Bzlmod resolves `@local-remote-execution` at pinned NativeLink commit
- `.bazelrc` ready to load Nix-generated `lre.bazelrc` when flake LRE module lands

**Still unsupported (unchanged):**

- `lre.bazelrc` generation until `lre-nix-flake-wire` completes
- Hermetic local↔remote cache hit parity via `lre.json5` local worker
- `nlfr run --bazel-arg=--config=lre` end-to-end ingest + proof export
- aarch64-darwin `--config=lre` (upstream LRE is x86_64-linux only)
- Fleet / queue / action-placement correlation

---

## Claims touched

- `lre_bazelrc_generated` — **partial** (Bazel import path only; generation deferred to flake worker)
- `claim_boundary.unsupported_until_nix_lre_toolchain` — **not lifted** (MODULE + try-import is necessary but not sufficient)

## Blockers

| Blocker | Owner worker |
|---------|--------------|
| `lre.bazelrc` not generated until flake-parts + `flakeModules.lre` | `lre-nix-flake-wire` |
| `bazel build --config=lre` proof | `lre-nix-toolchain-probe` |

---

## Evidence refs

- `flake.lock` → `nodes.nativelink.locked.rev`
- TraceMachina `templates/bazel/.bazelrc`, `local-remote-execution/README.md`
- `docs/sessions/handoffs/lre-proof/wave-3/provenance-lre-nix-research.md`

---

## JSON envelope

```json
{
  "worker_id": "lre-nix-bazel-wire",
  "status": "DONE",
  "handoff_dir": "docs/sessions/handoffs/lre-proof/wave-3/",
  "artifacts": {
    "provenance": "provenance-lre-nix-bazel-wire.md",
    "created": [
      "demo/bazel-monorepo/.bazelrc",
      "demo/bazel-monorepo/.gitignore"
    ],
    "updated": [
      "demo/bazel-monorepo/MODULE.bazel",
      ".gitignore"
    ]
  },
  "nativelink_rev": "946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4",
  "flake_lock_sync": true,
  "claims_touched": ["lre_bazelrc_generated"],
  "claim_ceiling": "partial_bazel_consumer_wiring",
  "blockers": [
    "lre-nix-flake-wire",
    "lre-nix-toolchain-probe",
    "PLATFORM_DARWIN",
    "CACHE_HIT_PARITY"
  ]
}
```
