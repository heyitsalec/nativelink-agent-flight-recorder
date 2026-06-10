# Critical review handoff — START HERE

**Purpose:** Onboard a fresh Claude (or human) critical-review session with enough context to
challenge claims, spot hype, and recommend next work — without re-reading 13 broker waves.

**Repo:** [heyitsalec/nativelink-agent-flight-recorder](https://github.com/heyitsalec/nativelink-agent-flight-recorder)  
**Branch:** `feat/docs-wiki-wave2`  
**Open PR:** [#10 — docs: wiki wave 2 — contracts, compare sample, KOS roadmap](https://github.com/heyitsalec/nativelink-agent-flight-recorder/pull/10)  
**Umbrella verdict:** Waves 1–13 **DONE_WITH_CONCERNS** (see wave-14 close packet)  
**Date:** 2026-06-07

**Fast path for Claude:** Copy the prompt in [09-claude-session-prompt.md](09-claude-session-prompt.md) into a new session.

---

## Packet index (00–09)

| # | File | One-line description |
|---|------|----------------------|
| **00** | [00-executive-summary.md](00-executive-summary.md) | Verdict table, stakes, first-30-min probes, red flags, suggested review outputs |
| **01** | [01-product-vision-and-thesis.md](01-product-vision-and-thesis.md) | Why NLFR exists, NativeLink demo fit, explicit unproven boundaries, career framing |
| **02** | [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md) | Architecture snapshot, proven vs unproven matrix, wave outcomes, PR #10 scope |
| **03** | [03-broker-history-and-waves.md](03-broker-history-and-waves.md) | Broker/KOS model, waves 1–13 receipts, DONE_WITH_CONCERNS residuals |
| **04a** | [04-drift-audit.md](04-drift-audit.md) | Pre-computed drift audit: Goals A–F scores, doc matrix, test gaps, demo blockers |
| **04b** | [04-file-mapping.md](04-file-mapping.md) | Repository tree and path → purpose → truth label → proof command map |
| **05** | [05-review-rubric.md](05-review-rubric.md) | Adversarial checklists, commands to run, severity rubric, review output template |
| **06** | [06-demo-rehearsal-script.md](06-demo-rehearsal-script.md) | Condensed Tier 1/2/3 demo script with cue cards and fallbacks |
| **07** | [07-career-positioning-notes.md](07-career-positioning-notes.md) | Portfolio/interview framing — honest claims vs hype to avoid |
| **08** | [08-open-questions-for-reviewer.md](08-open-questions-for-reviewer.md) | 48 specific questions the review must answer with evidence |
| **09** | [09-claude-session-prompt.md](09-claude-session-prompt.md) | Copy-paste prompt block for a fresh Claude adversarial review session |

---

## Recommended read order (fresh Claude session)

| Phase | Docs | Time | Goal |
|-------|------|------|------|
| **1 — Thesis** | [09](09-claude-session-prompt.md) (paste) → [00](00-executive-summary.md) → [docs/ONE_PAGER.md](../../../ONE_PAGER.md) | 10 min | Mission, limits, unproven table |
| **2 — State** | [02](02-current-state-and-proof-matrix.md) → [04-drift-audit.md](04-drift-audit.md) | 15 min | What is proven, what drifted, demo blockers |
| **3 — Depth (pick one)** | [01](01-product-vision-and-thesis.md) *or* [03](03-broker-history-and-waves.md) | 10 min | Product why *or* broker receipts |
| **4 — Execute review** | [05](05-review-rubric.md) + [08](08-open-questions-for-reviewer.md) | 45 min–3 hr | Run commands, file findings, answer Q1–48 |
| **5 — Optional** | [04-file-mapping](04-file-mapping.md), [06](06-demo-rehearsal-script.md), [07](07-career-positioning-notes.md) | as needed | Navigation, demo prep, portfolio context |

**Skeptical 30-min pass:** 00 → 02 → 04-drift-audit → run pytest + open `action-graph.json` → skim 08 Q6–Q10.

**Full adversarial pass:** All of phase 1–4; use 06 before any external demo.

---

## Canonical product docs (outside this packet)

| Doc | Role |
|-----|------|
| [docs/ONE_PAGER.md](../../../ONE_PAGER.md) | Thesis + proven vs unproven (authoritative) |
| [docs/USEFULNESS_ROADMAP.md](../../../USEFULNESS_ROADMAP.md) | Useful today vs gaps; M5–M9 ladder |
| [docs/DEMO_SCRIPT.md](../../../DEMO_SCRIPT.md) | Tier 1/2/3 demo rehearsal |
| [README.md](../../../../README.md) | Evaluator entry, paths A/B, truth labels |
| [AGENTS.md](../../../../AGENTS.md) | Engineering rules for contributors |

---

## Broker / implementation depth (if you need receipts)

| Span | Index |
|------|-------|
| KOS cutover waves 1–14 | [nlfr-kos-cutover/README.md](../nlfr-kos-cutover/README.md) |
| Umbrella close (waves 1–13) | [wave-14/umbrella-close-packet.md](../nlfr-kos-cutover/wave-14/umbrella-close-packet.md) |
| Gap honesty (fleet blockers) | [wave-9/gap-honesty-packet.md](../nlfr-kos-cutover/wave-9/gap-honesty-packet.md) |
| GHA offline substitute | [frontier-wave/wave-1/gha-offline-proof-shift.md](../frontier-wave/wave-1/gha-offline-proof-shift.md) |

---

## Quick proof commands (local)

```bash
uv sync && npm --prefix apps/canvas install
uv run pytest -q                    # expect 140 passed, 3 skipped
./scripts/verify-demo.sh            # fixture path + local gates
npm --prefix apps/canvas run preview  # canvas-dev collectable_v1 default
```

Nix real proof (30+ min, ~82GB disk): `nix develop` then `scripts/cold-warm-cache-proof.sh`.

---

## What this review should answer

1. Is the **evidence-first spine** real, or is the canvas doing theater?
2. Are **truth labels** enforced in code and tests, or mostly in docs?
3. Is the **NativeLink showcase** credible for DevRel/buyers without overselling RBE?
4. Is **PR #10** merge-ready given GHA offline and host-gated live proofs?
5. What is the **smallest honest next milestone** — reference kit polish vs operator console vs fleet evidence?

---

## Reviewer persona

Assume you are a skeptical staff engineer evaluating:

- a portfolio / credibility piece for agentic infra roles, and
- a potential NativeLink companion demo for platform buyers.

Reward honesty over ambition. Penalize any UI or copy that implies scheduler, queue time, placement,
or fleet ops without direct artifact evidence.
