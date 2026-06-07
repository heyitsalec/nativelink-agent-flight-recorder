# Future execution ladder — LRE, Bazel CI, worker dashboards

**Status:** research + blocker-gated (not active broker DAGs)  
**Parent:** [architecture-track.md](architecture-track.md) · PER-1058  
**Policy:** [`AGENTS.md`](../AGENTS.md) v1 order item 6; explicit out-of-scope list

---

## What these are (plain language)

### LRE path (Local Remote Execution)

**NativeLink product territory:** Nix-generated toolchains that run **identically** on a developer laptop and on remote workers, so cache keys stay valid across machines. NativeLink markets this as a major differentiator vs Buildfarm/Bazel RBE.

**NLFR meaning:** Record a Bazel workload where validation actually flows through NativeLink **remote execution** (not just cache-only or local-exec smoke), ingest stdout/admin evidence, and export projections with honest `collectable_v1` labels.

**Current state:** Cache-only and local-exec proofs exist (`cold-warm-cache-proof.sh`, `local-exec-proof.sh`). LRE is listed as v1 item **#6 — when stable on the host**. Not proven in NLFR yet.

**Broker?** **Yes, but only as a blocker-gated DAG** (`lre-proof`) once `nix develop` + NativeLink LRE config is green on CI or a designated host. Do **not** broker UI or narrative ahead of a real `summary.json`.

---

### Real Bazel validation in CI

**Meaning:** Tier 1 agent scenarios (`agent-bugfix-1`, `agent-feature-compare`) run `bazel test //tasks:priority_test` in GitHub Actions (or Nix job), not only `NLFR_SKIP_BAZEL=1` pytest fallback.

**Current state:** `.github/workflows/nlfr-proof.yml` runs pytest, generic record, canvas dogfood, Nix cold-warm/agent-loop — but **not** demo monorepo Bazel targets for tier1 acts.

**Broker?** **Yes, as a small DAG** (`ci-bazel-tier1`) **after** cache-only `nlfr doctor` gate is stable. Depends on Bazel + Java in CI or Nix shell; estimate 1–2 workers (workflow job + fixture doc). Lower priority than wave 5 close-out.

---

### Worker / scheduler dashboards

**Meaning:** Fleet ops UI — which worker ran which action, queue depth, scheduler assignment, OTLP/Jaeger-style traces. “Where did my build go?” at fleet scale.

**NLFR policy:** **Explicitly out of scope for v1** (`AGENTS.md`). Remote Boundary lens shows **configured** remote execution only; ONE_PAGER lists queue time, scheduler assignment, action placement as **unproven**.

**Current evidence ceiling:** `worker_endpoints_ready` (two workers configured + live endpoints) — not distribution, not identity correlation across runs.

**Broker?** **No implementation DAG.** Optional **research-only** DAG (`future-fleet-claims`) to keep honesty docs synchronized — never spawn implement workers without new **direct evidence parsers** and SQLite rows. Reject Harmony-style fake worker personas.

---

## Recommended broker order (when unblocked)

| Priority | DAG id | Gate |
|----------|--------|------|
| — | *(done)* tier1-agent-vision wave 5 | integrate + dogfood |
| 1 | `ci-cache-only-gate` | `nlfr doctor --mode cache-only` on every PR |
| 2 | `nlfr-doc-capture` wave 2 | tier1-aligned hero GIF refresh |
| 3 | `tier1-canvas-polish` | composer UI + view/run-group selector |
| 4 | `ci-bazel-tier1` | Bazel in CI for tier1 scenarios |
| 5 | `lre-proof` | host has stable LRE + Nix |
| — | `future-fleet-claims` | research only; no UI |

---

## Coordinator rule

Spawn `coord-lre-proof` or `coord-fleet-ui` only when architecture track Phase 3 exit criteria in [`ARCHITECTURE_TRACK.md`](../ARCHITECTURE_TRACK.md) name a **new collectable claim** with parser + pytest — not when a demo “needs” richer visuals.
