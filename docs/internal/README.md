# Internal / process docs

← [Docs index](../INDEX.md) · [Wiki hub](../wiki/README.md)

These are **build-log and process narratives** — how this repo was constructed,
the implementation DAGs, and toolchain-history notes. They are kept for
contributors and for provenance, but they are deliberately separated from the
product-facing docs so that a buyer reading the [README](../../README.md),
[one-pager](../ONE_PAGER.md), [tryout packet](../TRYOUT_PACKET.md), and
[adoption guide](../ADOPTION_GUIDE.md) reads *what NLFR is* first.

| Doc | What it covers |
|-----|----------------|
| [METHOD.md](METHOD.md) | Contracts-first, agent-coordinated development method |
| [IMPLEMENTATION_DAG.md](IMPLEMENTATION_DAG.md) | Historical implementation dependency graph |
| [IMPLEMENTATION_WALKTHROUGH.md](IMPLEMENTATION_WALKTHROUGH.md) | Step-by-step build walkthrough |
| [EXTENSION_DAG.md](EXTENSION_DAG.md) | Post-MVP extension planning graph |
| [REAL_TOOLCHAIN_DAG.md](REAL_TOOLCHAIN_DAG.md) | Real-toolchain (Nix) proof-pass planning record |
| [LOCAL_EXECUTION_DAG.md](LOCAL_EXECUTION_DAG.md) | Local-execution worker-proof planning record |

Milestone planning records remain under [`docs/dags/`](../dags/README.md); the
GHA restore runbook remains at [`docs/GHA_RESTORE_RUNBOOK.md`](../GHA_RESTORE_RUNBOOK.md)
(both are referenced by tooling and were intentionally left in place).

For current product truth and milestone status, use the
[one-pager](../ONE_PAGER.md) and [architecture track](../ARCHITECTURE_TRACK.md).

- [Campaign handoff](CAMPAIGN_HANDOFF.md) — durable cross-machine record: goal, what shipped, the assessment verdict, the wave-4 backlog, and how to resume the loop.
