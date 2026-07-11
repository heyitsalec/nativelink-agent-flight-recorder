import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, SkipBack, SkipForward, StepForward, X } from "lucide-react";
import {
  bucketChapterMarks,
  bucketize,
  chapterForEvent,
  chapterMetaLine,
  chapterStartPositions,
  formatRecordedTs,
  playheadBucket,
  playPressDecision,
  replayDetailRows,
  replayPositionReadout,
  replaySummaryLine,
  REPLAY_KIND_ORDER,
} from "../replayModel";
import { isRedactedValue } from "../pageModel";
import { provenanceBadge } from "../receiptModel";
import type { TimelineEvent, TimelineEventKind } from "../types";
import type { ComponentInstance } from "../view/types";
import { useViewContext } from "../view/ViewContext";
import { stringProp } from "./shared/props";
import { EvidenceRefs } from "./TablePanel";
import {
  ConfidenceMeter,
  ProvenanceBadge,
  RedactionChip,
  SourceGlyph,
  StatusGlyph,
  TruthLegend,
} from "./shared/truth";
import { SOURCE_KIND_META } from "./shared/truth/copy";

/**
 * Replay lens (flight-record playback). An hourly histogram of the timeline
 * projection's recorded events (stacked run / verdict / receipt), a playhead
 * with play/pause/step controls that walk the events chronologically and
 * AUTO-PAUSE on entering a derived repair_loop chapter, an event-detail card
 * rendering each event's own truth quad through the shared primitives, and
 * chapter jump chips (an open chapter is dashed and SAYS "open" — never
 * implied-closed). The canvas renders ONLY the projection: every count, label,
 * timestamp and chapter here is a recorded/derived projection field.
 *
 * Event kind (run/verdict/receipt) is NOT a truth label: it is encoded as
 * TEXTURE (solid / hatched / dotted) + text, never color alone, and each
 * event's real truth quad renders via SourceGlyph/ConfidenceMeter/
 * RedactionChip in the detail card (verdict status goes through statusTone via
 * StatusGlyph — no bespoke pass/fail coloring).
 *
 * NEW PRECEDENT — prefers-reduced-motion (first handling in this repo):
 * the playback tick is functional motion, not decorative, but under
 * `matchMedia("(prefers-reduced-motion: reduce)")` autoplay is DISABLED (the
 * play button becomes an explicit Step button) and the playhead's 180ms
 * ease-out transition is removed by the matching @media block in styles.css.
 * Follow this pattern for any future functional motion.
 */

/** Playback tick — one recorded event per interval. */
const PLAYBACK_TICK_MS = 900;

const KIND_TEXTURE: Record<TimelineEventKind, string> = {
  run: "solid",
  verdict: "hatched",
  receipt: "dotted",
};

function usePrefersReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduced, setReduced] = useState<boolean>(
    () =>
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia(query).matches,
  );
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(query);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** Honest empty state (compare's pattern) — no timeline projection is bound.
 *  NLFR never fabricates a replay; it names the file to place. */
function ReplayEmptyState({
  pathHint,
  onClose,
  onOpenComposer,
}: {
  pathHint: string;
  onClose: () => void;
  onOpenComposer: () => void;
}) {
  return (
    <aside className="replay-lens replay-lens--empty" aria-label="flight record replay">
      <button className="close-button replay-close" onClick={onClose} aria-label="Close replay lens">
        <X size={16} />
      </button>
      <div className="compare-empty-card" data-testid="replay-empty-state">
        <SourceGlyph kind="future" size={22} title={null} />
        <h2 className="compare-empty-title">No timeline is bound</h2>
        <p className="compare-empty-body">
          Place <code>{pathHint}</code> in <code>public/projections/</code> to replay the recorded
          flight record. NLFR never fabricates a replay.
        </p>
        <button
          type="button"
          className="compare-empty-composer"
          data-testid="replay-open-composer"
          title="Open the Composer drawer to bind run groups into a view spec."
          onClick={onOpenComposer}
        >
          Open Composer to bind run groups →
        </button>
      </div>
    </aside>
  );
}

/** Detail rows: status routes through StatusGlyph (statusTone); a redacted
 *  value keeps its slot as a lock chip carrying the partial path. */
function EventDetailRows({ event }: { event: TimelineEvent }) {
  const rows = replayDetailRows(event);
  if (rows.length === 0) return null;
  return (
    <dl className="replay-kv" aria-label="recorded detail fields">
      {rows.map((row) => (
        <div key={row.key}>
          <dt>{row.label}</dt>
          <dd>
            {row.isStatus ? (
              <StatusGlyph status={row.value} />
            ) : isRedactedValue(row.value) ? (
              <RedactionChip state="redacted" value={row.value} />
            ) : (
              <span>{row.value}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ReplayLensPanel(instance: ComponentInstance) {
  const { bindings, routeActions, overlayActions } = useViewContext();
  const projection = bindings.timelineProjection;
  const pathHint = stringProp(instance.props, "empty_state_path_hint") || "timeline.json";
  const reducedMotion = usePrefersReducedMotion();

  const events = useMemo(() => projection?.events ?? [], [projection]);
  const chapters = useMemo(() => projection?.chapters ?? [], [projection]);
  const histogram = useMemo(() => bucketize(events, projection?.span), [events, projection]);
  const pausePositions = useMemo(
    () => new Set(chapterStartPositions(events, chapters)),
    [events, chapters],
  );
  const chapterMarks = useMemo(
    () => bucketChapterMarks(histogram.buckets, events, chapters),
    [histogram.buckets, events, chapters],
  );

  const total = events.length;
  const lastPosition = Math.max(total - 1, 0);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [autoPaused, setAutoPaused] = useState(false);
  // The chapter-start position whose pause card was most recently shown
  // (review fix — pause-at-origin). Acknowledged means "the operator has SEEN
  // the pause card for this beat": auto-pause acknowledges on arrival, and
  // pressing play on an un-acknowledged chapter start shows the card instead
  // of silently advancing past it; the same start never re-pauses twice in a
  // row (playPressDecision in replayModel — unit-tested).
  const acknowledgedPauseRef = useRef<number | null>(null);
  useEffect(() => {
    acknowledgedPauseRef.current = null;
  }, [events]);

  // Advance one recorded event per tick while playing. Reduced motion never
  // reaches here (the play control is a Step button), but guard anyway.
  useEffect(() => {
    if (!playing || reducedMotion || total === 0) return;
    const id = window.setInterval(() => {
      setPosition((prev) => Math.min(prev + 1, lastPosition));
    }, PLAYBACK_TICK_MS);
    return () => window.clearInterval(id);
  }, [playing, reducedMotion, total, lastPosition]);

  // Auto-pause watcher: only a position CHANGE during playback can pause (the
  // standing-on-a-beat case is handled by togglePlay's pause-at-origin).
  const prevPositionRef = useRef(position);
  useEffect(() => {
    const moved = prevPositionRef.current !== position;
    prevPositionRef.current = position;
    if (!playing || !moved) return;
    if (pausePositions.has(position)) {
      setPlaying(false);
      setAutoPaused(true);
      acknowledgedPauseRef.current = position;
    } else if (position >= lastPosition) {
      setPlaying(false);
    }
  }, [position, playing, pausePositions, lastPosition]);

  const jumpTo = (next: number) => {
    setPlaying(false);
    setAutoPaused(false);
    setPosition(Math.min(Math.max(next, 0), lastPosition));
  };

  const step = (delta: 1 | -1) => jumpTo(position + delta);

  const togglePlay = () => {
    if (total === 0) return;
    if (reducedMotion) {
      // Reduced motion: the play affordance is an explicit single step.
      step(1);
      return;
    }
    if (playing) {
      setPlaying(false);
      return;
    }
    // Pause-at-origin (review fix): standing on a repair-loop start whose
    // pause card has not been shown → surface the card, don't move; the next
    // play (now acknowledged) advances.
    if (playPressDecision(events, chapters, position, acknowledgedPauseRef.current) === "pause_at_origin") {
      acknowledgedPauseRef.current = position;
      setAutoPaused(true);
      return;
    }
    setAutoPaused(false);
    if (position >= lastPosition) setPosition(0);
    setPlaying(true);
  };

  // Keyboard — ←/→ step, space plays/pauses (or steps under reduced motion).
  // A WINDOW listener (the ⌘K precedent) so the keys work the moment the lens
  // opens, without requiring focus inside it. Focus handling: typing surfaces
  // (input/textarea/select/contentEditable — e.g. the operator bar or the
  // palette) are never hijacked, and space on a focused button keeps its
  // native activation instead of double-firing playback. Space routes through
  // the SAME togglePlay as the button, so pause-at-origin applies to both.
  const keyActionsRef = useRef({ step, togglePlay });
  useEffect(() => {
    keyActionsRef.current = { step, togglePlay };
  });
  useEffect(() => {
    if (!projection) return;
    function onWindowKeyDown(event: KeyboardEvent) {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.closest("input, textarea, select") || target.isContentEditable)
      ) {
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        keyActionsRef.current.step(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        keyActionsRef.current.step(1);
      } else if (event.key === " " || event.key === "Spacebar") {
        if (target instanceof HTMLElement && target.closest("button, a, [role='button']")) {
          return; // native activation of the focused control wins
        }
        event.preventDefault();
        keyActionsRef.current.togglePlay();
      }
    }
    window.addEventListener("keydown", onWindowKeyDown);
    return () => window.removeEventListener("keydown", onWindowKeyDown);
  }, [projection]);

  if (!projection) {
    return (
      <ReplayEmptyState
        pathHint={pathHint}
        onClose={() => routeActions.setMode("graph")}
        onOpenComposer={() => overlayActions.openComposer()}
      />
    );
  }

  const current: TimelineEvent | null = total > 0 ? events[position] : null;
  const currentChapter = current ? chapterForEvent(chapters, current.index) : null;
  const activeBucket = playheadBucket(histogram.buckets, position);
  const bucketCount = histogram.buckets.length;
  // Playhead: bucket offset + intra-bucket fraction, as a % of the strip width.
  const innerFrac =
    activeBucket >= 0
      ? (histogram.buckets[activeBucket].positions.indexOf(position) + 0.5) /
        Math.max(histogram.buckets[activeBucket].positions.length, 1)
      : 0;
  const playheadPct =
    activeBucket >= 0 && bucketCount > 0 ? ((activeBucket + innerFrac) / bucketCount) * 100 : null;

  const sourceMeta = SOURCE_KIND_META[projection.source_kind] ?? SOURCE_KIND_META.unknown;
  const spanLine =
    projection.span.start && projection.span.end
      ? `${formatRecordedTs(projection.span.start)} → ${formatRecordedTs(projection.span.end)} UTC`
      : "no recorded span";
  const receiptBadge =
    current && current.kind === "receipt" ? provenanceBadge(current.detail) : null;

  return (
    <aside
      className="replay-lens"
      aria-label="flight record replay"
      data-reduced-motion={reducedMotion || undefined}
    >
      <button
        className="close-button replay-close"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close replay lens"
      >
        <X size={16} />
      </button>

      <header className="replay-head">
        <span className="replay-overline">REPLAY · RECORDED FLIGHT RECORD</span>
        <h2 className="replay-heading">{replaySummaryLine(projection)}</h2>
        <div className="replay-head-meta">
          <SourceGlyph kind={projection.source_kind} size={11} />
          <span className="replay-head-kind">{sourceMeta.enum} projection</span>
          <ConfidenceMeter confidence={projection.confidence} />
          {/* Rolled-up root redaction (most-restrictive over events/chapters) —
              a "redacted" rollup is stated, never hidden. */}
          <RedactionChip state={projection.redaction_state} />
          <span className="replay-head-span">{spanLine}</span>
          <span className="replay-head-sources">
            {projection.sources.length} source db{projection.sources.length === 1 ? "" : "s"}
          </span>
        </div>
      </header>

      {total === 0 ? (
        <div className="replay-no-events" data-testid="replay-no-events">
          <SourceGlyph kind="future" size={14} title={null} />
          <span>0 events recorded in this projection — nothing to replay, nothing invented.</span>
        </div>
      ) : (
        <>
          <div className="replay-histogram-block">
            <div className="replay-histogram" role="group" aria-label="hourly event histogram">
              {playheadPct !== null && (
                <span
                  className="replay-playhead"
                  data-testid="replay-playhead"
                  style={{ left: `${playheadPct}%` }}
                  aria-hidden="true"
                />
              )}
              {histogram.buckets.map((bucket, bucketIdx) => {
                const mark = chapterMarks[bucketIdx];
                const segTitle = REPLAY_KIND_ORDER.filter((kind) => bucket.counts[kind] > 0)
                  .map((kind) => `${bucket.counts[kind]} ${kind}`)
                  .join(" · ");
                return (
                  <button
                    key={bucket.key}
                    type="button"
                    className={`replay-bucket${bucketIdx === activeBucket ? " active" : ""}`}
                    disabled={bucket.positions.length === 0}
                    onClick={() => bucket.positions.length > 0 && jumpTo(bucket.positions[0])}
                    title={`${bucket.dayLabel} ${bucket.hourLabel} UTC — ${
                      bucket.total === 0 ? "no events recorded" : segTitle
                    }${mark ? ` · repair loop${mark.open ? " (open)" : ""}` : ""}`}
                    aria-label={`hour ${bucket.hourLabel}: ${
                      bucket.total === 0 ? "no events" : segTitle
                    }`}
                  >
                    <span className="replay-bar-count">{bucket.total > 0 ? bucket.total : ""}</span>
                    <span className="replay-bar" aria-hidden="true">
                      {REPLAY_KIND_ORDER.map((kind) =>
                        bucket.counts[kind] > 0 ? (
                          <span
                            key={kind}
                            className={`replay-seg replay-seg--${kind}`}
                            data-kind={kind}
                            style={{
                              height: `${(bucket.counts[kind] / Math.max(histogram.maxTotal, 1)) * 100}%`,
                            }}
                          />
                        ) : null,
                      )}
                    </span>
                    {mark ? (
                      <span
                        className={`replay-chapter-mark${mark.open ? " replay-chapter-mark--open" : ""}`}
                        aria-hidden="true"
                      >
                        {mark.open ? "open" : ""}
                      </span>
                    ) : (
                      <span className="replay-chapter-mark replay-chapter-mark--none" aria-hidden="true" />
                    )}
                    <span className="replay-bar-hour">{bucket.hourLabel}</span>
                  </button>
                );
              })}
            </div>
            <div className="replay-kind-legend" aria-label="event kind encoding — texture, not color alone">
              {REPLAY_KIND_ORDER.map((kind) => (
                <span key={kind} className="replay-kind-legend-item">
                  <i className={`replay-swatch replay-seg--${kind}`} aria-hidden="true" />
                  {kind} · {KIND_TEXTURE[kind]}
                </span>
              ))}
            </div>
            {histogram.unplaced.length > 0 && (
              <p className="replay-unplaced" role="note">
                {histogram.unplaced.length} event{histogram.unplaced.length === 1 ? "" : "s"} carry no
                parseable recorded timestamp — reachable by stepping, not placed on the histogram.
              </p>
            )}
          </div>

          <div className="replay-controls" role="group" aria-label="playback controls">
            <button
              type="button"
              className="replay-ctl"
              data-testid="replay-prev"
              aria-label="Previous event"
              onClick={() => step(-1)}
              disabled={position <= 0}
            >
              <SkipBack size={15} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="replay-ctl replay-ctl--play"
              data-testid="replay-play"
              aria-label={reducedMotion ? "Step to next event" : playing ? "Pause" : "Play"}
              title={
                reducedMotion
                  ? "Reduced motion is on — autoplay is disabled; this steps one event."
                  : "Playback pauses automatically when a repair loop begins."
              }
              onClick={togglePlay}
              disabled={total === 0 || (reducedMotion && position >= lastPosition)}
            >
              {reducedMotion ? (
                <StepForward size={15} aria-hidden="true" />
              ) : playing ? (
                <Pause size={15} aria-hidden="true" />
              ) : (
                <Play size={15} aria-hidden="true" />
              )}
            </button>
            <button
              type="button"
              className="replay-ctl"
              data-testid="replay-next"
              aria-label="Next event"
              onClick={() => step(1)}
              disabled={position >= lastPosition}
            >
              <SkipForward size={15} aria-hidden="true" />
            </button>
            <span className="replay-position" data-testid="replay-position" role="status">
              {replayPositionReadout(position, total)}
            </span>
            <span className="replay-keys" aria-hidden="true">
              ← → step · space {reducedMotion ? "steps" : "plays"}
            </span>
          </div>

          <div className="replay-chapters" aria-label="repair loop chapters">
            <span className="replay-chapters-overline">CHAPTERS</span>
            {chapters.length === 0 ? (
              <span className="replay-chapters-empty">
                no repair loops recorded in this projection
              </span>
            ) : (
              chapters.map((chapter, chapterIdx) => {
                const firstIndex =
                  chapter.event_indexes.length > 0 ? Math.min(...chapter.event_indexes) : null;
                const chapterPosition =
                  firstIndex === null
                    ? -1
                    : events.findIndex((event) => event.index === firstIndex);
                return (
                  <button
                    key={`${chapter.label}-${chapterIdx}`}
                    type="button"
                    className={`replay-chapter-chip${chapter.open ? " replay-chapter-chip--open" : ""}${
                      currentChapter === chapter ? " active" : ""
                    }`}
                    data-testid="replay-chapter-chip"
                    data-chapter-open={chapter.open}
                    data-lineage={chapter.lineage ?? undefined}
                    disabled={chapterPosition < 0}
                    onClick={() => chapterPosition >= 0 && jumpTo(chapterPosition)}
                    title={
                      chapter.open
                        ? `${chapterMetaLine(chapter)} (started ${formatRecordedTs(chapter.start_ts)} UTC)`
                        : `${chapterMetaLine(chapter)} — ${formatRecordedTs(chapter.start_ts)} → ${
                            chapter.end_ts ? formatRecordedTs(chapter.end_ts) : "?"
                          } UTC · ${chapter.event_indexes.length} events`
                    }
                  >
                    <SourceGlyph kind={chapter.source_kind} size={9} title={null} />
                    <span>{chapter.label}</span>
                    <span className="replay-chapter-chip-meta">
                      {chapter.open ? "open" : `${chapter.event_indexes.length} events`}
                    </span>
                  </button>
                );
              })
            )}
          </div>

          {current && (
            <section
              className={`replay-event-card${autoPaused ? " replay-event-card--paused" : ""}`}
              data-testid="replay-event-card"
              data-event-position={position + 1}
              data-event-index={current.index}
              aria-label={`event ${position + 1} of ${total}`}
            >
              {autoPaused && currentChapter && (
                <div className="replay-pause-note" data-testid="replay-pause-note" role="status">
                  paused — {currentChapter.label} begins here
                </div>
              )}
              <header className="replay-event-head">
                <span className="replay-event-overline">EVENT {position + 1} / {total}</span>
                <span className="replay-event-kind">
                  <i className={`replay-swatch replay-seg--${current.kind}`} aria-hidden="true" />
                  {current.kind}
                </span>
                {receiptBadge && <ProvenanceBadge badge={receiptBadge} />}
              </header>
              <h3 className="replay-event-label">{current.label}</h3>
              <div className="replay-event-meta">
                <span className="replay-event-source" title="evidence database this event was read from">
                  source db · <code>{current.source}</code>
                </span>
                <span className="replay-event-ts">recorded {formatRecordedTs(current.ts)} UTC</span>
              </div>
              {currentChapter && (
                <p className="replay-event-chapter" data-testid="replay-event-chapter">
                  {chapterMetaLine(currentChapter)}
                </p>
              )}
              <EventDetailRows event={current} />
              <div className="replay-event-truth" aria-label="truth labels">
                <span className="truth-value">
                  <SourceGlyph kind={current.source_kind} size={11} />
                  <span>{(SOURCE_KIND_META[current.source_kind] ?? SOURCE_KIND_META.unknown).enum}</span>
                </span>
                <span className="truth-value">
                  <ConfidenceMeter confidence={current.confidence} />
                  <span>{current.confidence}</span>
                </span>
                <RedactionChip state={current.redaction_state} />
              </div>
              <EvidenceRefs refs={current.evidence_refs} defaultOpen={false} />
            </section>
          )}
        </>
      )}

      <div className="replay-legend-slot">
        <TruthLegend />
      </div>
    </aside>
  );
}

export type ReplayPanelKind = "replay_timeline";

export const REPLAY_PANELS: Record<ReplayPanelKind, (instance: ComponentInstance) => React.ReactNode> = {
  replay_timeline: ReplayLensPanel,
};
