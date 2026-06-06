# NLFR Architecture Track DAG

Linear: [PER-1058](https://linear.app/gradschool/issue/PER-1058)

Full spec: [../ARCHITECTURE_TRACK.md](../ARCHITECTURE_TRACK.md)

## Coordinator mode

**Serial across milestones** (M1 → M2 → M3 → M4). **Parallel tracks** A/B/C only when write scopes do not collide.

| Track | Linear touch | Active after |
|-------|--------------|--------------|
| A — Truth spine | M2+ projectors, contracts | M2 |
| B — Toolchain proof | M2 cold/warm, M3 two-worker Nix | M1 merge |
| C — Tryout surface | M1 tag + docs only | M1 |

## Milestone DAG

```
PER-1058 (parent)
├── PER-1059 M1 — Reference kit        [Phase 1]  ← YOU ARE HERE
├── PER-1060 M2 — Quantified cache     [Phase 2]  blockedBy PER-1059
├── PER-1061 M3 — Two-worker Nix       [Phase 3]  blockedBy PER-1060
└── PER-1062 M4 — Agent loop           [Phase 4]  blockedBy PER-1061
```

Phase 5 (product shape fork) is out of DAG until M4 exit.

## Handoff checklist (per milestone)

- [ ] Collect gate: artifacts + SHA-256
- [ ] Normalize gate: idempotent ingest
- [ ] Project gate: four truth labels on all nodes
- [ ] Consume gate: canvas from projection JSON only
- [ ] Ship gate: skeptic script re-run documented

## Related DAGs

- Vision umbrella (Done): [PER-1053](https://linear.app/gradschool/issue/PER-1053) — [vision sub-DAGs](README.md)
- Foundation: PER-998, PER-1007, PER-1013, PER-1019
