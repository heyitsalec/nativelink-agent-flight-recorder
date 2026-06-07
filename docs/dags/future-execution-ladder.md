# Future execution ladder — LRE, Bazel CI, worker dashboards

**Status:** research + blocker-gated (not active broker DAGs)  
**Parent:** [architecture-track.md](architecture-track.md) · PER-1058  
**Policy:** [`AGENTS.md`](../AGENTS.md) v1 order item 6; explicit out-of-scope list

---

## What these are (plain language)

### LRE path (Local Remote Execution)

**NativeLink product territory:** Nix-generated toolchains that run **identically** on a developer laptop and on remote workers, so cache keys stay valid across machines. NativeLink markets this as a major differentiator vs Buildfarm/Bazel RBE.

**NLFR meaning:** Record a Bazel workload where validation actually flows through NativeLink **remote execution** (not just cache-only or local-exec smoke), ingest stdout/admin evidence, and export projections with honest `collectable_v1` labels.

**Current state:** Cache-only and local-exec proofs exist (`cold-warm-cache-proof.sh`, `local-exec-proof.sh`). **Phases 1–4 script path shipped:** `lre_substrate_ready` → `lre_bazelrc_generated` → `lre_cache_parity_observed` via `scripts/lre-proof.sh`, `scripts/lre-nix-toolchain-proof.sh`, and `scripts/lre-cold-warm-proof.sh` (see [`lre-proof.md`](lre-proof.md)). Redacted schema samples in [`proof-samples/`](../proof-samples/README.md).

**Manual Linux path (phase 4, GHA offline):** `lre_cache_parity_observed` requires x86_64-linux inside `nix develop`. Operators follow [`LRE_LINUX_PROOF.md`](../LRE_LINUX_PROOF.md). On Darwin the script records honest `environment-blocker.json` (exit `2`) — cite [`lre-cold-warm-proof-linux-manual-sample.json`](../proof-samples/lre-cold-warm-proof-linux-manual-sample.json) or [`lre-cold-warm-proof-blocker-sample.json`](../proof-samples/lre-cold-warm-proof-blocker-sample.json). Promote green `summary.json` only after a real Linux run; do **not** fabricate parity metrics.

**CI promotion:** `lre-cold-warm-ci` artifact green deferred while GHA offline (wave 4). Manual Linux sample closes the evaluator gap without claiming CI green.

**Broker?** **`lre-proof` waves 2–4 script path shipped.** Do **not** broker fleet dashboards or hermetic container-image parity ahead of new collectable parsers and direct evidence.

---

### Real Bazel validation in CI

**Meaning:** Tier 1 agent scenarios (`agent-bugfix-1`, `agent-feature-compare`) run `bazel test //tasks:priority_test` in GitHub Actions (or Nix job), not only `NLFR_SKIP_BAZEL=1` pytest fallback.

**Current state:** **Done** — `scripts/tier1-bazel-ci-proof.sh` proves Act 1+2 validation with real Bazel (`//tasks:priority_test`); CI job `tier1-bazel` in `.github/workflows/nlfr-proof.yml` (Nix shell). Output: `data/tier1-bazel-ci/summary.json` or `environment-blocker.json`.

**Broker?** **`ci-bazel-tier1` shipped.** Does not claim LRE or worker placement.

---

### Worker / scheduler dashboards

**Meaning:** Fleet ops UI — which worker ran which action, queue depth, scheduler assignment, OTLP/Jaeger-style traces. “Where did my build go?” at fleet scale.

**NLFR policy:** **Explicitly out of scope for v1** (`AGENTS.md`). Remote Boundary lens shows **configured** remote execution only; ONE_PAGER lists queue time, scheduler assignment, action placement as **unproven**.

**Current evidence ceiling:** `worker_endpoints_ready` (two workers configured + live endpoints) — not distribution, not identity correlation across runs.

**Phase-3 blocker (fleet parsers):** Direct worker/admin log ingest and action-placement claims require **new collectable parsers**, SQLite proof blocks, and pytest per [`ARCHITECTURE_TRACK.md`](../ARCHITECTURE_TRACK.md) Phase 3 ladder — not research-matrix sync alone.

**Broker?** **No implementation DAG.** **Wave-1 done:** research-only DAG [`future-fleet-claims.md`](future-fleet-claims.md) keeps honesty docs synchronized via `fleet-claims-audit.sh` claim matrix — never spawn implement workers without new **direct evidence parsers** and SQLite rows. Reject Harmony-style fake worker personas.

---

## Recommended broker order (when unblocked)

| Priority | DAG id | Gate |
|----------|--------|------|
| — | *(done)* tier1-agent-vision wave 5 | integrate + dogfood |
| — | *(done)* `lre-proof` waves 2–4 + W3 manual Linux | `lre_cache_parity_observed` script path; manual Linux sample or blocker; CI green deferred |
| — | *(done)* `ci-bazel-tier1` | `tier1-bazel` CI job + proof script |
| — | *(done)* `future-fleet-claims` wave-1 | claim matrix + ONE_PAGER sync; phase-3 parsers blocked |
| 1 | `ci-cache-only-gate` | `nlfr doctor --mode cache-only` on every PR |
| 2 | `nlfr-doc-capture` wave 2 | tier1-aligned hero GIF refresh |
| 3 | `tier1-canvas-polish` | composer UI + view/run-group selector |
| — | *(done)* `lre-proof` wave-3 | `lre_bazelrc_generated`; Nix LRE toolchain wired |
| — | *(phase-3)* fleet evidence | direct admin/stdout parsers + SQLite rows (no UI until exit criteria) |

---

## Coordinator rule

Spawn `coord-lre-proof` or `coord-fleet-ui` only when architecture track Phase 3 exit criteria in [`ARCHITECTURE_TRACK.md`](../ARCHITECTURE_TRACK.md) name a **new collectable claim** with parser + pytest — not when a demo “needs” richer visuals.
