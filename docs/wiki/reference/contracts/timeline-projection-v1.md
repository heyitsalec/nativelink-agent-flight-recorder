# Reference: timeline projection v1

← [Contracts index](README.md)

**Contract:** [`contracts/timeline_projection.v1.json`](../../../../contracts/timeline_projection.v1.json) ·
**Producer:** `nlfr timeline export` ([`src/nlfr/projectors/timeline.py`](../../../../src/nlfr/projectors/timeline.py)) ·
**Consumer:** the canvas Replay lens

The flight record as a replayable, chronological event stream. One or more
evidence databases (repeatable `--db`, or `--db-root` over an `nlfr record`
layout) merge into a single `events[]` list — recorded **runs**, recorded
**evaluation verdict** blocks, and **agent-receipt** provenance blocks — plus
derived `chapters[]`.

Honesty properties the contract pins:

- **Recorded timestamps only.** `events[].ts` is the row's own
  `started_at` / `generated_at` / `captured_at` — never export wall-clock.
- **Truth quad per event, copied from the source row/block.** A run event is
  exactly as collectable as its `runs` row; a verdict event carries its
  block's `derived_v1`.
- **Chapters are synthesis, labeled as such.** A `repair_loop` chapter opens
  at a verdict whose `next_steps[0].action == "dispatch_fix_with_evidence"`
  and closes at the next `ok` verdict. A dispatch with **no recorded green
  close stays `open: true`** — the projection never implies a repair
  completed when the record doesn't show it. Chapters are `derived_v1` by
  construction (`const` in the schema).
- **Merge provenance survives.** Every event names its `source` database
  label; the root `sources[]` lists them all.

Additive policy per the [contracts README](README.md): unknown fields are
allowed and consumers must ignore them.
