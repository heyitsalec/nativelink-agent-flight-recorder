# Wave 2.5 Vision Auditor Provenance

**When:** 2026-06-06  
**Branch:** `feat/frontier-wave`  
**Scope:** Post–Wave 2 (M7 worker parser, M8 agent adapter) vs [`ONE_PAGER.md`](../../../ONE_PAGER.md) + [`ARCHITECTURE_TRACK.md`](../../../ARCHITECTURE_TRACK.md)

## Assessment

| Area | Verdict |
|------|---------|
| Evidence-first product rule | **Maintained** — canvas, compare lens, and proof packet render projection JSON only; no invented backend state |
| M7 worker identity | **Landed** — `worker_admin_stdout` parser promotes `worker_identity` when direct stdout rows exist (`collectable_v1`, `high`) |
| M8 agent adapter | **Mostly aligned** — `model` + `prompt_sha256` only; dry-run and pytest path proven; live Cursor session not required for architecture track |
| M5 CI credibility | **Partial** — workflow + local proofs exist; `docs/proof-samples/` still author-Nix sourced, not GHA-promoted |
| M6 real default | **Aligned** — committed `apps/canvas/public/projections/` is `collectable_v1` after `verify-demo.sh` / `record-canvas-build.sh` |
| Phase 3 execution ladder | **Advanced one step** — direct admin stdout ingest exists; four fleet claims remain unsupported |
| Broker / handoff | Wave 2 provenance on disk; Wave 2.5 pack materializing in this review |

## Built vs north star

| North-star claim | Built? | Evidence |
|------------------|--------|----------|
| Immutable artifacts + SHA-256 ingest | Yes | `record-proof.sh`, manifest ingest unchanged |
| Truth labels on every projected node | Yes | graph, proof, compare projectors |
| Canvas projection-only | Yes | `test:truth`, compare lens loads `compare-projection.json` only |
| One promoted worker claim (M7) | Yes | `worker-evidence-proof.sh` → `worker_identity_observed: true` |
| Bounded agent provenance (M8) | Yes (adapter leg) | `record-agent-change.sh --dry-run`, `--provenance-sidecar` |
| Multi-run compare foundation (M9 preview) | **Out of 2.5 scope** — Wave 3; landed separately per wave-3 provenance | `compare-proof.sh`, `derived_v1` compare projection |

## Drift items

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| **High** | [`ONE_PAGER.md`](../../../ONE_PAGER.md) “What is explicitly unproven” still lists **worker identity** wholesale | Split: conditional `worker_identity` when M7 stdout attached; keep scheduler/queue/placement/distribution unproven |
| **High** | [`ARCHITECTURE_TRACK.md`](../../../ARCHITECTURE_TRACK.md) Phase 3 footer still says worker identity unsupported until direct evidence | Update ladder text to match M7 parser + `future-fleet-claims` conditional policy |
| **Medium** | M5 `docs/proof-samples/` not promoted from first green GHA run | **DEFERRED** — GHA offline; promote after green `nlfr-proof.yml` on Linux |
| **Medium** | M8 real non-dry agent E2E (Cursor session → Bazel) not proven | Document in ADOPTION_GUIDE as operator path; keep `simulated_v1` vs `collectable_v1` honest in ONE_PAGER |
| **Low** | M7 default proof mode is fixture-replay, not live Nix stdout | Accept for v1; live path available when `nix develop` + `local-exec-proof.sh` chained |
| **Low** | Test count grew (100 passed, 2 skipped vs wave-4 note of 61) | No product drift; update proof matrices when citing counts |

## Wave 3 gate (M9)

Vision drift does **not** block Wave 3 once this handoff pack + M9 integration brief publish. No north-star thesis change required — M7/M8 close the Wave 2 ladder steps without softening blockers for the four remaining unsupported fleet claims.
