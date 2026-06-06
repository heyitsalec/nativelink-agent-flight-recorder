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

### Phase 2 — Quantified “fast” (Ring 3, cache leg) → **M2**

**Goal:** “Fast” is measurable in proof JSON, not rhetoric.

- Re-run cold/warm in Nix; persist timing + cache `hit_rate` in proof packet
- Projector exposes collectable cache economics (hits, misses, rate — not dollar claims)
- Canvas shows cache block from proof only

**Exit:** Proof packet shows warm run with higher `hit_rate` or lower duration than cold (`collectable_v1`).

**Stop:** Do not claim “10× faster” without artifact-backed deltas.

### Phase 3 — Execution ladder (Ring 3, remote leg) → **M3**

Strict order — each step is a new claim boundary:

```
1-worker endpoints ready     ← Nix proof exists (635ee36)
        ↓
2-worker config + Nix smoke  ← config done; live proof pending
        ↓
Direct worker/admin log ingest  ← new parsers, new proof block kinds
        ↓
Action placement / identity (only if direct evidence exists)
        ↓
Multi-machine / LRE / fleet
```

- **2-worker:** `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh` in Nix → new `summary.json`
- **Parsers:** NativeLink stdout/admin only when structured rules exist; else stay unsupported
- **Graph:** worker nodes only when SQLite has direct evidence rows

**Exit:** Each step has `summary.json` + pytest + no softened blockers.

### Phase 4 — Agent loop closure (Ring 2 → 3 bridge) → **M4**

**Goal:** Connect “agent changed code” to “validation ran” without token firehose.

- `nlfr simulate` scenarios (backbone) — already there
- One bounded LLM patch path with full provenance chain
- Optional: thin adapter docs for Cursor/Bazel monorepo (reference architecture, not product)

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

| Milestone | Proves | Ring | Linear |
|-----------|--------|------|--------|
| M1 | PR merged + tryout tag | Ring 1 ~95% | child of PER-1058 |
| M2 | Cold/warm metrics in proof packet | Ring 3 cache leg | child of PER-1058 |
| M3 | Two-worker Nix `summary.json` | Ring 3 ~55% | child of PER-1058 |
| M4 | One LLM spark + full provenance | Ring 2+3 bridge | child of PER-1058 |

After M4: credibly at reference-kit + credible substrate demo, not operator console or enterprise provenance yet.

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
NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh
npm --prefix apps/canvas run capture
```
