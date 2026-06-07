# GHA offline — parent proof gate shift

**Date:** 2026-06-06  
**Branch:** `feat/frontier-wave`  
**Coordinator:** `coord-gha-offline-shift`  
**Status:** SHIPPED (doc land)

---

## Constraint and assumption

| Field | Value |
|-------|-------|
| **Observation date** | 2026-06-06 |
| **Assumption** | GitHub Actions workflows have been **non-green / effectively offline** for ~1 month |
| **Broker rule** | Parent broker **must not block** ship or merge on CI green |
| **Revisit trigger** | First sustained green run on `nlfr-proof.yml` (or operator declares GHA restored) |

This is an operational shift, not a product claim. Do not document CI as passing until workflows actually pass.

---

## Parent proof gates (local only)

At `completion-ritual`, parent runs **host-local** gates only:

```bash
cd /Users/alecbot/Documents/nativelink-agent-flight-recorder
uv run pytest -q
bash -n scripts/*.sh
```

Optional when Nix is available on the host:

```bash
nix develop --command ./scripts/lre-proof.sh
nix develop --command ./scripts/lre-cold-warm-proof.sh
```

**Not required for ship while GHA is offline:**

- GitHub Actions job green (`lre-cold-warm-ci`, `lre-proof-probe`, or any workflow badge)
- Waiting for CI before spawning the next worker wave
- Claiming `lre_cache_parity_observed` from CI artifacts

Workers may still declare `proof_commands` in packets; parent records pass/fail locally and notes CI deferral in provenance.

---

## LRE cold/warm honesty

| Path | Status while GHA offline |
|------|--------------------------|
| Script + tests + blocker samples | **Supported** locally (`bash -n`, fixture-backed pytest) |
| `lre_cache_parity_observed` green on x86_64-linux CI | **Deferred** — do not claim |
| Manual Linux host with Nix | **Optional** green path; operator-owned, not broker-blocking |
| Darwin / macOS dev host | **Blocker sample** remains valid honest outcome |

Green LRE cold/warm parity is **not** a ship gate until either:

1. GHA `lre-cold-warm-ci` runs green again, or  
2. Operator runs `nix develop --command ./scripts/lre-cold-warm-proof.sh` on a manual x86_64-linux host and attaches `data/lre-cold-warm-proof/summary.json` to the review packet.

Until then, cite `docs/proof-samples/lre-cold-warm-proof-blocker-sample.json` or environment-blocker artifacts — not CI success.

---

## PR merge policy (GHA offline)

Merge when **all** of the following hold:

1. **Local parent proof gates pass** (`uv run pytest -q`, `bash -n scripts/*.sh`, plus any DAG-specific local commands declared in the coordinator `completion-ritual`)
2. **Review packet** posted (integration brief, spawn ledger, honesty boundaries, `files_touched` / provenance paths)
3. **Human review** per operator policy (not substituted by CI)

**Do not require:**

- CI green on the PR
- Workflow badge / check run success
- Blocking broker loop until Actions recover

When GHA returns, re-run workflows on open PRs and treat CI green as a **restored** gate — update this handoff and `ship-packet.md` in a follow-up wave.

---

## Broker integration

Per [broker-dispatch-manifest.md](/Users/alecbot/Documents/knowledge-os/agent-os/harness/broker-dispatch-manifest.md):

- **Proof ownership** stays with parent at `completion-ritual`; commands above replace any CI-only gate in coordinator packets.
- **`completion-ritual`** may ship with `DONE_WITH_CONCERNS` when the only concern is deferred CI — must cite this handoff.
- **Spawn ledger** records `coord-gha-offline-shift` as SHIPPED after doc land.

Repo product rules unchanged: [AGENTS.md](../../../../AGENTS.md) — evidence-first, honest truth labels, no invented backend state.

---

## Files touched (this wave)

| File | Action |
|------|--------|
| `docs/sessions/handoffs/frontier-wave/wave-1/gha-offline-proof-shift.md` | NEW — this handoff |
| `docs/sessions/handoffs/frontier-wave/wave-0/ship-packet.md` | UPDATE — proof gates + merge policy |
| `docs/sessions/handoffs/frontier-wave/wave-0/spawn-ledger.md` | UPDATE — coordinator row |
| `docs/dags/README.md` | UPDATE — orchestration proof-gate note (if needed) |
