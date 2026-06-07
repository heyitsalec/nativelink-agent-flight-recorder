# Integration Brief — NLFR Demo for NativeLink Team

**When:** 2026-06-06  
**Synthesizes:** `provenance-nativelink-external-research.md`, `provenance-nlfr-built-audit.md`, `provenance-demo-strategy-nl-team.md`  
**Audience:** Coordinators preparing a NativeLink builder demo  
**Presenter profile:** TypeScript-strong, Rust-weak

---

## Executive summary (honest)

NLFR is a **real, evidence-first recorder** with a working spine (CLI → hashed artifacts → SQLite → truth-labeled projection JSON → sparse canvas). It is **not** a NativeLink fork, scheduler dashboard, or BuildBuddy competitor. The architecture is honest: every node carries `source_kind`, and unsupported claims stay explicit.

**What is genuinely proven:** Cold/warm cache economics through real Bazel + NativeLink cache-only (`collectable_v1`, Nix-gated, partially CI-gated). Agent-loop validation leg with mixed labels (real Bazel ingest + simulated agent/change). Generic command recording and canvas dogfood without Nix. Environment blockers instead of fake success when tools are absent.

**What is not proven or is fixture-only:** Committed canvas projections are `simulated_v1` fixtures, not live proof — a documented M6 drift. Worker identity parser exists but last proof was fixture-replay. Two-worker proof is endpoint readiness only, not distributed execution. Scheduler assignment, queue time, action placement, and fleet ops remain explicitly unproven.

**Recommended demo:** **15-minute Tier 2** — live canvas + evidence-spine CLI/JSON walkthrough + redacted `docs/proof-samples/` for `collectable_v1` claims. Avoid live Nix unless the room demands exit codes. This tier impresses NativeLink builders by showing conservative truth-labeling and real proof artifacts without Rust cosplay.

**Confidence:** Medium-high that the demo lands well if the presenter narrates `source_kind` honestly. Medium that live Nix re-run succeeds on first attempt without staging. Low that NLFR currently productizes what NativeLink builders care about most (LRE, fleet ops, scheduler internals) — it complements those, it does not replace them.

---

## What NativeLink team cares about vs what NLFR proves

| NativeLink builders care about | NLFR status | Demo stance |
|-------------------------------|-------------|-------------|
| **RE API v2 correctness** | NLFR consumes Bazel/NativeLink outputs; does not implement RE API | Black-box recorder around their stack |
| **Cache hit rate / wall time at scale** | **Proven locally + CI:** cold 0.0 → warm 1.0 hit_rate | Show `docs/proof-samples/cold-warm-summary.json` |
| **LRE / Nix toolchain hermeticity** | Not in NLFR scope; NativeLink's moat | Do not demo; acknowledge as their territory |
| **Production scale (1B req/month, Samsung)** | Not claimed | Do not compare; NLFR is reference-kit depth |
| **Worker fleet / scheduler routing** | Endpoint readiness only (`worker_endpoints_ready`) | Remote Boundary lens; label as configured, not distributed |
| **Rust performance / no-GC** | Not NLFR's story | Never lead with; show measured cache economics instead |
| **Agent-era validation loops** | **Partially proven:** mixed agent-loop chain | Show simulated agent + collectable validation leg |
| **Provenance / audit trails** | **Core NLFR thesis:** truth labels, proof packet, evidence refs | Lead here — this is the complement NativeLink docs don't fully productize |
| **Observability (Prometheus, OTel)** | Not cloned; NLFR exports projection JSON | Position as evidence export, not metrics dashboard |
| **Competitive benchmarks vs BuildBuddy** | None published; NLFR has none either | Do not trash-talk or benchmark |

**Alignment opportunity:** NativeLink messaging is "fast validation" (cache/RBE); NLFR adds "trustworthy validation" (evidence-first proof with honest boundaries). The pair story is credible when both sides stay in lane.

**Misalignment risk:** Presenting NLFR as if it knows which worker ran an action, how the scheduler assigned work, or how fleet load distributes — all explicitly unproven and will erode credibility instantly with builders.

---

## Recommended demo for TypeScript-skilled presenter (15 min script outline)

**Tier:** 15-minute "Evidence spine without Rust"  
**Prep (day before):** `npm --prefix apps/canvas install`; `npm --prefix apps/canvas run preview` smoke test; open `docs/proof-samples/` tabs; skim ONE_PAGER "explicitly unproven" list.

| Time | Segment | Action | Talking point |
|------|---------|--------|---------------|
| 0:00–0:30 | Thesis | Slide or README north star | "When AI writes the code, NativeLink makes validating it fast; NLFR makes validating it trustworthy." |
| 0:30–1:30 | Dual heroes | Show `nlfr-canvas-tour.gif` + `nlfr-evidence-loop.gif` | Surface (canvas) vs spine (record→ingest→export). Evidence loop GIF is curated replay, not live shell. |
| 1:30–5:30 | Live canvas | `npm --prefix apps/canvas run preview` on `127.0.0.1:5174` | Operator commands: `proof` → Proof Packet; `remote` → Remote Boundary; `agent loop` → simulated provenance; `compare` if JSON loaded. Point to truth legend. **Say aloud:** committed projections are `simulated_v1` fixtures. |
| 5:30–8:30 | Evidence spine | Terminal: `nlfr simulate --scenario safe-leaf-change --skip-run --json` → ingest → `graph export` | Show projection JSON node with `source_kind`, `evidence_refs`. "This is TypeScript-friendly contract — canvas never invents backend state." |
| 8:30–11:30 | Real proof samples | Open `docs/proof-samples/cold-warm-summary.json`, `two-worker-summary.json`, `agent-loop-summary.json` | Cold/warm: collectable_v1. Two-worker: endpoints ready, **not** distributed work. Agent-loop: mixed labels; prompt = SHA-256 only. |
| 11:30–13:30 | Honesty slide | ONE_PAGER unsupported claims | worker identity (partial M7), queue time, scheduler assignment, action placement, multi-machine fleet — all unproven or fixture-only. |
| 13:30–14:30 | NativeLink fit | No Rust | "NLFR is a recorder around your stack. We don't patch NativeLink. We make cache/RBE outcomes auditable for agent loops." |
| 14:30–15:00 | Close | Repeat north star | Invite skeptic re-run (Tier 3) if they want `nix develop` + exit codes. |

**Fallback if canvas fails:** Use committed GIFs + proof-samples JSON only (degrades to Tier 1 + samples).

**Optional pre-run (not live):** `uv run pytest tests -q` — "~61 tests, fixture-backed spine."

---

## What NOT to demo

| Avoid | Why (NativeLink builder reaction) |
|-------|-----------------------------------|
| Rust scheduler internals (`schedulers.rs`, LRU/MRU allocation) | Requires deep contributor context; shallow demo backfires |
| Custom scheduler / federation config hacks | Config-composition domain, not recorder domain |
| Worker executor implementation | Ops + Rust; not NLFR |
| Store backend internals (FastSlow, CAS dedup) | Infra engineering territory |
| LRE / Nix toolchain pipeline (`rbe_configs_gen`) | NativeLink's technical moat; outsider will misstep |
| "We know which worker ran action X" | Unless direct log evidence ingested; M7 last proof was fixture-replay |
| Queue time / load distribution claims | Explicitly in UNSUPPORTED_CLAIMS |
| Head-to-head "NativeLink beats BuildBuddy" | No published benchmarks; engineers will challenge |
| BuildBuddy-style results UI | Not NativeLink's surface |
| Multi-region / K8s fleet ops | Hard ops domain (Kleckner blog territory) |
| RBE without correct toolchain config | Fails silently or slow-compiles |
| "Rust is fast" advocacy | Marketing; show measured cache hit rate instead |
| Live LLM agent calls | Agent nodes are `simulated_v1`; zero LLM tokens in v1 |
| Presenting fixture canvas as live NativeLink proof | M6 drift; say `simulated_v1` aloud |

---

## Gap list prioritized

### Fix before demo (credibility risks)

| Priority | Gap | Fix | Effort |
|----------|-----|-----|--------|
| P0 | M6 drift: docs say canvas-dev `collectable_v1` default; committed `public/projections/` is `simulated_v1` | **Fixed** — `record-canvas-build.sh` output committed; `verify-demo.sh` no longer overwrites public projections; canvas shows projection-notice banner | Done |
| P0 | Presenter may accidentally call fixtures "live proof" | Add demo script cue cards / `docs/DEMO_SCRIPT.md` Tier 2 section with mandatory `source_kind` narration | Low |
| P1 | `verify-demo.sh` overwrites public projections with fixtures after canvas dogfood | **Fixed** — fixture exports stay under `data/demo-proof/projections/` | Done |
| P1 | `docs/proof-samples/` from author Mac, not Linux CI artifact | Promote first green GHA `linux-nix-toolchain` summary to proof-samples before demo | Medium |

### OK to show (with honest labels)

| Item | Label to state aloud |
|------|---------------------|
| Committed canvas projections | `simulated_v1` — fixture agent-loop chain |
| Cold/warm proof-samples | `collectable_v1` — real Bazel through NativeLink cache (redacted paths) |
| Two-worker summary | `collectable_v1` — endpoint readiness only, not distributed execution |
| Agent-loop summary | Mixed — validation leg collectable, agent/change simulated |
| M7 worker identity parser | Parser proven on fixture-replay; live Nix stdout optional |
| M8 record-agent-change | Adapter metadata collectable; validation via pytest not Bazel |
| M9 compare lens | `derived_v1` — cross-run diff, no worker correlation |
| Environment blockers off-Nix | `collectable_v1` honesty — readiness evidence, not failure |
| Evidence-loop GIF | Curated HTML replay — illustrates pipeline, not live recording |

### Post-demo / not blocking

| Gap | Notes |
|-----|-------|
| CI omits local-exec, two-worker, worker-evidence, compare-proof | Tier 2 uses proof-samples; Tier 3 needs Nix staging |
| M8 no live Cursor hook | Manual script is honest v1 scope |
| tri-agent-loop not a proof gate | Scenario name only |
| M9 retention index-only | Future work |
| Fleet / scheduler / queue time | Explicitly future per ONE_PAGER |

---

## Next 5 actions ranked by ROI

| Rank | Action | ROI | Why |
|------|--------|-----|-----|
| 1 | **Rehearse Tier 2 with mandatory `source_kind` narration** — update `docs/DEMO_SCRIPT.md` or cue card from this brief | Highest | Zero code; prevents P0 credibility failure in room |
| 2 | **Resolve M6 drift** — pick one: commit canvas-dev projections OR document fixture-default + UI banner for `simulated_v1` | High | Stops doc/code contradiction that builders will notice |
| 3 | **Promote Linux CI cold-warm summary to `docs/proof-samples/`** after green GHA run | High | Gives skeptic-proof artifact not tied to author Mac |
| 4 | **Pre-stage Tier 3 fallback pack** — download `linux-nix-toolchain-proof` CI artifact + proof-samples side-by-side | Medium | De-risks live Nix failure without blocking Tier 2 |
| 5 | **Run live Nix worker-evidence once** (`worker-evidence-proof.sh` chained to local-exec) and capture summary | Medium | Upgrades M7 from fixture-replay to collectable live stdout — only if audience asks about worker identity |

**Deprioritized for demo ROI:** Rust changes, scheduler integration, Cursor live hook, tri-agent-loop script, M9 retention policy — all valuable post-demo, none required to land the 15-minute story.

---

## Source index

| Document | Role |
|----------|------|
| `provenance-nativelink-external-research.md` | What NativeLink is, who uses it, impress/avoid lists |
| `provenance-nlfr-built-audit.md` | M1–M9 truth table, scripts, gaps, demo_ready_scripts |
| `provenance-demo-strategy-nl-team.md` | Three tiers (5/15/30 min), Harmony dual-hero, overclaim risks |
| `docs/ONE_PAGER.md` | Canonical claims and explicitly unproven list |
| `docs/DEMO_SCRIPT.md` | Existing 5-step rehearsal path (extend for Tier 2) |

---

## JSON (integration output)

```json
{
  "recommended_demo_tier": "15min",
  "top_3_actions": [
    "Rehearse Tier 2 with mandatory source_kind narration (cue cards / DEMO_SCRIPT update)",
    "Resolve M6 drift: commit canvas-dev collectable_v1 OR document fixture-default with visible banner",
    "Promote Linux CI cold-warm summary to docs/proof-samples/ after green GHA run"
  ],
  "honest_confidence_level": "medium-high for Tier 2 landing if source_kind narrated; medium for live Nix Tier 3 first-attempt; low for NLFR substituting NativeLink core builder concerns (LRE, fleet, scheduler)"
}
```
