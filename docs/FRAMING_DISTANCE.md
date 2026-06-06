# Framing Distance Table

Date: 2026-06-06 · Linear [PER-1053](https://linear.app/gradschool/issue/PER-1053)

| Ring | Target | Status after M2–M4 live proofs |
|------|--------|--------------------------------|
| **Ring 1 — Tryout kit** | Runnable, explainable, fundraising/DevRel-ready | **~92%** — dual-path README, ONE_PAGER, GITHUB_RELEASE, TRYOUT_PACKET reconciled; operator O-gate pending |
| **Ring 2 — Core v1 proof layer** | Black-box recorder with truth labels | **~95%** — agent-loop bridge proven (`agent → change → run → cache`, hashed-prompt provenance); Remote lens uses proof summaries; unsupported claims aligned; redaction in Proof Drawer |
| **Ring 3 — Remote execution wedge** | Two-worker → LLM spark → multi-machine | **~60%** — cache leg quantified (M2 cold/warm deltas); two-worker live endpoint readiness in Nix (M3, `worker_endpoints_ready`, 2 configured); direct worker-identity/placement parsers still open |

North star: **Fast** quantified in Nix (M2 cold/warm). Agent-loop bridge proven
(M4). **Trustworthy-at-scale** still needs direct worker evidence (identity,
placement, scheduler, queue time, load) + operator sign-off.
