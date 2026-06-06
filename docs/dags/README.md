# NLFR DAG Mirrors

## Active — Architecture track

Linear: [PER-1058](https://linear.app/gradschool/issue/PER-1058/nlfr-arch-architecturally-sound-track-l0-l2-hardening)

| Milestone | Linear | Phase |
|-----------|--------|-------|
| M1 Reference kit | PER-1059 | 1 — merge PR #2 + tag |
| M2 Quantified fast | PER-1060 | 2 — cache economics in proof |
| M3 Two-worker Nix | PER-1061 | 3 — execution ladder |
| M4 Agent loop | PER-1062 | 4 — LLM patch provenance |

Mirror: [architecture-track.md](architecture-track.md) · Spec: [../ARCHITECTURE_TRACK.md](../ARCHITECTURE_TRACK.md)

## Completed — Vision DAG

Linear umbrella: [PER-1053](https://linear.app/gradschool/issue/PER-1053/nlfr-vision-product-vision-implementation-dag)

| Sub-DAG | Linear | Ring | Repo mirror |
|---------|--------|------|-------------|
| A — Tryout kit | PER-1055 | 1 | [vision-a-tryout.md](vision-a-tryout.md) |
| B — Truth and canvas | PER-1054 | 2 | [vision-b-truth.md](vision-b-truth.md) |
| C — Remote execution | PER-1056 | 3 | [vision-c-remote.md](vision-c-remote.md) |
| D — Integration | PER-1057 | all | [vision-d-integration.md](vision-d-integration.md) |

Coordinator mode: single serial session **A → B → C → D**.

Handoffs: `docs/sessions/handoffs/`
