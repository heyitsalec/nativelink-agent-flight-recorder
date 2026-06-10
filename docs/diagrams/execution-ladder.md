# Execution ladder

**Caption:** Remote-execution and cache claims climb one rung at a time. Each completed step has `collectable_v1` proof (`summary.json` + pytest). Rungs above the current ceiling are `future` — not projected until direct evidence exists.

```mermaid
flowchart TB
    R0["L0 — Toolchain ready\nNix + Bazel + NativeLink substrate"]
    R1["L1 — Cache-only proof\ncold/warm hit_rate + duration"]
    R2["L2 — 1-worker endpoints\nlocal-exec substrate ready"]
    R3["L3 — 2-worker live endpoints\nconfigured + opened (not distribution)"]
    R4["L4 — Worker admin stdout ingest\nworker_admin_stdout parser"]
    R5["L5 — Worker identity (conditional)\nregex on attached stdout"]
    R6["L6 — Action placement / scheduler / queue\nfuture — direct evidence required"]
    R7["L7 — Multi-machine LRE / fleet\nfuture — host-stable LRE parity"]

    R0 --> R1 --> R2 --> R3 --> R4 --> R5 --> R6 --> R7

    R1 -.->|proven| P1["data/cold-warm-proof/summary.json"]
    R3 -.->|proven| P3["data/local-exec-proof-2w/summary.json"]
    R5 -.->|proven when stdout attached| P5["data/worker-evidence-proof/summary.json"]
    R7 -.->|probe / blocker| P7["data/lre-cold-warm-proof/\nsummary.json or environment-blocker.json"]
```

## Honesty notes

| Rung | Status | `source_kind` | `confidence` | Honest ceiling |
|------|--------|---------------|--------------|----------------|
| L0 toolchain | Proven in Nix | `collectable_v1` | `high` | Substrate starts; not workload economics |
| L1 cache economics | Proven | `collectable_v1` | `high` | `hit_rate`, duration deltas — not "10× faster" rhetoric |
| L2 1-worker endpoints | Proven | `collectable_v1` | `high` | Endpoints ready |
| L3 2-worker live | Proven | `collectable_v1` | `high` | Two workers configured and endpoints opened — **not** work distribution |
| L4 stdout ingest | Proven (M7) | `collectable_v1` | `high` | Parser rows in SQLite |
| L5 worker identity | Conditional | `collectable_v1` | `high` when stdout pre-attached | Identity from admin stdout regex — not scheduler |
| L6 placement / queue | **Unsupported** | `future` | `unknown` | No graph nodes without new parsers |
| L7 LRE / fleet | Partial probe | `collectable_v1` or blocker | `medium` | LRE cold/warm wired; local proof gates canonical until CI restore |

**Stop rules:** If a rung would report a blocker as success, stop — architectural violation. Canvas (L3 consume) must not add claims the ladder did not collect.

**Evidence refs:** `docs/ARCHITECTURE_TRACK.md` Phase 2–3, `scripts/cold-warm-cache-proof.sh`, `scripts/local-exec-proof.sh`, `scripts/worker-evidence-proof.sh`, `scripts/lre-cold-warm-proof.sh`.
