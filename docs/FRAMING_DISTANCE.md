# Framing Distance Table

Date: 2026-06-06 · Linear [PER-1053](https://linear.app/gradschool/issue/PER-1053)

| Ring | Target | Status after vision DAG |
|------|--------|-------------------------|
| **Ring 1 — Tryout kit** | Runnable, explainable, fundraising/DevRel-ready | **~92%** — dual-path README, ONE_PAGER, GITHUB_RELEASE, TRYOUT_PACKET reconciled; operator O-gate pending |
| **Ring 2 — Core v1 proof layer** | Black-box recorder with truth labels | **~93%** — Remote lens uses proof summaries; unsupported claims aligned; redaction in Proof Drawer; source_kind propagation fixed |
| **Ring 3 — Remote execution wedge** | Two-worker → LLM spark → multi-machine | **~50%** — two-worker config + config gate pass; direct worker evidence parsers still open; Wave 2 armed |

North star: **Fast** proven in Nix. **Trustworthy-at-scale** needs Wave 2 (LLM spark) + direct worker evidence + operator sign-off.
