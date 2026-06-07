# Critical review handoff — START HERE

**Purpose:** Onboard a fresh Claude (or human) critical-review session with enough context to
challenge claims, spot hype, and recommend next work — without re-reading 13 broker waves.

**Repo:** [heyitsalec/nativelink-agent-flight-recorder](https://github.com/heyitsalec/nativelink-agent-flight-recorder)  
**Branch:** `feat/docs-wiki-wave2`  
**Open PR:** [#10 — docs: wiki wave 2 — contracts, compare sample, KOS roadmap](https://github.com/heyitsalec/nativelink-agent-flight-recorder/pull/10)  
**Umbrella verdict:** Waves 1–13 **DONE_WITH_CONCERNS** (see wave-14 close packet)  
**Date:** 2026-06-07

---

## Read order (this packet)

| # | Doc | Time | What you get |
|---|-----|------|--------------|
| 0 | [00-executive-summary.md](00-executive-summary.md) | 5 min | Verdict, stakes, first 30 min, red flags to probe |
| 1 | [01-product-vision-and-thesis.md](01-product-vision-and-thesis.md) | 10 min | Why NLFR exists, NativeLink demo fit, honest career framing |
| 2 | [02-current-state-and-proof-matrix.md](02-current-state-and-proof-matrix.md) | 15 min | What is proven, what is not, proof commands |
| 3 | [03-broker-history-and-waves.md](03-broker-history-and-waves.md) | 10 min | How work was organized, wave outcomes, residuals |

**Total:** ~40 min for full packet. A skeptical pass can stop after docs 0 + 2.

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
