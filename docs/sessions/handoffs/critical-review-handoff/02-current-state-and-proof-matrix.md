# Current state and proof matrix

← [01-product-vision-and-thesis.md](01-product-vision-and-thesis.md) · [README](README.md)

**As of:** 2026-06-07 · Branch `feat/docs-wiki-wave2` · Tag reference `v0.2.0-mvp` on `main`

---

## Repository posture

| Item | Value |
|------|-------|
| Tests | **140 passed, 3 skipped** (`uv run pytest -q`) |
| Open PR | [#10](https://github.com/heyitsalec/nativelink-agent-flight-recorder/pull/10) — wiki wave 2 + KOS waves 1–13 |
| CI | **GHA offline** (~1 month); local gates primary |
| Control plane | **KOS local primary** (`kos serve`, `linear_authority: false`) |
| DAG | `dag:nlfr-flagship` — waves 1–13 closed **DONE_WITH_CONCERNS** |
| Default canvas | `canvas-dev` **`collectable_v1`** (dogfood record) |

---

## Architecture snapshot

```text
┌─────────────────────────────────────────────────────────────┐
│  nlfr CLI (Python)                                          │
│  run · ingest · graph export · proof export · compare · init  │
└──────────────────────────┬──────────────────────────────────┘
                           │ SQLite + artifact manifest
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Parsers: Bazel BEP/profile/exec log · worker_admin_stdout  │
│  Projectors: action graph · proof packet · compare/history  │
└──────────────────────────┬──────────────────────────────────┘
                           │ projection JSON (truth-labeled)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  apps/canvas (Vite/React) — read-only, no SQLite writes     │
│  lenses: Graph · Proof · Remote Boundary · Compare          │
└─────────────────────────────────────────────────────────────┘
```

**Why SQLite + JSON projections:** Durable evidence authority stays in the recorder; the canvas is
replaceable and cannot become source of truth.

---

## Milestone substrate (M5–M9, pre-umbrella)

These shipped on `main` before/alongside KOS cutover waves:

| Milestone | Delivers | Why it mattered |
|-----------|----------|-----------------|
| **M5** | `nlfr-proof.yml`, CI_RECIPE, ADOPTION_GUIDE | Skeptic path off author's Mac (blocked by GHA offline) |
| **M6** | Real default projection + fixture fallback banner | First screen can be `collectable_v1`, not only fixtures |
| **M7** | `worker_admin_stdout` parser + proof script | One legitimate remote claim without fleet fantasy |
| **M8** | `record-agent-change.sh`, Cursor adapter docs | Live agent provenance shape (host-gated) |
| **M9** | `compare export/index/history`, compare lens | Pairwise history without queue/worker correlation |

---

## Proof matrix — what is proven

| Capability | Truth label | Confidence | How to verify |
|------------|-------------|------------|---------------|
| Fixture evidence path | `simulated_v1` | high | `uv run pytest -q`; README Path A |
| Cache cold/warm economics | `collectable_v1` | high | `scripts/cold-warm-cache-proof.sh` (Nix) → `data/cold-warm-proof/summary.json` |
| One-process local-exec smoke | `collectable_v1` | high | `scripts/local-exec-proof.sh` |
| Two-worker endpoint readiness | `collectable_v1` | high | `NLFR_EXPECTED_WORKERS=2` local-exec script; **not** distributed work |
| Worker identity (conditional) | `collectable_v1` | high when stdout matches | `scripts/worker-evidence-proof.sh` |
| Agent loop chain closure | mixed | high for chain flag | `scripts/agent-loop-proof.sh` — validation collectable, agent simulated |
| Tier1 live Bazel agent acts | `collectable_v1` | high on Nix | `scripts/tier1-live-bazel-proof.sh` |
| Canvas from projection only | `derived_v1` | high | `npm --prefix apps/canvas run test:truth` |
| Compare across run groups | `derived_v1` | high | `nlfr compare export`, `scripts/compare-proof.sh` |
| Multi-run history export | `derived_v1` | high | `nlfr compare history`, `tests/test_compare_history.py` |
| Retention policy v1 | `derived_v1` | high | index-only, no auto-purge — `retention_policy.py` |
| Adoption init path | `derived_v1` | high | `nlfr init`, `tests/test_init_cmd.py` |
| PR proof markdown export | `derived_v1` | high | wave 8 exporter + sample |
| 8-node canvas default cap | `derived_v1` | high | `tests/test_canvas_node_cap.py` |
| Doctor environment honesty | `collectable_v1` / blocker | high | `nlfr doctor --mode cache-only --json` |
| dag-gui handoff bridge | `collectable_v1` | high | `wave-9/cutover-manifest.json` |

**Public redacted samples:** `docs/proof-samples/` — use for demos without Nix.

---

## Proof matrix — what is NOT proven

| Claim | Status | Documented in |
|-------|--------|---------------|
| Scheduler assignment | **Unproven** | ONE_PAGER, gap honesty packet |
| Queue time | **Unproven** | ONE_PAGER, future-fleet-claims DAG |
| Action placement | **Unproven** | ONE_PAGER |
| Load distribution across workers | **Unproven** | README two-worker caveat |
| Multi-machine fleet behavior | **Unproven** | future-execution-ladder |
| Org-scale run trends | **Unproven** | M9 pairwise only |
| Sustained GHA green | **Blocked** | C-UMB-1, gha-offline-proof-shift |
| CI proof-sample promotion | **Deferred** | C-UMB-2 |
| Live Cursor on all hosts | **Host-gated** | C-UMB-4, wave 2 |
| LRE Linux parity on Darwin | **Host-gated** | C-UMB-5, wave 3 |
| Full operator / fleet console | **Blocked by policy** | C-UMB-6, wave 13 |

Run `./scripts/fleet-claims-audit.sh` → `data/fleet-claims-audit/claim-matrix.json` for
machine-readable claim audit.

---

## Wave-delivered capabilities (umbrella 1–13)

Grouped by **user outcome**, not file tree:

### Demo and canvas (waves 1, 6, 13)

- **Why:** Evaluators judge with eyes first; dishonest defaults destroy trust.
- **Built:** Run-group selector, real `canvas-dev` default, 8-node cap + overflow chip, lens polish,
  truth-guard Playwright tests.
- **Residual:** Ergonomics ≠ fleet ops UI.

### Live proof paths (waves 2, 3, 5)

- **Why:** Reference kit needs at least one non-fixture agent and LRE narrative.
- **Built:** Agent-live scripts, Cursor adapter, LRE runbooks, honest `environment_blocker` samples.
- **Residual:** Full live proof requires operator host (Cursor CLI, x86_64-linux for LRE).

### CI and gates (waves 4, 7, 10)

- **Why:** Skeptics discount "works on my Mac"; CI recipe must exist even when offline.
- **Built:** GHA restore runbook, `cache-only-ci-gate.sh`, `verify-gha-readiness.sh`, ci-offline sample.
- **Residual:** No sustained green runs observable.

### Operator bridge (waves 6, 8, 9, 12)

- **Why:** Day-to-day usefulness needs retention, PR attachment, history, KOS manifest for dag-gui.
- **Built:** Retention policy, PR markdown exporter, compare history, cutover manifest, gap honesty.
- **Residual:** PR comment automation optional; Harmony/Electron is cross-repo.

### Adoption (wave 11)

- **Why:** Proof kit too repo-specific blocks third-party evaluators.
- **Built:** `nlfr init`, config module, adopt-existing-Bazel wiki, `record-this-target.sh`.
- **Residual:** Still requires Bazel/NativeLink literacy for real path.

---

## Evaluator paths

| Path | Time | Requirements | What you prove |
|------|------|--------------|----------------|
| **A — Fixture** | ~5 min | uv, npm | Labels, canvas contract, pytest green |
| **B — Nix real proof** | ~30+ min | nix develop, ~82GB disk | Cold/warm, agent-loop, worker M7 |
| **C — Proof samples only** | ~10 min | browser | Narrate real summaries without running Bazel |
| **D — Full verify** | ~15 min | uv | `./scripts/verify-demo.sh` local gate bundle |

Canonical spine from [AGENTS.md](../../../../AGENTS.md):

```bash
python3 -m pytest
python3 -m nlfr doctor --mode cache-only
python3 -m nlfr run --scenario tri-agent-loop --mode cache-only --target //...
python3 -m nlfr graph export --run-group latest
python3 -m nlfr proof export --run-group latest
```

---

## PR #10 scope (integration under review)

**Title:** docs: wiki wave 2 — contracts, compare sample, KOS roadmap

**Includes:**

- Wiki contracts reference (artifact manifest, projection schemas, proof packet v1).
- M9 compare proof samples + fixture tests.
- How-to: adopt existing Bazel monorepo, browse run history.
- Full `nlfr-kos-cutover` handoff tree waves 1–14.
- Waves 10–13 code: GHA readiness, `nlfr init`, compare history, canvas node cap.

**Documented residuals in PR body:**

- GHA offline — no sustained green.
- Fleet parsers blocked — honesty packet only.
- M8/LRE live — operator-host gated.

**Review question:** Is docs+local-gate completion sufficient to merge while CI is offline?

---

## Local verification bundle (umbrella close)

From [umbrella-close-packet.md](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md):

```bash
uv run pytest -q
bash -n scripts/*.sh
./scripts/verify-gha-readiness.sh
./scripts/cache-only-ci-gate.sh
PYTHONPATH=src uv run python -m nlfr init --help
PYTHONPATH=src uv run python -m nlfr compare history --help
npm --prefix apps/canvas run test:truth
```

**Recorded result:** 140 passed, 3 skipped (2026-06-07).

---

## Reviewer checklist

- [ ] Every hero GIF and screenshot — which `source_kind`?
- [ ] `apps/canvas/public/projections/` — default is `collectable_v1` dogfood?
- [ ] Proof packet lists unsupported claims matching ONE_PAGER?
- [ ] Compare lens dimensions — any smuggled fleet metrics?
- [ ] Tests assert truth labels, not just JSON shape?
- [ ] `docs/proof-samples/` align with live script outputs?
- [ ] No secrets or raw prompts in committed artifacts?

---

← [01-product-vision-and-thesis.md](01-product-vision-and-thesis.md) · Next: [03-broker-history-and-waves.md](03-broker-history-and-waves.md)
