/**
 * Unit tests for the Replay lens model (src/replayModel.ts — pure, JSX-free so
 * `node --test` imports it directly; Node strips TS types on import). Run with
 * `npm --prefix apps/canvas run test:unit`. Covers, against the REAL committed
 * timeline projection (public/projections/timeline.json — an actual recorded
 * self-healing repair cycle: 14 events, 7 runs + 7 verdicts, 1 closed
 * repair_loop chapter):
 *   - bucketize: hourly buckets whose counts sum EXACTLY to the event total —
 *     nothing invented, nothing dropped; per-kind counts match the summary.
 *   - chapterForEvent: maps every chapter event index to its chapter and
 *     nothing else (resolved via the event's `index` field, never assumed to
 *     equal the array position).
 *   - nextPauseIndex / chapterStartPositions: the auto-pause beat is the
 *     chapter's FIRST event (the red dispatch verdict at index 9).
 *   - open-chapter handling on a synthetic fixture (incl. a receipt event and
 *     an open:true chapter): buckets span contiguous hours (a silent hour is an
 *     honest empty bar), the open chapter marks `open`, and readouts/summary
 *     lines state real numbers only.
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
  chapterStartPositions,
  formatRecordedTs,
  isPausePosition,
  nextPauseIndex,
  playheadBucket,
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

/* ── chapters over the REAL projection ──────────────────────────────────── */

test("chapterForEvent maps exactly the 5 chapter event indexes", () => {
  const chapter = timeline.chapters[0];
  assert.deepEqual(chapter.event_indexes, [9, 10, 11, 12, 13]);
  for (const index of chapter.event_indexes) {
    assert.equal(chapterForEvent(timeline.chapters, index), chapter);
  }
  // Events before the loop belong to no chapter.
  for (const index of [0, 4, 8]) {
    assert.equal(chapterForEvent(timeline.chapters, index), null);
  }
});

test("nextPauseIndex hits the chapter's first event (the red dispatch verdict)", () => {
  assert.deepEqual(chapterStartPositions(timeline.events, timeline.chapters), [9]);
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 0), 9);
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 8), 9);
  // Standing on the pause beat: the next pause is strictly after it — none.
  assert.equal(nextPauseIndex(timeline.events, timeline.chapters, 9), null);
  assert.equal(isPausePosition(timeline.events, timeline.chapters, 9), true);
  assert.equal(isPausePosition(timeline.events, timeline.chapters, 10), false);
  // The pause beat really is the dispatch_fix_with_evidence verdict.
  assert.equal(timeline.events[9].kind, "verdict");
  assert.equal(timeline.events[9].detail.next_action, "dispatch_fix_with_evidence");
});

test("closed chapter marks its bucket solid — never 'open'", () => {
  const { buckets } = bucketize(timeline.events, timeline.span);
  const marks = bucketChapterMarks(buckets, timeline.events, timeline.chapters);
  assert.equal(marks.length, 1);
  assert.deepEqual(marks[0], { labels: ["verdict-driven repair"], open: false });
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
    "14 events · 7 runs · 7 verdicts · 0 receipts · 1 repair loop",
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
