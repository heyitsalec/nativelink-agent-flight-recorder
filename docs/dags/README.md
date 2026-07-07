# Milestone planning docs

Short planning records for the milestones that shipped in NLFR v1, kept
because other docs cite them. Each file states the objective, deliverables,
and proof commands for one milestone. The full development history lives in
git history; the development approach is summarized in
[docs/internal/METHOD.md](../internal/METHOD.md).

| Doc | What it covers |
|-----|----------------|
| [m7-worker-parser.md](m7-worker-parser.md) | M7 — worker admin stdout parser; conditional `worker_identity` evidence |
| [m8-agent-adapter.md](m8-agent-adapter.md) | M8 — bounded agent adapter (`model` + `prompt_sha256` provenance only) |
| [m9-multi-run-compare.md](m9-multi-run-compare.md) | M9 — multi-run retention and compare exports + canvas compare lens |
| [future-fleet-claims.md](future-fleet-claims.md) | Research matrix keeping fleet/scheduler claims aligned with the actual evidence ceiling |

Milestone status and the architecture ladder:
[ARCHITECTURE_TRACK.md](../ARCHITECTURE_TRACK.md). Proven vs unproven claims:
[ONE_PAGER.md](../ONE_PAGER.md).
