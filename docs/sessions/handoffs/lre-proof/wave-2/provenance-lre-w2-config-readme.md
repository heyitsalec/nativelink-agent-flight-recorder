# Provenance — lre-w2-config-readme

**Worker:** `lre-w2-config-readme`  
**Wave:** 2  
**Write scope:** `demo/nativelink/lre.json5`, `demo/nativelink/README.md`  
**KOS routing:** `docs/sessions/handoffs/unlock-wave/KOS-startup-routing.md`

---

## Parent pre-work (broker contamination note)

Before broker re-arm, the parent agent added:

| Artifact | State at worker start | Notes |
|----------|----------------------|-------|
| `demo/nativelink/lre.json5` | Untracked new file | Full one-worker LRE substrate config with ports `50071` (public) / `50081` (worker API), filesystem stores under `/tmp/nlfr-nativelink/lre`, header comment distinguishing phase-1 substrate from Nix `--config=lre` |
| `demo/nativelink/README.md` | Unstaged edit | New **LRE Substrate (phase 1)** section; renamed prior “Future full-LRE” block to **Future full-LRE (phase 2 — Nix toolchain)** |

Parent did **not** touch `scripts/lre-proof.sh`, tests, CI, or proof samples in this packet.

---

## Worker verification

### `demo/nativelink/lre.json5`

| Check | Result |
|-------|--------|
| Public listener `127.0.0.1:50071` | Pass (`servers[0].lre_public`) |
| Worker API `127.0.0.1:50081` | Pass (`workers[0].local.worker_api_endpoint` + `servers[1].lre_worker_api`) |
| Exactly one `local` worker | Pass (`grep -c '"local"'` → 1) |
| Scheduler + execution + capabilities | Pass (matches `local-execution.json5` shape) |
| Honest ceiling comment | Pass (phase-1 substrate; not TraceMachina Nix LRE) |

**Worker change:** None — parent file verified complete; no structural edits required.

### `demo/nativelink/README.md`

| Check | Result |
|-------|--------|
| Mentions `lre_substrate_ready` | Pass (parent) |
| Mentions `claim_boundary` | Pass (parent) |
| Bazel command for `50071` | Added by worker (parity with cache-only / local-exec sections) |
| Truth labels (`collectable_v1`, `medium`) | Added by worker |
| Explicit `claim_boundary` supported / unsupported lists | Added by worker (aligned with `scripts/lre-proof.sh` summary schema) |
| Port collision note vs `50051` / `50061` | Added by worker |
| `NLFR_EXPECTED_WORKERS=2` → `configuration_blocker` | Added by worker |

---

## Proof commands (worker run)

```bash
grep -n '50071\|50081' demo/nativelink/lre.json5
grep -c '"local"' demo/nativelink/lre.json5   # expect 1
grep -n 'lre_substrate_ready\|claim_boundary' demo/nativelink/README.md
```

---

## Honesty ceiling (unchanged)

Phase 1 = `lre_substrate_ready` (`collectable_v1`, `medium`). Does **not** claim hermetic Nix `--config=lre`, `lre.bazelrc` parity, fleet dashboards, or queue/action correlation.

Phase 2 remains blocked on `flake.nix` + `MODULE.bazel` TraceMachina LRE wiring per README **Future full-LRE** section.

---

## Claims touched

- `lre_substrate_ready` — documentation + config substrate only (no live Nix proof run in this worker packet)
- `claim_boundary` — README now mirrors `scripts/lre-proof.sh` supported / `unsupported_until_nix_lre_toolchain` lists

## Blockers

None for this worker packet. Live `nix develop --command ./scripts/lre-proof.sh` green path is out of scope (`scripts/**` no-touch); coord-lre-proof / CI workers own script + test proof.
