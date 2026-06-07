# Wave 2.5 E2E Verifier Provenance

**Host:** `/Users/alecbot/Documents/nativelink-agent-flight-recorder`  
**Branch:** `feat/frontier-wave`  
**When:** 2026-06-06  
**Agent:** Wave 2.5 E2E verifier (`m5-m9-w25-review`)

## Environment

| Signal | Value |
|--------|-------|
| OS | darwin 25.4.0 |
| Nix | Available (`nix develop -c echo ok` — ~17s cold shell) |
| GHA | **Offline** — CI matrix rows marked **DEFERRED** |
| Supplemental baseline | [`wave-4/human-design-handoff.md`](../wave-4/human-design-handoff.md) local matrix (2026-06-06) |

## Proof matrix — local (this review)

| # | Command | Exit | Result | Key artifacts / notes |
|---|---------|------|--------|------------------------|
| 1 | `uv run pytest -q` | 0 | **PASS** | 100 passed, 2 skipped (~15s) |
| 2 | `./scripts/record-proof.sh` | 0 | **PASS** | `data/record-proof/summary.json`, run `run_b2dceef830b24d0760949a81` |
| 3 | `./scripts/record-canvas-build.sh` | 0 | **PASS** | `data/canvas-dev/summary.json`, run `run_f7167b7d48a4e36e89fb657f` |
| 4 | `npm --prefix apps/canvas run build` | 0 | **PASS** | (via `record-canvas-build.sh` / `verify-demo.sh`) `apps/canvas/dist/` |
| 5 | `npm --prefix apps/canvas run test:truth` | 0 | **PASS** | `schema_ok: true`, `lens_visible: true`, graph parity ok |
| 6 | `./scripts/verify-demo.sh` | 0 | **PASS** | `data/demo-proof/nlfr.sqlite`, committed canvas `collectable_v1` |
| 7 | `./scripts/worker-evidence-proof.sh` | 0 | **PASS** | `data/worker-evidence-proof/summary.json`, `worker_identity_observed: true`, `worker_nodes: 2` |
| 8 | `./scripts/record-agent-change.sh --dry-run --change-path README.md --model composer-2.5 --prompt-file README.md` | 0 | **PASS** | stdout JSON with `prompt_sha256`; no raw prompt |
| 9 | `./scripts/compare-proof.sh` | 0 | **PASS** | `data/compare-proof/summary.json`, 5 dimensions, record-proof vs canvas-dev |
| 10 | `nix develop --command ./scripts/cold-warm-cache-proof.sh` | 1 | **FAIL** | Exited during cold Bazel run (NativeLink server started; cold leg incomplete this session) |
| 11 | `nix develop --command ./scripts/agent-loop-proof.sh` | — | **NOT RUN** | Skipped after cold-warm failure; wave-4 handoff reports PASS for this host date |

### Wave 2 completion proofs (M7 + M8)

| Command | Exit | Result |
|---------|------|--------|
| `./scripts/worker-evidence-proof.sh` | 0 | PASS (fixture-replay default) |
| `./scripts/record-agent-change.sh --dry-run ...` | 0 | PASS |

## Proof matrix — CI (DEFERRED)

**Blocker:** GitHub Actions not executed in this review environment (GHA offline).

| Job / check | Expected command surface | Status |
|-------------|-------------------------|--------|
| `unit` — pytest | `uv run pytest -q` | **DEFERRED** |
| `unit` — `record-proof.sh` | generic record | **DEFERRED** |
| `unit` — canvas dogfood | `record-canvas-build.sh`, `npm build`, `test:truth` | **DEFERRED** (workflow present; not executed) |
| `linux-nix-toolchain` | `cold-warm-cache-proof.sh`, `agent-loop-proof.sh` | **DEFERRED** |
| `verify-demo-fixture` | fixture projection overwrite | **DEFERRED** |
| CI artifact promotion | redacted `summary.json` → `docs/proof-samples/` | **DEFERRED** — depends on first green Linux run |

Honest note: local cold-warm failed in this session; do not treat CI Nix legs as proven here. Wave-4 handoff and existing `docs/proof-samples/cold-warm-summary.json` remain the best available evidence for cold/warm economics until GHA green.

## Wave 4 handoff cross-check (same host, prior run)

| Command | Wave-4 result | This review |
|---------|---------------|-------------|
| `uv run pytest -q` | 61 passed | 100 passed, 2 skipped (test growth) |
| `record-proof.sh` | PASS | PASS |
| `record-canvas-build.sh` | PASS | PASS |
| `worker-evidence-proof.sh` | PASS | PASS |
| `record-agent-change.sh --dry-run` | PASS | PASS |
| `compare-proof.sh` | PASS | PASS |
| `test:truth` | PASS (15/15 nodes) | PASS |

## Summary

- **Wave 2.5 minimum matrix (review-gates.md):** pytest, record-proof, canvas build, test:truth, verify-demo — all **PASS** locally.
- **M7/M8 wave-2 proofs:** **PASS**.
- **M9 compare proof:** **PASS** (`compare-proof.sh`; M9 is Wave 3 deliverable, validated here for completeness).
- **Nix cold-warm:** **FAIL** this session; **DEFERRED** for CI.
- **GHA:** all CI-dependent checks **DEFERRED** with blocker documented.

Wave 3 (M9) is not blocked by local e2e gaps on the fixture-backed spine. CI promotion and live Nix re-proof remain operator follow-ups.
