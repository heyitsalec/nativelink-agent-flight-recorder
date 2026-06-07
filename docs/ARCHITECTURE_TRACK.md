# NLFR Architecture Track

Linear parent: [PER-1058](https://linear.app/gradschool/issue/PER-1058) — **NLFR-ARCH — Architecturally sound track**

Supersedes the launch-demo shortcut. Harden L0–L2 before expanding L3/L4 or changing product shape.

## One sentence

Freeze the evidence spine, quantify cache reuse, climb the remote-execution ladder one claim at a time, close the agent loop with one real patch, then choose product shape from buyer signal — never UI or narrative ahead of collectable proof.

## Principle 1 — Evidence before narrative

Every phase ends with collectable proof, not slides.

| Gate | Question |
|------|----------|
| Collect | Did we capture immutable artifacts with SHA-256? |
| Normalize | Are rows idempotent with stable keys? |
| Project | Do all nodes carry four truth labels? |
| Consume | Does canvas render projection JSON only? |
| Ship | Can a skeptic re-run scripts and get the same boundary? |

If a feature cannot pass that ladder, it is not on the sound track yet.

## Principle 2 — Three parallel tracks, one spine

Run in parallel only where write scopes do not collide.

| Track | Purpose | Touch |
|-------|---------|-------|
| **A — Truth spine** | Protect L1–L2 | `src/nlfr/`, `contracts/`, projectors |
| **B — Toolchain proof** | Deepen L0 | Nix, `demo/nativelink/`, proof scripts |
| **C — Tryout surface** | L4 packaging | `docs/`, README, ONE_PAGER |

Never let C rewrite what B proved. Never let canvas (L3) add claims B did not collect.

## Phase map

### Phase 0 — Frozen foundation (done; maintain)

SQLite + manifest + ingest + projectors + canvas.

Foundation issues: PER-998, PER-1007, PER-1013, PER-1019, PER-1053.

**Rule:** no schema/contract breaks without migration + fixture tests.

### Phase 1 — Reference kit credibility (Ring 1) → **M1**

**Goal:** External evaluator can trust the story in 5 min or 30 min.

- Merge [PR #2](https://github.com/heyitsalec/nativelink-agent-flight-recorder/pull/2) → tag tryout release
- Dual-path docs stay honest (fixture ≠ real proof)
- Optional: redacted `docs/proof-samples/` from real `summary.json`
- **Not:** new features; polish and packaging only

**Exit:** A-O1 (PER-1055), D-O1 (PER-1057) sign-off.

### Phase 2 — Quantified “fast” (Ring 3, cache leg) → **M2** (done)

**Goal:** “Fast” is measurable in proof JSON, not rhetoric.

**Proven (Nix, `collectable_v1`):** cold `hit_rate` 0.0 / 8.17s vs warm
`hit_rate` 1.0 / 5.48s (`warm_hit_rate_higher` and `warm_duration_lower` both
true). Evidence: `data/cold-warm-proof/summary.json`.

- Re-run cold/warm in Nix; persist timing + cache `hit_rate` in proof packet
- Projector exposes collectable cache economics (hits, misses, rate — not dollar claims)
- Canvas shows cache block from proof only

**Exit:** Proof packet shows warm run with higher `hit_rate` or lower duration than cold (`collectable_v1`).

**Stop:** Do not claim “10× faster” without artifact-backed deltas.

### Phase 3 — Execution ladder (Ring 3, remote leg) → **M3** (two-worker live)

Strict order — each step is a new claim boundary:

```
1-worker endpoints ready     ← Nix proof exists (635ee36)
        ↓
2-worker live endpoints      ← Nix proof exists (worker_endpoints_ready, 2 configured)
        ↓
Direct worker/admin log ingest  ← M7 landed (worker_admin_stdout parser)
        ↓
Worker identity (conditional)   ← M7: collectable_v1 when stdout attached + regex match
        ↓
Action placement / scheduler / queue (only if direct evidence exists)
        ↓
Multi-machine / LRE / fleet
```

- **2-worker (done):** `NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w scripts/local-exec-proof.sh`
  ran live in Nix → `data/local-exec-proof-2w/summary.json` with
  `status=completed`, `worker_readiness.status=worker_endpoints_ready`,
  `expected_workers=2`, `configured_workers=2`, no environment blocker
  (`collectable_v1`). This proves two workers configured AND endpoints opened
  live — not work distribution.
- **M7 worker identity (done):** `worker_admin_stdout` ingests admin stdout rows;
  graph/proof promote `worker_identity` when stdout is attached pre-ingest and
  regex matches (`collectable_v1`, `high`). Proof:
  `scripts/worker-evidence-proof.sh` → `data/worker-evidence-proof/summary.json`
  with `worker_identity_observed: true`. Default path is fixture-replay; live
  stdout when Nix + chained local-exec. Honest ceiling — not scheduler/fleet UI.
- **Parsers:** M7 structured rules on attached stdout; no promotion without matching rows
- **Graph:** worker nodes only when SQLite has direct `worker_admin_identity_v1` evidence rows

**Still unsupported:** scheduler assignment, queue time, action placement, load
distribution. Worker identity is conditional on M7 stdout capture — not a
scheduler, queue, placement, or fleet-ops claim.

**Exit:** Each step has `summary.json` + pytest + no softened blockers.

### Phase 4 — Agent loop closure (Ring 2 → 3 bridge) → **M4** (proven)

**Goal:** Connect “agent changed code” to “validation ran” without token firehose.

- `nlfr simulate` scenarios (backbone) — already there
- One bounded LLM patch path with full provenance chain — `demo/scenarios/llm-bounded-patch.json`
- Optional: thin adapter docs for Cursor/Bazel monorepo (reference architecture, not product)

**Proven (Nix, `collectable_v1`):** `scripts/agent-loop-proof.sh` applies the
bounded `llm-bounded-patch` scenario to a copied workspace (never the source),
runs Bazel through the NativeLink cache, ingests validation+cache evidence with
`simulate --ingest`, and exports projections. The action graph then shows the
chain `agent → (authored_change) → change → (validated_by) → run →
evaluated_target → target → produced_action → action → observed_cache_event →
cache_event`. Evidence: `data/agent-loop-proof/summary.json` with
`chain_complete=true`. The patch carries a `model` label and a SHA-256 prompt
hash only; the raw prompt is never stored or exported (AGENTS.md privacy rule).
The graph projector now also derives the `agent` node from the
`agent_provenance` proof block plus the `changes` table, with new edge kinds
`authored_change` and `validated_by`.

**Exit:** One end-to-end proof run: patch → run → ingest → graph shows agent → patch → validation → cache/execution evidence.

**Stop:** Do not build agent marketplace, auth, or fleet scheduling.

### Phase 5 — Product shape fork (only after Phase 2–4)

| Shape | Build when | Architecture add |
|-------|------------|------------------|
| Reference architecture | DevRel/fundraising wins | Playbooks, example repos, integration guides |
| Operator console | Platform teams want fleet view | Read-only analytics plane; still no canvas inventing state |
| Provenance layer | Enterprise wants audit/history | Multi-run retention, export APIs — not multi-tenant SaaS first |

**Default for NLFR:** reference architecture first. Console and provenance layer are projections of the same spine, not new truth sources.

## Milestones

| Milestone | Proves | Ring | Status | Linear |
|-----------|--------|------|--------|--------|
| M1 | PR merged + tryout tag | Ring 1 ~95% | done | child of PER-1058 |
| M2 | Cold/warm metrics in proof packet | Ring 3 cache leg | done (`data/cold-warm-proof/summary.json`) | child of PER-1058 |
| M3 | Two-worker live Nix `summary.json` | Ring 3 cache+remote leg | done (`data/local-exec-proof-2w/summary.json`) | child of PER-1058 |
| M4 | One bounded LLM patch + full provenance chain | Ring 2+3 bridge | done (`data/agent-loop-proof/summary.json`) | child of PER-1058 |

After M4: credibly at reference-kit + credible substrate demo, not operator
console or enterprise provenance yet. M7 adds conditional worker identity when
admin stdout is captured (`collectable_v1`, `high`); scheduler assignment,
queue time, action placement, and load distribution remain unsupported.

## Decision rules

| Question | Answer |
|----------|--------|
| Needs new collectable artifacts? | Track B before canvas (L3) |
| Only changes how we explain existing proof? | Track C |
| Adds a new claim type? | Design brief: allowed vs unsupported; parser before UI |
| Touches `contracts/` or DB schema? | Serialize; one integrator; fixture tests |
| Would a blocker be reported as success? | Stop; architectural violation |

## Anti-tracks

From `AGENTS.md` and product framing:

- SaaS, auth, billing, multi-tenancy
- Worker/scheduler dashboard that invents queue time or placement
- OTLP/Jaeger clone
- Canvas as source of truth (must stay projection-only)
- LLM-heavy demo load before toolchain ladder is stable
- Claiming worker correlation without direct evidence parsers

## Proof commands

```bash
uv run pytest tests -q
npm --prefix apps/canvas run build
scripts/verify-demo.sh

# Real toolchain (inside nix develop):
scripts/cold-warm-cache-proof.sh
scripts/local-exec-proof.sh
NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w scripts/local-exec-proof.sh
scripts/agent-loop-proof.sh
npm --prefix apps/canvas run capture
```
