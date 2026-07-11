# Reference: timeline projection v1

← [Contracts index](README.md)

**Contract:** [`contracts/timeline_projection.v1.json`](../../../../contracts/timeline_projection.v1.json) ·
**Producer:** `nlfr timeline export` ([`src/nlfr/projectors/timeline.py`](../../../../src/nlfr/projectors/timeline.py)) ·
**Consumer:** the canvas Replay lens

The flight record as a replayable, chronological event stream. One or more
evidence databases (repeatable `--db`, or `--db-root` over an `nlfr record`
layout; overlapping paths are deduplicated by resolved path) merge into a
single `events[]` list — recorded **runs**, recorded **evaluation verdict**
blocks, and **agent-receipt** provenance blocks — plus derived `chapters[]`.

## Root object

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | `const 1` | contract version |
| `projection_kind` | `const "timeline"` | discriminator |
| `generated_at` | string | export time — metadata only, never used as an event `ts` |
| `sources` | string[] | per-database labels (directory basenames) |
| `span` | `{start, end}` | first/last recorded event ts, `null` when empty |
| `summary` | counts | `events / runs / verdicts / receipts / repair_loops` |
| `events` | array | see below |
| `chapters` | array | see below |
| truth quad | — | root is `derived_v1` (const); `confidence` = weakest consulted row; `redaction_state` = most-restrictive rollup (`blocked > redacted > safe`) |

## Events

Each event: `ts` (the row's own recorded `started_at` / `generated_at` /
`captured_at`), `kind` (`run | verdict | receipt`), `label`, `source` (db
label), `index` (position in the merged stream — chapters reference these),
kind-specific `detail` (always includes `run_group` when recorded), and the
truth quad **copied from the source row/block** — a run event is exactly as
collectable as its `runs` row.

## Chapters (`repair_loop`)

A chapter opens at a verdict whose `next_steps[0].action ==
"dispatch_fix_with_evidence"` and closes only at a later `ok` verdict **of
the same lineage** — the run-group prefix after stripping the product's own
recorded iteration/retry/leg suffixes (`-iterN` from `nlfr loop`, `-rN` from
the A/B recording protocol, `-red`/`-green` proof legs), exposed as
`lineage`. Honesty properties:

- an unrelated group's green can never close another lineage's dispatch;
- a second same-lineage dispatch **supersedes** the first attempt, which
  stays `open: true` (no green ever closed *it*) as its own beat;
- a dispatch with no recorded green close stays `open: true` — the projection
  never implies a repair completed when the record doesn't show it;
- `source_kind` is `derived_v1` by `const` (a forged collectable chapter is
  schema-rejected); `redaction_state` rolls up the member events'.

## Example

The committed canvas fixture
[`apps/canvas/public/projections/timeline.json`](../../../../apps/canvas/public/projections/timeline.json)
is a real export from a recorded self-healing repair cycle (seeded red →
insufficient fix honestly rejected by a pinned test → second fix → green).

## Out of scope (v1)

Cache-event and artifact-level events; cross-database lineage linking beyond
the naming convention; pagination (consumers bucket client-side).

## Related

- [Compare projection v1](compare-projection-v1.md) — the pairwise view over
  the same evidence
- [Proof packet v1](proof-packet-v1.md) — per-run-group depth
