/**
 * Unit tests for the Replay lens model (src/replayModel.ts — pure, JSX-free so
 * `node --test` imports it directly; Node strips TS types on import). Run with
 * `npm --prefix apps/canvas run test:unit`. Covers, against the REAL committed
 * timeline projection (public/projections/timeline.json — an actual recorded
 * self-healing repair cycle: 14 events, 7 runs + 7 verdicts, and TWO
 * lineage-scoped repair_loop chapters in lineage "body-claude-w4-selfheal": a
 * superseded fix attempt that stays honestly OPEN, then the resolved loop
 * closed by the real green):
 *   - bucketize: hourly buckets whose counts sum EXACTLY to the event total —
 *     nothing invented, nothing dropped; per-kind counts match the summary.
 *   - chapterForEvent: maps every chapter event index to ITS chapter and
 *     nothing else (resolved via the event's `index` field, never assumed to
 *     equal the array position).
 *   - nextPauseIndex / chapterStartPositions: TWO auto-pause beats — each
 *     chapter's FIRST event (the dispatch verdicts at indexes 9 and 11).
 *   - playPressDecision (pause-at-origin review fix): play on an
 *     un-acknowledged chapter start pauses at origin; the SAME start never
 *     re-pauses twice in a row.
 *   - chapterMetaLine: renders the recorded `lineage` key when present.
 *   - open-chapter + receipt handling on a synthetic fixture; a zero-events
 *     projection (span nulls) degrades honestly without crashing.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  bucketChapterMarks,
  bucketize,
  chapterForEvent,
  chapterMetaLine,
  chapterStartPositions,
  formatRecordedTs,
  isPausePosition,
  nextPauseIndex,
  playheadBucket,
  playPressDecision,
  replayDetailRows,
  replayPositionReadout,
  replaySummaryLine,
  REPLAY_KIND_ORDER,
} from "../src/replayModel.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const timeline = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, "..", "public", "projections", "timeline.json"),
    "utf8",
  ),
);

/* ── bucketize over the REAL projection ─────────────────────────────────── */

test("bucketize: bucket counts sum exactly to the 14 recorded events", () => {
  const { buckets, unplaced } = bucketize(timeline.events, timeline.span);
  const total = buckets.reduce((sum, bucket) => sum + bucket.total, 0);
  assert.equal(total, 14);
  assert.equal(total, timeline.summary.events);
  assert.deepEqual(unplaced, []);
  // Per-kind sums match the projection summary — real numbers only.
  const byKind = { run: 0, verdict: 0, receipt: 0 };
  for (const bucket of buckets) {
    for (const kind of REPLAY_KIND_ORDER) byKind[kind] += bucket.counts[kind];
  }
  assert.equal(byKind.run, timeline.summary.runs);
  assert.equal(byKind.verdict, timeline.summary.verdicts);
  assert.equal(byKind.receipt, timeline.summary.receipts);
});

test("bucketize: the repair cycle lands in the real 06:00 UTC hour", () => {
  const { buckets } = bucketize(timeline.events, timeline.span);
  // All 14 events were recorded 06:31–06:38 UTC → exactly one hourly bucket.
  assert.equal(buckets.length, 1);
  assert.equal(buckets[0].hourLabel, "06:00");
  assert.equal(buckets[0].dayLabel, "2026-07-11");
  assert.equal(buckets[0].total, 14);
  // Every position 0..13 is placed in this bucket, ascending.
  assert.deepEqual(
    buckets[0].positions,
    Array.from({ length: 14 }, (_, i) => i),
  );
});

test("playheadBucket resolves any event position to its bucket", () => {
  const { buckets } = bucketize(timeline.events, timeline.span);
  assert.equal(playheadBucket(buckets, 0), 0);
  assert.equal(playheadBucket(buckets, 13), 0);
  assert.equal(playheadBucket(buckets, 99), -1);
});

/* ── chapters over the REAL projection (two lineage-scoped loops) ───────── */

test("chapterForEvent maps the two lineage-scoped chapters' event indexes", () => {
  const [superseded, resolved] = timeline.chapters;
  assert.equal(timeline.chapters.length, 2);
  // Superseded attempt: dispatch (9) + the failed fix run (10), honestly OPEN.
  assert.deepEqual(superseded.event_indexes, [9, 10]);
  assert.equal(superseded.open, true);
  assert.equal(superseded.end_ts, null);
  // Resolved loop: second dispatch (11) through the real green close (13).
  assert.deepEqual(resolved.event_indexes, [11, 12, 13]);
  assert.equal(resolved.open, false);
  // Both are the SAME recorded lineage — that is what scopes them.
  assert.equal(superseded.lineage, "body-claude-w4-selfheal");
  assert.equal(resolved.lineage, "body-claude-w4-selfheal");
  for (const index of superseded.event_indexes) {
    assert.equal(chapterForEvent(timeline.chapters, index), superseded);
  }
  for (const index of resolved.event_indexes) {
    assert.equal(chapterForEvent(timeline.chapters, index), resolved);
  }
  // Events before the loops belong to no chapter.
  for (const index of [0, 4, 8]) {
    assert.equal(chapterForEvent(timeline.chapters, index), null);
  }
});

test("nextPauseIndex walks BOTH dispatch beats (indexes 9 then 11)", () => {
  assert.deepEqual(chapterStartPositions(timeline.events, timeline.chapters), [9, 11]);
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 0), 9);
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 8), 9);
  // Standing on the first beat: the NEXT pause is the second dispatch.
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 9), 11);
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 10), 11);
  // After the second beat there is no further pause.
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 11), null);
  assert.equal(isPausePosition(timeline.events, timeline.chapters, 9), true);
  assert.equal(isPausePosition(timeline.events, timeline.chapters, 11), true);
  assert.equal(isPausePosition(timeline.events, timeline.chapters, 10), false);
  // Both pause beats really are dispatch_fix_with_evidence verdicts.
  for (const position of [9, 11]) {
    assert.equal(timeline.events[position].kind, "verdict");
    assert.equal(timeline.events[position].detail.next_action, "dispatch_fix_with_evidence");
  }
});

test("real fixture bucket mark: superseded OPEN chapter wins the open mark", () => {
  const { buckets } = bucketize(timeline.events, timeline.span);
  const marks = bucketChapterMarks(buckets, timeline.events, timeline.chapters);
  assert.equal(marks.length, 1);
  // Both chapters intersect the single 06:00 bucket; the open one marks it open.
  assert.deepEqual(marks[0], {
    labels: ["verdict-driven repair", "verdict-driven repair"],
    open: true,
  });
  // The resolved chapter ALONE marks solid/closed — never 'open'.
  const closedOnly = bucketChapterMarks(buckets, timeline.events, [timeline.chapters[1]]);
  assert.deepEqual(closedOnly[0], { labels: ["verdict-driven repair"], open: false });
});

/* ── playPressDecision (pause-at-origin, review fix) ────────────────────── */

test("play on an un-acknowledged chapter start pauses at origin", () => {
  // Standing on either dispatch beat with no acknowledged card → pause first.
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 9, null), "pause_at_origin");
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 11, null), "pause_at_origin");
  // Moving to the SECOND beat after acknowledging the first still pauses.
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 11, 9), "pause_at_origin");
});

test("the SAME chapter start never re-pauses twice in a row", () => {
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 9, 9), "play");
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 11, 11), "play");
});

test("play anywhere else just plays", () => {
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 0, null), "play");
  assert.equal(playPressDecision(timeline.events, timeline.chapters, 10, null), "play");
  assert.equal(playPressDecision([], [], 0, null), "play");
});

/* ── chapterMetaLine (lineage rendering) ────────────────────────────────── */

test("chapterMetaLine renders the recorded lineage key and open/closed words", () => {
  assert.equal(
    chapterMetaLine(timeline.chapters[0]),
    "repair loop · verdict-driven repair · lineage body-claude-w4-selfheal · open — no recorded green close",
  );
  assert.equal(
    chapterMetaLine(timeline.chapters[1]),
    "repair loop · verdict-driven repair · lineage body-claude-w4-selfheal · closed",
  );
  // Lineage is an ADDITIVE contract field — absent lineage renders no slot.
  assert.equal(
    chapterMetaLine({ ...timeline.chapters[1], lineage: undefined }),
    "repair loop · verdict-driven repair · closed",
  );
});

/* ── synthetic fixture: receipt event + OPEN chapter + hour gap ─────────── */

const quad = {
  source_kind: "collectable_v1",
  confidence: "high",
  evidence_refs: ["artifact:run.json"],
  redaction_state: "safe",
};

const synthetic = {
  events: [
    { ...quad, ts: "2026-07-11T06:10:00Z", kind: "run", label: "red · failed", source: "red", index: 0, detail: { status: "failed" } },
    {
      ...quad,
      source_kind: "derived_v1",
      confidence: "low",
      ts: "2026-07-11T06:12:00Z",
      kind: "verdict",
      label: "verdict · failed · dispatch_fix_with_evidence",
      source: "red",
      index: 1,
      detail: { status: "failed", next_action: "dispatch_fix_with_evidence" },
    },
    {
      ...quad,
      ts: "2026-07-11T08:05:00Z",
      kind: "receipt",
      label: "agent receipt",
      source: "red",
      index: 2,
      detail: { provenance_class: "receipt_verified_v1", receipt_verified: true },
    },
  ],
  chapters: [
    {
      kind: "repair_loop",
      label: "verdict-driven repair",
      start_ts: "2026-07-11T06:12:00Z",
      end_ts: null,
      open: true,
      event_indexes: [1, 2],
      source_kind: "derived_v1",
      confidence: "medium",
      evidence_refs: ["event:1"],
      redaction_state: "safe",
    },
  ],
  span: { start: "2026-07-11T06:10:00Z", end: "2026-07-11T08:05:00Z" },
};

test("synthetic: contiguous hourly buckets — a silent hour is an honest empty bar", () => {
  const { buckets, unplaced } = bucketize(synthetic.events, synthetic.span);
  assert.deepEqual(
    buckets.map((bucket) => bucket.hourLabel),
    ["06:00", "07:00", "08:00"],
  );
  assert.deepEqual(buckets.map((bucket) => bucket.total), [2, 0, 1]);
  // The receipt event is counted as a receipt, in the 08:00 bucket.
  assert.equal(buckets[2].counts.receipt, 1);
  assert.deepEqual(unplaced, []);
});

test("synthetic: an open chapter marks open — never implied-closed", () => {
  const { buckets } = bucketize(synthetic.events, synthetic.span);
  const marks = bucketChapterMarks(buckets, synthetic.events, synthetic.chapters);
  assert.deepEqual(marks[0], { labels: ["verdict-driven repair"], open: true });
  assert.equal(marks[1], null); // empty hour carries no invented mark
  assert.deepEqual(marks[2], { labels: ["verdict-driven repair"], open: true });
  // Pause beat = the chapter's first event (the dispatch verdict at position 1).
  assert.equal(nextPauseIndex(synthetic.events, synthetic.chapters, 0), 1);
  assert.equal(chapterForEvent(synthetic.chapters, 2).open, true);
});

test("synthetic: an unparseable ts is surfaced as unplaced, never dropped", () => {
  const events = [
    ...synthetic.events,
    { ...quad, ts: "not-a-timestamp", kind: "run", label: "?", source: "red", index: 3, detail: {} },
  ];
  const { buckets, unplaced } = bucketize(events, synthetic.span);
  assert.deepEqual(unplaced, [3]);
  const total = buckets.reduce((sum, bucket) => sum + bucket.total, 0);
  assert.equal(total + unplaced.length, events.length);
});

/* ── readouts / summary lines ───────────────────────────────────────────── */

test("replayPositionReadout states real 1-based positions", () => {
  assert.equal(replayPositionReadout(0, 14), "event 1 / 14");
  assert.equal(replayPositionReadout(13, 14), "event 14 / 14");
  assert.equal(replayPositionReadout(99, 14), "event 14 / 14"); // clamped, never invented
  assert.equal(replayPositionReadout(0, 0), "no events recorded");
});

test("replaySummaryLine reads only the projection's real summary numbers", () => {
  assert.equal(
    replaySummaryLine(timeline),
    "14 events · 7 runs · 7 verdicts · 0 receipts · 2 repair loops",
  );
});

/* ── zero-events projection (span nulls) degrades honestly ──────────────── */

test("empty projection: no buckets, no beats, honest readouts — no crash", () => {
  const empty = {
    schema_version: 1,
    projection_kind: "timeline",
    generated_at: "2026-07-11T00:00:00Z",
    sources: [],
    span: { start: null, end: null },
    summary: { events: 0, runs: 0, verdicts: 0, receipts: 0, repair_loops: 0 },
    events: [],
    chapters: [],
    source_kind: "derived_v1",
    confidence: "unknown",
    evidence_refs: [],
    redaction_state: "safe",
  };
  const { buckets, maxTotal, unplaced } = bucketize(empty.events, empty.span);
  assert.deepEqual(buckets, []);
  assert.equal(maxTotal, 0);
  assert.deepEqual(unplaced, []);
  assert.deepEqual(chapterStartPositions(empty.events, empty.chapters), []);
  assert.equal(nextPauseIndex(empty.events, empty.chapters, 0), null);
  assert.equal(playheadBucket(buckets, 0), -1);
  assert.deepEqual(bucketChapterMarks(buckets, empty.events, empty.chapters), []);
  assert.equal(replayPositionReadout(0, empty.events.length), "no events recorded");
  assert.equal(
    replaySummaryLine(empty),
    "0 events · 0 runs · 0 verdicts · 0 receipts · 0 repair loops",
  );
});

test("replayDetailRows flags status for statusTone routing and keeps recorded order", () => {
  const rows = replayDetailRows(timeline.events[9]);
  assert.deepEqual(
    rows.map((row) => row.key),
    ["classification", "next_action", "run_group", "status"],
  );
  const status = rows.find((row) => row.isStatus);
  assert.equal(status.value, "failed");
  assert.equal(rows.filter((row) => row.isStatus).length, 1);
});

test("formatRecordedTs keeps the RECORDED timestamp, UTC, second precision", () => {
  assert.equal(formatRecordedTs("2026-07-11T06:35:19.398438Z"), "2026-07-11 06:35:19");
});
