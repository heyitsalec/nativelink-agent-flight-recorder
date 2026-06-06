# Vision R-Wave Synthesis — 2026-06-06

Linear umbrella: [PER-1053](https://linear.app/gradschool/issue/PER-1053)

## Summary

Four parallel explore audits complete. Serial execution: **A → B → C → D**.

| Packet | Status | Top finding |
|--------|--------|-------------|
| A-R1 Packaging | DONE | GitHub `main` lacks `635ee36`; docs contradict PER-1019 Nix success |
| B-R1 Truth/canvas | DONE | Remote Boundary lens synthesizes headlines; proof block source_kind collapse |
| C-R1 Two-worker | DONE | Gate fails on 1-worker config; parser gaps for direct evidence remain open |
| Meta-R1 Framing | DONE | Ring 1 ~85%, Ring 2 ~90%, Ring 3 ~40% |

## Sub-DAG A design brief (A-D1)

**Narrative:** Nix-first for real proof; honest Mac/fixture fallback for 5-minute canvas demo.

**Dual paths:**
1. **5-min (no Nix):** `uv sync` → pytest → canvas dev (committed fixture projections)
2. **Real proof (Nix):** `nix develop` → cold-warm + local-exec → summaries in `data/`

**Do not claim:** real NativeLink execution outside Nix shell.

## Sub-DAG B design brief (B-D1)

Fix priority:
1. Remote lens: use proof block summary/claims; reduce synthesized status strings
2. Align unsupported claims (5 items) across worker-readiness, remote_execution.py, canvas
3. Fallback banner when using sampleProjection
4. Proof Drawer: show `redaction_state` in truth grid
5. Proof projector: propagate dominant source_kind from rows (not blanket derived_v1)

## Sub-DAG C design brief (C-D1)

**Wave 1 allowed claims:** config-declared worker count ≥2, endpoint readiness, Bazel remote_executor intent.

**Still unsupported:** worker identity, action placement, queue time, scheduler assignment, load distribution (until direct evidence parsers exist).

**Implementation:** second worker in `local-execution.json5`; update tests; run `NLFR_EXPECTED_WORKERS=2 scripts/local-exec-proof.sh` in Nix.

## Framing distance (Meta-R1)

| Ring | ~Today | Focus |
|------|--------|-------|
| 1 Tryout kit | 85% | Sub-DAG A |
| 2 Proof layer | 90% | Sub-DAG B protect |
| 3 Remote wedge | 40% | Sub-DAG C Wave 1 |

## Operator gates pending

- A-O1: fundraising read-through
- B-O1: claim discipline sign-off
- D-O1: umbrella tryout sign-off
