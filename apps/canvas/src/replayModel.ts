import type {
  TimelineChapter,
  TimelineEvent,
  TimelineEventKind,
  TimelineProjection,
} from "./types";

/**
 * Replay lens model (pure, JSX-free — mirrors pageModel.ts so `node --test`
 * can import it directly; unit-tested in scripts/replay-model.test.mjs).
 *
 * Everything here is derived 1:1 from the timeline projection
 * (contracts/timeline_projection.v1.json). Nothing is invented: buckets count
 * only real recorded events, chapters come from the projection's derived
 * repair_loop chapters, and an event whose recorded timestamp cannot be parsed
 * is surfaced in `unplaced` — stated, never silently dropped.
 *
 * Two kinds of index, kept deliberately distinct:
 *   - POSITION: an index into the events array — the playback order the lens
 *     walks (the projector emits events chronologically).
 *   - `TimelineEvent.index`: the projector-assigned field chapters reference
 *     via `event_indexes`. The model resolves chapter membership through this
 *     field and never assumes it equals the array position.
 */

export const REPLAY_KIND_ORDER: TimelineEventKind[] = ["run", "verdict", "receipt"];

const HOUR_MS = 3_600_000;

/** Contiguous-hour cap: past this, fall back to event-hours-only buckets (each
 *  still labeled with its real recorded hour, so gaps stay visible by label —
 *  the axis is compressed, never the data). */
const MAX_CONTIGUOUS_BUCKETS = 400;

export type ReplayBucket = {
  /** ISO hour key, e.g. "2026-07-11T06:00Z". */
  key: string;
  /** "HH:MM" (UTC) label for the hour tick. */
  hourLabel: string;
  /** "YYYY-MM-DD" (UTC) for tooltips / day boundaries. */
  dayLabel: string;
  startMs: number;
  counts: Record<TimelineEventKind, number>;
  total: number;
  /** Ascending event POSITIONS (array indexes) recorded inside this hour. */
  positions: number[];
};

export type ReplayHistogram = {
  buckets: ReplayBucket[];
  maxTotal: number;
  /** Event POSITIONS whose recorded ts failed to parse — stated, not dropped. */
  unplaced: number[];
};

function parseMs(iso: string | null | undefined): number | null {
  if (typeof iso !== "string" || !iso.trim()) return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

function hourFloor(ms: number): number {
  return ms - (ms % HOUR_MS);
}

function emptyCounts(): Record<TimelineEventKind, number> {
  return { run: 0, verdict: 0, receipt: 0 };
}

function makeBucket(startMs: number): ReplayBucket {
  const iso = new Date(startMs).toISOString();
  return {
    key: `${iso.slice(0, 13)}:00Z`,
    hourLabel: iso.slice(11, 16),
    dayLabel: iso.slice(0, 10),
    startMs,
    counts: emptyCounts(),
    total: 0,
    positions: [],
  };
}

function isEventKind(value: unknown): value is TimelineEventKind {
  return value === "run" || value === "verdict" || value === "receipt";
}

/**
 * Hourly histogram over the recorded events. Buckets are contiguous hours from
 * the earliest to the latest recorded timestamp (union'd with the projection
 * span when it parses), so an hour with nothing recorded renders as an honest
 * empty bar rather than being elided. Counts sum exactly to the number of
 * placeable events; unparseable timestamps land in `unplaced`.
 */
export function bucketize(
  events: ReadonlyArray<TimelineEvent>,
  span?: TimelineProjection["span"],
): ReplayHistogram {
  const placed: { position: number; kind: TimelineEventKind; hour: number }[] = [];
  const unplaced: number[] = [];
  for (let position = 0; position < events.length; position++) {
    const event = events[position];
    const ms = parseMs(event.ts);
    if (ms === null) {
      unplaced.push(position);
      continue;
    }
    const kind: TimelineEventKind = isEventKind(event.kind) ? event.kind : "run";
    placed.push({ position, kind, hour: hourFloor(ms) });
  }

  const hourSet = new Set<number>(placed.map((entry) => entry.hour));
  const spanStart = parseMs(span?.start ?? null);
  const spanEnd = parseMs(span?.end ?? null);
  if (spanStart !== null) hourSet.add(hourFloor(spanStart));
  if (spanEnd !== null) hourSet.add(hourFloor(spanEnd));
  if (hourSet.size === 0) return { buckets: [], maxTotal: 0, unplaced };

  const hours = [...hourSet].sort((a, b) => a - b);
  const first = hours[0];
  const last = hours[hours.length - 1];
  const contiguousCount = (last - first) / HOUR_MS + 1;

  const bucketStarts: number[] =
    contiguousCount <= MAX_CONTIGUOUS_BUCKETS
      ? Array.from({ length: contiguousCount }, (_, i) => first + i * HOUR_MS)
      : hours;

  const byStart = new Map<number, ReplayBucket>();
  const buckets = bucketStarts.map((start) => {
    const bucket = makeBucket(start);
    byStart.set(start, bucket);
    return bucket;
  });

  for (const entry of placed) {
    const bucket = byStart.get(entry.hour);
    if (!bucket) continue; // unreachable: every placed hour is a bucket start
    bucket.counts[entry.kind] += 1;
    bucket.total += 1;
    bucket.positions.push(entry.position);
  }
  for (const bucket of buckets) bucket.positions.sort((a, b) => a - b);

  const maxTotal = buckets.reduce((max, bucket) => Math.max(max, bucket.total), 0);
  return { buckets, maxTotal, unplaced };
}

/** Bucket array-index containing the event at `position`, or -1. */
export function playheadBucket(buckets: ReadonlyArray<ReplayBucket>, position: number): number {
  return buckets.findIndex((bucket) => bucket.positions.includes(position));
}

/** The chapter (if any) whose event_indexes include the event's `index` field. */
export function chapterForEvent(
  chapters: ReadonlyArray<TimelineChapter>,
  eventIndex: number,
): TimelineChapter | null {
  return chapters.find((chapter) => chapter.event_indexes.includes(eventIndex)) ?? null;
}

/**
 * Playback POSITIONS where a repair_loop chapter begins — the auto-pause beats.
 * Each chapter's first event is its smallest `event_indexes` entry, resolved to
 * the array position of the event carrying that `index` field. Sorted, deduped;
 * a chapter referencing no loaded event contributes nothing (never invented).
 */
export function chapterStartPositions(
  events: ReadonlyArray<TimelineEvent>,
  chapters: ReadonlyArray<TimelineChapter>,
): number[] {
  const positions = new Set<number>();
  for (const chapter of chapters) {
    if (chapter.event_indexes.length === 0) continue;
    const firstIndex = Math.min(...chapter.event_indexes);
    const position = events.findIndex((event) => event.index === firstIndex);
    if (position >= 0) positions.add(position);
  }
  return [...positions].sort((a, b) => a - b);
}

/** Smallest chapter-start position strictly after `current`, or null. */
export function nextPauseIndex(
  events: ReadonlyArray<TimelineEvent>,
  chapters: ReadonlyArray<TimelineChapter>,
  current: number,
): number | null {
  for (const position of chapterStartPositions(events, chapters)) {
    if (position > current) return position;
  }
  return null;
}

/** True when the event at `position` is the first beat of a repair_loop. */
export function isPausePosition(
  events: ReadonlyArray<TimelineEvent>,
  chapters: ReadonlyArray<TimelineChapter>,
  position: number,
): boolean {
  return chapterStartPositions(events, chapters).includes(position);
}

export type BucketChapterMark = {
  /** Chapter labels intersecting the bucket, in chapter order. */
  labels: string[];
  /** True when ANY intersecting chapter is open (unresolved wins the mark). */
  open: boolean;
};

/** Per-bucket repair-loop marks: which buckets carry chapter events, and
 *  whether any of those chapters is still open (renders dashed + "open"). */
export function bucketChapterMarks(
  buckets: ReadonlyArray<ReplayBucket>,
  events: ReadonlyArray<TimelineEvent>,
  chapters: ReadonlyArray<TimelineChapter>,
): (BucketChapterMark | null)[] {
  const positionsByChapter = chapters.map((chapter) => {
    const positions = new Set<number>();
    for (const index of chapter.event_indexes) {
      const position = events.findIndex((event) => event.index === index);
      if (position >= 0) positions.add(position);
    }
    return positions;
  });
  return buckets.map((bucket) => {
    const labels: string[] = [];
    let open = false;
    chapters.forEach((chapter, chapterIdx) => {
      if (bucket.positions.some((position) => positionsByChapter[chapterIdx].has(position))) {
        labels.push(chapter.label);
        if (chapter.open) open = true;
      }
    });
    return labels.length > 0 ? { labels, open } : null;
  });
}

/** "event N / M" position readout (1-based, real totals only). */
export function replayPositionReadout(position: number, total: number): string {
  if (total <= 0) return "no events recorded";
  const clamped = Math.min(Math.max(position, 0), total - 1);
  return `event ${clamped + 1} / ${total}`;
}

function summaryNumber(summary: Record<string, unknown>, key: string): number {
  const value = summary[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/** One-line rollup from the projection's REAL summary numbers. */
export function replaySummaryLine(projection: TimelineProjection): string {
  const s = projection.summary ?? {};
  const events = summaryNumber(s, "events");
  const runs = summaryNumber(s, "runs");
  const verdicts = summaryNumber(s, "verdicts");
  const receipts = summaryNumber(s, "receipts");
  const loops = summaryNumber(s, "repair_loops");
  return (
    `${events} event${events === 1 ? "" : "s"} · ${runs} run${runs === 1 ? "" : "s"} · ` +
    `${verdicts} verdict${verdicts === 1 ? "" : "s"} · ${receipts} receipt${receipts === 1 ? "" : "s"} · ` +
    `${loops} repair loop${loops === 1 ? "" : "s"}`
  );
}

export type ReplayDetailRow = {
  key: string;
  label: string;
  value: string;
  /** True for the recorded `status` field — rendered via StatusGlyph/statusTone. */
  isStatus: boolean;
};

/** Primitive detail fields of an event, in recorded order. Objects/arrays are
 *  skipped (the projection's detail is flat for known producers); status is
 *  flagged so the view routes it through statusTone, never bespoke coloring. */
export function replayDetailRows(event: TimelineEvent): ReplayDetailRow[] {
  const rows: ReplayDetailRow[] = [];
  for (const [key, raw] of Object.entries(event.detail ?? {})) {
    if (raw === null || raw === undefined) continue;
    if (typeof raw !== "string" && typeof raw !== "number" && typeof raw !== "boolean") continue;
    rows.push({
      key,
      label: key.replace(/_/g, " "),
      value: String(raw),
      isStatus: key === "status",
    });
  }
  return rows;
}

/** ISO ts → "YYYY-MM-DD HH:MM:SS" (kept UTC; callers append " UTC"). */
export function formatRecordedTs(iso: string): string {
  if (typeof iso !== "string" || iso.length < 19) return iso ?? "";
  return iso.slice(0, 19).replace("T", " ");
}
