# NLFR Demo Strategy — NativeLink Team

**Worker:** wave-research  
**When:** 2026-06-06  
**Purpose:** Three-tier demo plan for presenting NLFR to NativeLink builders  
**Sources:** `docs/ONE_PAGER.md`, `docs/TRYOUT_PACKET.md`, Harmony dual-hero README pattern, built-state audit

---

## Audience & presenter profile

**Audience:** NativeLink builders — cache, remote execution, worker readiness, skeptical of dashboard theater.

**Presenter:** TypeScript-strong, Rust-weak. Stay on the **black-box recorder** story: Bazel/NativeLink in, hashed artifacts → SQLite → projection JSON → canvas. No NativeLink Rust internals, no Rust changes.

**North star (from ONE_PAGER / TRYOUT_PACKET):**

> When AI writes the code, NativeLink makes validating it fast, and NLFR makes validating it trustworthy.

---

## Harmony dual-hero pattern (adapted)

Harmony pairs **surface** (Cockpit tour GIF) with **under-the-hood** (Fleet terminal GIF). NLFR mirrors this:

| Hero | NLFR asset | Story |
|------|------------|--------|
| Surface | `docs/media/nlfr-canvas-tour.gif` | Action Graph, Proof Packet, Compare, operator command — **projection JSON only** |
| Under-the-hood | `docs/media/nlfr-evidence-loop.gif` | Record → ingest → export → project with truth labels |

**Live demo flow:** open with both heroes (README or slides), then **live canvas** (surface) and **terminal + `summary.json`** (under-the-hood). Always pair a visual claim with `source_kind`.

---

## Three demo tiers

### Tier 1 — 5 minutes: "Trust model, not toy UI"

**Goal:** Show NLFR is evidence-first, not a fake scheduler dashboard.

**Prep:** `npm --prefix apps/canvas run preview` (or dev); committed projections under `apps/canvas/public/projections/`.

**Script (~5 min):**

1. **Thesis (30s)** — validation scarcity in agent loops; NLFR records what ran.
2. **Dual heroes (60s)** — canvas tour + evidence loop; "surface vs spine."
3. **Live canvas (3 min)** — operator commands from WALKTHROUGH:
   - `proof` → Proof Packet (claims, confidence, evidence_refs)
   - `remote` → Remote Boundary (configured vs unsupported claims)
   - `agent loop` → deterministic provenance (`simulated_v1` agent/change)
   - `cache` / `failures` if time
4. **Honesty close (30s)** — legend: purple = `simulated_v1`, green = `collectable_v1`; v1 does **not** claim worker identity, queue time, placement.

**Commands (optional, pre-run):** `uv run pytest tests -q` — "~61 tests, no Nix."

**Impresses because:** Remote Boundary and truth labels match builder skepticism; zero Rust.

**Avoid:** Calling fixture path "live NativeLink proof."

---

### Tier 2 — 15 minutes: "Evidence spine without Rust" *(recommended)*

**Goal:** Show the full pipeline using CLI + JSON + canvas; real proof via redacted samples, not live Nix.

**Prep:** Tier 1 + `docs/proof-samples/*.json`; optional pre-run `verify-demo.sh`.

**Script (~15 min):**

1. **Tier 1 canvas tour (5 min)** — as above.
2. **Under-the-hood (5 min)** — evidence loop narrative:
   ```bash
   PYTHONPATH=src uv run python -m nlfr simulate \
     --scenario safe-leaf-change --output-dir /tmp/nlfr-sim --skip-run --json
   ```
   Then fixture ingest → export (README Path A):
   ```bash
   PYTHONPATH=src uv run python -m nlfr ingest ... --source-kind simulated_v1
   PYTHONPATH=src uv run python -m nlfr graph export --run-group latest \
     --output apps/canvas/public/projections/action-graph.json
   ```
   Brief peek at projection JSON (TypeScript-friendly) — `source_kind`, `evidence_refs` on nodes.
3. **Real proof, no live Nix (4 min)** — open `docs/proof-samples/cold-warm-summary.json`:
   - cold `hit_rate` 0.0 / 8.17s vs warm 1.0 / 5.48s (`collectable_v1`)
   - `two-worker-summary.json`: `worker_endpoints_ready`, `expected_workers=2` — **explicitly not** distributed work
   - `agent-loop-summary.json`: mixed labels; prompt = SHA-256 only
4. **NativeLink fit (1 min)** — cache → local-exec smoke → future fleet; NLFR makes substrate visible without owning scheduler.

**Impresses because:** Live ingest/export + redacted `collectable_v1` samples; presenter stays in Python/TS/JSON.

**Presenter cheat sheet:** When asked about Rust/scheduler — "NLFR is a recorder around your stack; we don't patch NativeLink."

---

### Tier 3 — 30 minutes: "Skeptic re-run"

**Goal:** Reproduce or replay real toolchain proof for engineers who want exit codes and artifacts.

**Prep:** `nix develop` staged (~82GB first fetch); or CI artifact `linux-nix-toolchain-proof` + local Tier 2 fallback.

**Script (~30 min):**

1. **Tier 2 (12 min)** — condensed.
2. **Live Nix proof (15 min)** — inside `nix develop`:
   ```bash
   scripts/cold-warm-cache-proof.sh
   scripts/local-exec-proof.sh
   NLFR_EXPECTED_WORKERS=2 NLFR_LOCAL_EXEC_OUTPUT=$PWD/data/local-exec-proof-2w \
     scripts/local-exec-proof.sh
   scripts/agent-loop-proof.sh
   ```
   Show `data/*/summary.json` with `source_kind: collectable_v1`; align canvas Remote Boundary with summary claims.
3. **Verifier + skeptic path (3 min)**:
   ```bash
   scripts/verify-demo.sh
   ```
   CI: download `linux-nix-toolchain-proof`; compare to `docs/proof-samples/`.

**Impresses because:** Exit 0, hashes preserved, PER-1019 table from TRYOUT_PACKET — builder-grade evidence.

**Risk:** Live Nix fails → pivot to proof-samples + CI artifacts; `environment_blocker` is honest, not failure.

---

## Pre-demo checklist (all tiers)

| Item | Purpose |
|------|---------|
| Canvas preview on `127.0.0.1:5174` | Avoid Vite cold start |
| Know fixture vs `canvas-dev` vs Nix projections | Correct `source_kind` narration |
| `docs/proof-samples/README.md` open | Quick honesty reference |
| ONE_PAGER "explicitly unproven" memorized | Deflect overclaim questions |

---

## What NOT to do (Rust-weak presenter)

- Don't walk NativeLink Rust source or propose Rust patches.
- Don't imply two-worker proof = load balancing or action placement.
- Don't present agent loop as live LLM (`simulated_v1` for agent/change).
- Don't hide fixture fallback banner — explain it.
- Don't skip Remote Boundary on a NativeLink audience.

---

## JSON summary

```json
{
  "tier_summaries": [
    {
      "tier": "5min",
      "name": "Trust model, not toy UI",
      "audience_hook": "NativeLink builders who need to see conservative truth-labeling before caring about the stack",
      "format": "Harmony dual-hero open (canvas tour + evidence loop GIFs) → live canvas operator commands (proof, remote, agent loop) → honesty close on simulated_v1 vs collectable_v1",
      "prep": "npm canvas preview/dev only; committed projections; no Nix/Bazel/NativeLink required",
      "live_commands": ["uv run pytest tests -q (optional)", "npm --prefix apps/canvas run preview"],
      "proof_level": "simulated_v1 fixtures + optional canvas-dev collectable_v1 dogfood; no live NativeLink",
      "impresses_because": "Remote Boundary lens and per-claim truth labels signal evidence-first design, not scheduler cosplay",
      "time_budget_minutes": 5
    },
    {
      "tier": "15min",
      "name": "Evidence spine without Rust",
      "audience_hook": "Platform engineers who want pipeline mechanics and real proof artifacts without a 30+ min Nix run",
      "format": "Tier 1 canvas → live nlfr simulate/ingest/graph export → projection JSON walkthrough → docs/proof-samples collectable_v1 cold/warm, two-worker, agent-loop summaries side-by-side with canvas lenses",
      "prep": "Tier 1 prep + proof-samples JSON + optional verify-demo.sh pre-run",
      "live_commands": [
        "nlfr simulate --scenario safe-leaf-change --skip-run",
        "nlfr ingest + graph export (fixture path)",
        "canvas operator: proof, remote, agent loop, cache"
      ],
      "proof_level": "mixed: live simulated_v1 pipeline demo + redacted collectable_v1 proof-samples (PER-1019 outcomes)",
      "impresses_because": "Shows end-to-end record→ingest→project→inspect in presenter-strong TS/Python/JSON; grounds NativeLink value in real cold/warm and worker-endpoint evidence without touching Rust",
      "time_budget_minutes": 15
    },
    {
      "tier": "30min",
      "name": "Skeptic re-run",
      "audience_hook": "NativeLink builders who will only trust exit codes, summary.json, and reproducible scripts",
      "format": "Condensed Tier 2 → nix develop live cold-warm + local-exec + two-worker + agent-loop scripts → data/*/summary.json vs canvas → verify-demo.sh + CI artifact skeptic path",
      "prep": "nix develop staged (~82GB first fetch) OR CI artifact linux-nix-toolchain-proof as fallback",
      "live_commands": [
        "scripts/cold-warm-cache-proof.sh",
        "scripts/local-exec-proof.sh",
        "NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh",
        "scripts/agent-loop-proof.sh",
        "scripts/verify-demo.sh"
      ],
      "proof_level": "collectable_v1 from real NativeLink 1.3.2 + Bazel 9.1.1 inside Nix",
      "impresses_because": "Reproducible PER-1019 proof table with explicit unsupported-claims boundaries; matches builder verification habits",
      "time_budget_minutes": 30
    }
  ],
  "recommended_tier": "15min",
  "recommended_tier_rationale": "Best balance for a TS-strong, Rust-weak presenter impressing NativeLink builders: live evidence-spine demo in Python/JSON/TS plus redacted collectable_v1 proof-samples convey real NativeLink cache and worker-endpoint proof without risking a live Nix failure or overclaiming Rust integration. Reserve 30min for rooms that demand live re-run; use 5min only for first-touch or when time is severely constrained.",
  "risk_of_overclaim": [
    "Presenting fixture or canvas-dev path as live NativeLink execution without stating source_kind",
    "Implying two-worker local-exec proof means work distributed across workers, scheduler assignment, or load balancing (proven: endpoints ready; not: placement or distribution)",
    "Describing agent-loop demo as live LLM or NativeLink worker identity (agent/change nodes are simulated_v1; prompt is SHA-256 hash only)",
    "Equating Remote Boundary 'remote execution configured' with direct worker execution evidence",
    "Claiming worker identity, queue time, action placement, multi-machine fleet, or org-scale history (explicitly unproven in ONE_PAGER and TRYOUT_PACKET)",
    "Framing NLFR as a NativeLink fork or requiring NativeLink Rust changes (it is a black-box recorder; v1 needs no Rust patches)",
    "Hiding or ignoring fixture fallback banner instead of explaining honest degraded mode",
    "Treating environment_blocker on bare host as demo failure rather than valid readiness evidence"
  ]
}
```
