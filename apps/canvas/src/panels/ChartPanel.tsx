import { useEffect, useMemo, useRef, useState } from "react";
import { select, zoom, zoomIdentity, type ZoomTransform } from "d3";
import {
  Bot,
  Box,
  ChevronDown,
  ChevronRight,
  Columns2,
  Database,
  FileCheck2,
  FileText,
  GitCommitVertical,
  Globe,
  LayoutGrid,
  Maximize2,
  Network,
  Play,
  Route,
  Rows3,
  Server,
  Target,
  Terminal,
  TriangleAlert,
  X,
  Zap,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  evidenceMix,
  highlightedIds,
  labelKind,
  remoteLensModel,
  runwayArtifactColumns,
  runwayLanes,
  type RunwayLane,
} from "../pageModel";
import {
  buildGraphScene,
  type GraphSceneCard,
  type GraphSceneCluster,
  type GraphSceneEdge,
} from "../layout";
import { provenanceBadge } from "../receiptModel";
import type { ProjectionNode, SourceKind } from "../types";
import type { ComponentInstance, ViewModeId } from "../view/types";
import { useViewContext } from "../view/ViewContext";
import { IconButton } from "./shared/IconButton";
import { boolProp, parseListProp, stringProp } from "./shared/props";
import { useOptionalZoomControllerRef } from "./shared/ZoomContext";
import { ThemeToggle } from "./shared/ThemeToggle";
import { ViewTemplateSelector } from "./shared/ViewTemplateSelector";
import { Wordmark } from "./shared/Wordmark";
import { ConfidenceMeter, ProvenanceBadge, SourceGlyph, StatusGlyph, TruthLegend } from "./shared/truth";
import { SOURCE_KIND_META } from "./shared/truth/copy";

// Lens icons per board 1c: graph=network, runway=rows, proof=file-check,
// remote=globe, compare=columns.
const MODE_ICONS: Record<ViewModeId, React.ReactNode> = {
  graph: <Network size={18} />,
  runway: <Rows3 size={18} />,
  proof: <FileCheck2 size={18} />,
  remote: <Globe size={18} />,
  compare: <Columns2 size={18} />,
};

/** Honest name for a mix segment: the "unknown" bucket also absorbs any
 *  out-of-enum source_kind (see evidenceMix), so name it explicitly. */
function segmentLabel(kind: string): string {
  return kind === "unknown" ? "unknown source_kind" : kind;
}

/** Evidence-mix stacked bar — segments sized to the real node source_kind
 *  distribution of the loaded projection (board 1c). Real counts only. */
function EvidenceMixBar({ projection }: { projection: ReturnType<typeof useViewContext>["bindings"]["actionGraph"] }) {
  const mix = useMemo(() => evidenceMix(projection), [projection]);
  return (
    <span
      className="evidence-mix"
      role="img"
      aria-label={`evidence mix: ${mix.segments.map((s) => `${s.count} ${segmentLabel(s.kind)}`).join(", ")}`}
      title={mix.segments.map((s) => `${segmentLabel(s.kind)}: ${s.count} of ${mix.total}`).join(" · ")}
    >
      {mix.segments.map((seg) => (
        <span
          key={seg.kind}
          className={`evidence-mix-seg truth--${SOURCE_KIND_META[seg.kind].tone}`}
          data-source-kind={seg.kind}
          style={{ flexGrow: seg.count }}
        />
      ))}
    </span>
  );
}

/**
 * Context banner (board 1c): persistent 36px strip. Left = source glyph + run
 * group + projection descriptor + node count; right = evidence-mix bar. Tone
 * follows the evidence mix; the compare lens re-tones it derived. A fixture
 * fallback re-tones to the honest fallback state.
 */
export function ProjectionNoticePanel(_instance: ComponentInstance) {
  const { bindings, projectionNotice, route } = useViewContext();
  const projection = bindings.actionGraph;
  const mix = useMemo(() => evidenceMix(projection), [projection]);
  const dominant = mix.dominant;
  const isFallback = projectionNotice?.tone === "fallback";
  const compareToned = route.mode === "compare";
  // When the compare lens is active AND a compare projection is bound, the
  // banner states the REAL compare projection (board 1i): "left ↔ right —
  // derived_v1 compare projection · N dimensions" with the derived diamond —
  // not the underlying graph's collectable descriptor (redesign P6 fix m7).
  const compareProjection = compareToned ? bindings.compareProjection : null;

  const tone = isFallback ? "fallback" : compareToned ? "derived" : SOURCE_KIND_META[dominant].tone;
  const descriptor = isFallback
    ? projectionNotice?.message
    : `${SOURCE_KIND_META[dominant].enum} projection`;
  const glyphKind = isFallback ? "simulated_v1" : compareProjection ? "derived_v1" : dominant;

  return (
    <div className={`context-banner context-banner--${tone}`} data-testid="context-banner" role="status">
      <div className="context-banner-lead">
        <SourceGlyph kind={glyphKind} size={9} />
        {compareProjection ? (
          <span className="context-banner-text">
            <strong>
              {compareProjection.left_run_group} ↔ {compareProjection.right_run_group}
            </strong>
            {" — derived_v1 compare projection · "}
            <span className="context-banner-count">
              {compareProjection.dimensions.length} dimension
              {compareProjection.dimensions.length === 1 ? "" : "s"}
            </span>
          </span>
        ) : (
          <span className="context-banner-text">
            <strong>{projection.run_group}</strong> run group — {descriptor}
            {!isFallback && (
              <>
                {" · "}
                <span className="context-banner-count">{mix.total} nodes</span>
              </>
            )}
          </span>
        )}
      </div>
      <div className="context-banner-mix">
        <span className="context-banner-mix-caption">evidence mix</span>
        <EvidenceMixBar projection={projection} />
      </div>
    </div>
  );
}

/**
 * Header (board 1c): ~60px E2 bar. Wordmark · view picker · spacer ·
 * run-summary strip (real projection totals) · honest remote pill · theme
 * toggle. The remote pill reflects the real remote state and stays calm slate
 * (dashed), never red.
 */
export function TopbarSummaryPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const projection = bindings.actionGraph;
  const showRemote = boolProp(instance.props, "show_remote_label", true);
  const remoteLens = useMemo(
    () => remoteLensModel(projection, bindings.proofPacket),
    [projection, bindings.proofPacket],
  );
  const summary = projection.summary;
  const runs = Number(summary.runs ?? 0);
  const nodes = Number(summary.nodes ?? projection.nodes.length);
  const cacheEvents = Number(summary.cache_events ?? 0);
  const failures = Number(summary.failures ?? 0);
  // Observed only when the proof packet recorded real remote invocations —
  // never inferred from prose. Default projection has none → "not observed".
  const remoteInvocations = remoteLens.metrics.find((m) => m.label === "remote invocations")?.value ?? "0";
  const remoteObserved = remoteInvocations !== "0" && remoteInvocations !== "n/a";

  const stats: { value: number; label: string }[] = [
    { value: runs, label: runs === 1 ? "run" : "runs" },
    { value: nodes, label: "nodes" },
    { value: cacheEvents, label: cacheEvents === 1 ? "cache event" : "cache events" },
    { value: failures, label: failures === 1 ? "failure" : "failures" },
  ];

  return (
    <header className="topbar">
      <Wordmark />
      <ViewTemplateSelector />
      <span className="topbar-spacer" />
      <div className="run-strip" aria-label="projection summary">
        {stats.map((stat, index) => (
          <span key={stat.label} className="run-stat">
            {index > 0 && <span className="run-stat-sep" aria-hidden="true" />}
            <span className="run-stat-value">{stat.value}</span>
            <span className="run-stat-label">{stat.label}</span>
          </span>
        ))}
      </div>
      {showRemote && (
        <span
          className={`remote-pill${remoteObserved ? " remote-pill--observed" : ""}`}
          title={remoteLens.modeLabel}
          data-remote-observed={remoteObserved}
        >
          <SourceGlyph kind={remoteObserved ? "collectable_v1" : "future"} size={9} title={null} />
          <span>remote execution — {remoteObserved ? "observed" : "not observed"}</span>
        </span>
      )}
      <ThemeToggle />
    </header>
  );
}

/**
 * Left tool rail (board 1c): floating 44px E2 panel. Zoom-in/out/fit, a
 * divider, then the five lens buttons. Active lens = solid ink chip. Keeps the
 * mode-switch behaviour + aria-labels the truth-guard/captures depend on; the
 * fit button retains aria-label "Reset view" (capture selector).
 */
export function ModeRailPanel(instance: ComponentInstance) {
  const { spec, route, routeActions } = useViewContext();
  const zoomRef = useOptionalZoomControllerRef();
  const modeIds = parseListProp(instance.props?.modes) as ViewModeId[];
  const modes = spec.modes.filter((entry) => modeIds.length === 0 || modeIds.includes(entry.mode_id));

  const applyZoom = (next: "in" | "out" | "reset") => {
    const ctrl = zoomRef?.current;
    if (!ctrl) return;
    if (next === "in") ctrl.zoomIn();
    else if (next === "out") ctrl.zoomOut();
    else ctrl.reset();
  };

  // The zoom controls and the lens switcher are wrapped in two groups. On
  // desktop the groups are `display:contents`, so they vanish from layout and
  // the buttons flow directly in the vertical tool rail exactly as before (no
  // desktop regression). On mobile (board 1m, @media) the tool rail becomes
  // `display:contents` and the two groups reposition independently: the lens
  // group becomes a horizontal chip row under the header, the zoom group floats
  // top-right. Each lens chip carries a label span shown only on mobile.
  return (
    <nav className="tool-rail" aria-label="canvas tools">
      <div className="tool-rail-zoom">
        <IconButton label="Zoom in" icon={<ZoomIn size={18} />} onClick={() => applyZoom("in")} />
        <IconButton label="Zoom out" icon={<ZoomOut size={18} />} onClick={() => applyZoom("out")} />
        <IconButton label="Reset view" icon={<Maximize2 size={18} />} onClick={() => applyZoom("reset")} />
      </div>
      <span className="rail-break" />
      <div className="tool-rail-lenses" data-testid="lens-chip-row">
        {modes.map((mode) => (
          <IconButton
            key={mode.mode_id}
            label={mode.label}
            active={route.mode === mode.mode_id}
            icon={
              <>
                {MODE_ICONS[mode.mode_id]}
                <span className="rail-lens-label">{mode.label}</span>
              </>
            }
            onClick={() => {
              routeActions.setMode(mode.mode_id);
              if (mode.mode_id === "remote") routeActions.setFocus("remote");
              if (mode.mode_id === "compare") routeActions.setFocus("derived");
            }}
          />
        ))}
      </div>
    </nav>
  );
}

/**
 * Zoom controls consolidated into the tool rail (ModeRailPanel) in P3. Kept as
 * an inert slot so the view-spec instance still resolves; renders nothing.
 */
export function ZoomControlsPanel(instance: ComponentInstance) {
  void stringProp(instance.props, "target_instance_id");
  return null;
}

function centerTransform(svg: SVGSVGElement): ZoomTransform {
  const box = svg.getBoundingClientRect();
  const scale = box.width < 720 ? 0.44 : 0.95;
  return zoomIdentity.translate(box.width / 2, box.height / 2).scale(scale);
}

/** Padding kept between the fitted graph and the svg edge, in px. Trimmed
 *  (was 48) so the full-width scene fills more of the viewport at fit
 *  (redesign P6 fix M2). */
const FIT_PADDING_PX = 24;
/** Fit may zoom to a legible near-100% — board 1c lands at "fit · 100%".
 *  (was 0.95; the fit is now width-bound rather than height-bottlenecked so
 *  this cap is what lets the default graph read full, redesign P6 fix M2.) */
const MAX_FIT_SCALE = 1.0;
/** Provenance badges + card shadows render past the card boxes; keep them
 *  on-screen when fitting (agent badge extends ~32px below its card). */
const SCENE_FIT_MARGIN = 34;
/** Below this zoom, card meta rows hide and labels condense (LOD). */
const LOD_ZOOM_THRESHOLD = 0.6;
/** At/under this svg width the graph uses the mobile fit path (board 1m, P8).
 *  Matches the shell's responsive breakpoint so the two agree. */
const MOBILE_FIT_BREAKPOINT_PX = 720;
/** On mobile, fitting the whole tall 7-run scene collapses the graph to ~26%
 *  — below the LOD floor, so nodes are illegible and well under a 44px touch
 *  target. Instead the mobile default anchors the scene top-left at a legible,
 *  near-desktop scale and lets the operator PAN. Nothing is hidden: the honest
 *  count readout still names the full total, and the operator can still zoom
 *  OUT to the whole-scene overview (the scale-extent floor stays the true fit).
 *  0.9 keeps the 54px card ≈ 49px tall on screen (≥44px). */
const MOBILE_LEGIBLE_SCALE = 0.9;
const MOBILE_TOP_PAD_PX = 20;

type SceneBounds = { minX: number; minY: number; maxX: number; maxY: number };

function paddedBounds(bounds: SceneBounds): SceneBounds {
  return {
    minX: bounds.minX - SCENE_FIT_MARGIN,
    minY: bounds.minY - SCENE_FIT_MARGIN,
    maxX: bounds.maxX + SCENE_FIT_MARGIN,
    maxY: bounds.maxY + SCENE_FIT_MARGIN,
  };
}

/** The true fit-everything scale (0.2..MAX). Used for the zoom scale-extent
 *  FLOOR so the operator can always zoom out to the whole-scene overview — even
 *  on mobile, where the initial transform sits at the legible scale instead. */
function overviewFitScale(svg: SVGSVGElement, bounds: SceneBounds | null): number {
  const box = svg.getBoundingClientRect();
  if (!bounds || box.width <= 0 || box.height <= 0) return centerTransform(svg).k;
  const b = paddedBounds(bounds);
  const spanX = Math.max(b.maxX - b.minX, 1);
  const spanY = Math.max(b.maxY - b.minY, 1);
  return Math.max(
    0.2,
    Math.min(
      MAX_FIT_SCALE,
      (box.width - FIT_PADDING_PX * 2) / spanX,
      (box.height - FIT_PADDING_PX * 2) / spanY,
    ),
  );
}

function fitTransform(svg: SVGSVGElement, bounds: SceneBounds | null): ZoomTransform {
  const box = svg.getBoundingClientRect();
  if (!bounds || box.width <= 0 || box.height <= 0) {
    return centerTransform(svg);
  }
  const b = paddedBounds(bounds);
  const overview = overviewFitScale(svg, bounds);
  if (box.width < MOBILE_FIT_BREAKPOINT_PX) {
    // Mobile (board 1m): legible near-desktop scale, anchored top-left so the
    // change→run→invocation→artifact flow reads left-to-right; pannable.
    const scale = Math.min(MAX_FIT_SCALE, Math.max(MOBILE_LEGIBLE_SCALE, overview));
    return zoomIdentity
      .translate(FIT_PADDING_PX - b.minX * scale, MOBILE_TOP_PAD_PX - b.minY * scale)
      .scale(scale);
  }
  const scale = overview;
  const centerX = (b.minX + b.maxX) / 2;
  const centerY = (b.minY + b.maxY) / 2;
  return zoomIdentity
    .translate(box.width / 2 - centerX * scale, box.height / 2 - centerY * scale)
    .scale(scale);
}

/** Curved cubic edge path flowing between column-aligned entities. */
function edgePath(edge: GraphSceneEdge): string {
  const dx = edge.x2 - edge.x1;
  const bend = Math.max(Math.abs(dx) * 0.45, 24) * Math.sign(dx || 1);
  return `M ${edge.x1} ${edge.y1} C ${edge.x1 + bend} ${edge.y1}, ${edge.x2 - bend} ${edge.y2}, ${edge.x2} ${edge.y2}`;
}

export function ActionGraphCanvasPanel(instance: ComponentInstance) {
  const { bindings, route, routeActions } = useViewContext();
  const zoomRef = useOptionalZoomControllerRef();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const behaviorRef = useRef<ReturnType<typeof zoom<SVGSVGElement, unknown>> | null>(null);
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);
  // "fit" until the operator pans/zooms; reset returns to "fit".
  const [viewMode, setViewMode] = useState<"fit" | "zoom">("fit");

  const minScale = typeof instance.props?.scale_extent_min === "number" ? instance.props.scale_extent_min : 0.55;
  const maxScale = typeof instance.props?.scale_extent_max === "number" ? instance.props.scale_extent_max : 2.35;

  const projection = bindings.actionGraph;
  const selectedId = route.selectedId;

  // Density model (board 1c/1d): group by run, expand on demand. Default =
  // first run expanded, later runs + change column collapsed into clusters.
  const [expandedState, setExpandedState] = useState<ReadonlySet<string> | null>(null);
  const defaultExpanded = useMemo(() => {
    const firstRun = projection.nodes.find((node) => node.kind === "run");
    return new Set<string>(firstRun ? [firstRun.id] : []);
  }, [projection]);
  const expanded = expandedState ?? defaultExpanded;

  const scene = useMemo(
    () => buildGraphScene(projection, { expanded, selectedId }),
    [projection, expanded, selectedId],
  );

  const toggleExpand = (key: string | null) => {
    if (!key) return;
    setExpandedState((previous) => {
      const next = new Set(previous ?? defaultExpanded);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const highlighted = useMemo(
    () => highlightedIds(projection.nodes, route.focus),
    [projection.nodes, route.focus],
  );

  // Selection emphasis: neighbours stay bright, everything else dims.
  const neighborIds = useMemo(() => {
    if (!selectedId) return null;
    const ids = new Set<string>([selectedId]);
    for (const edge of scene.edges) {
      if (edge.fromId === selectedId) ids.add(edge.toId);
      if (edge.toId === selectedId) ids.add(edge.fromId);
    }
    return ids;
  }, [scene.edges, selectedId]);

  const cardDimmed = (card: GraphSceneCard): boolean => {
    if (route.focus !== "all" && !highlighted.has(card.node.id)) return true;
    if (neighborIds && !neighborIds.has(card.node.id)) return true;
    return false;
  };
  const clusterDimmed = (cluster: GraphSceneCluster): boolean => {
    if (route.focus !== "all" && !cluster.memberIds.some((id) => highlighted.has(id))) return true;
    if (neighborIds && !neighborIds.has(cluster.id)) return true;
    return false;
  };

  // Keep the latest scene bounds available to the zoom-init effect and the
  // Reset handler without re-running them (and stomping user zoom) whenever
  // expansion changes the layout.
  const boundsRef = useRef<SceneBounds | null>(scene.bounds);
  useEffect(() => {
    boundsRef.current = scene.bounds;
  }, [scene.bounds]);

  useEffect(() => {
    if (!svgRef.current) return;
    const fit = fitTransform(svgRef.current, boundsRef.current);
    const overview = overviewFitScale(svgRef.current, boundsRef.current);
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([Math.min(minScale, overview, fit.k), maxScale])
      .on("zoom", (event) => {
        setTransform(event.transform);
        if (event.sourceEvent) setViewMode("zoom");
      });
    behaviorRef.current = behavior;
    select(svgRef.current).call(behavior);
    select(svgRef.current).call(behavior.transform, fit);
  }, [minScale, maxScale]);

  useEffect(() => {
    if (!zoomRef) return;
    zoomRef.current = {
      zoomIn: () => {
        if (!svgRef.current || !behaviorRef.current) return;
        setViewMode("zoom");
        select(svgRef.current).transition().duration(220).call(behaviorRef.current.scaleBy, 1.18);
      },
      zoomOut: () => {
        if (!svgRef.current || !behaviorRef.current) return;
        setViewMode("zoom");
        select(svgRef.current).transition().duration(220).call(behaviorRef.current.scaleBy, 0.84);
      },
      reset: () => {
        if (!svgRef.current || !behaviorRef.current) return;
        const fit = fitTransform(svgRef.current, boundsRef.current);
        const overview = overviewFitScale(svgRef.current, boundsRef.current);
        behaviorRef.current.scaleExtent([Math.min(minScale, overview, fit.k), maxScale]);
        setViewMode("fit");
        select(svgRef.current)
          .transition()
          .duration(420)
          .call(behaviorRef.current.transform, fit);
      },
      getTransform: () => transform,
    };
    return () => {
      if (zoomRef.current) zoomRef.current = null;
    };
  }, [zoomRef, transform, minScale, maxScale]);

  const lod = transform.k < LOD_ZOOM_THRESHOLD;
  const { totals } = scene;
  const zoomPct = Math.round(transform.k * 100);
  // Honesty-critical readout: the visible-vs-total count is ALWAYS shown, and
  // collapsed nodes are counted — clustered is never "gone".
  const readout =
    totals.clusters > 0
      ? `${totals.total} total · ${totals.cards} cards · ${totals.clustered} in ${totals.clusters} cluster${totals.clusters === 1 ? "" : "s"}`
      : `${totals.total} nodes / ${totals.cards} shown`;

  // When a full-overlay lens is open (proof / remote / compare) the graph is
  // background context — dim it to ~38% (DESIGN-SYSTEM.md §4/§5/§6) so the
  // floating panel reads as the foreground. The inspector (graph/runway mode)
  // keeps the graph bright and interactive — it dims only non-neighbour nodes.
  const lensDimmed =
    route.mode === "proof" || route.mode === "remote" || route.mode === "compare";

  return (
    <section
      className={`canvas-stage${lensDimmed ? " canvas-stage--proof-dim" : ""}`}
      aria-label="NativeLink evidence canvas"
    >
      <svg
        ref={svgRef}
        className={`graph-canvas${lod ? " lod-compact" : ""}`}
        role="img"
        aria-label="Action Graph projection"
      >
        <g transform={transform.toString()}>
          <g className="edge-layer">
            {scene.edges.map((edge) => {
              const active =
                selectedId !== null && (edge.fromId === selectedId || edge.toId === selectedId);
              return (
                <path
                  key={edge.id}
                  d={edgePath(edge)}
                  className={`gedge ${edge.source_kind}${edge.dashed ? " dashed" : ""}${active ? " active" : ""}`}
                />
              );
            })}
          </g>
          <g className="node-layer">
            {scene.clusters.map((cluster) => (
              <ClusterCapsule
                key={cluster.id}
                cluster={cluster}
                dimmed={clusterDimmed(cluster)}
                onExpand={() => toggleExpand(cluster.expandKey)}
              />
            ))}
            {scene.cards.map((card) => (
              <GraphCard
                key={card.node.id}
                card={card}
                selected={card.node.id === selectedId}
                dimmed={cardDimmed(card)}
                onSelect={() => routeActions.setSelectedId(card.node.id)}
                onToggle={() => toggleExpand(card.expandKey)}
              />
            ))}
          </g>
        </g>
      </svg>
      <div
        className="graph-grouping-pill"
        title="Nodes group by run. Expand clusters on click; detail follows zoom (meta rows hide when zoomed out)."
      >
        <LayoutGrid size={11} aria-hidden="true" />
        <span>
          group <strong>by run</strong> · detail <strong>auto</strong>
        </span>
        <ChevronDown size={10} aria-hidden="true" />
      </div>
      <div
        className="graph-count-readout"
        data-testid="graph-count-readout"
        role="status"
        data-total={totals.total}
        data-cards={totals.cards}
        data-clustered={totals.clustered}
        data-clusters={totals.clusters}
        title="Every projection node is either a card or counted inside a labeled cluster — nothing is silently hidden."
      >
        {viewMode} · {zoomPct}% · {readout}
      </div>
    </section>
  );
}

const REMOTE_WORKER_KINDS = new Set(["worker", "worker_readiness", "remote_execution_config"]);

function isRemoteWorkerKind(kind: string): boolean {
  return REMOTE_WORKER_KINDS.has(kind);
}

/** Kinds whose labels are file paths / commands → mono label (board 1c). */
const MONO_LABEL_KINDS = new Set(["invocation", "artifact", "change"]);

/** Kind → lucide icon for the card plate (DESIGN-SYSTEM.md §1). */
const KIND_ICONS: Record<
  string,
  React.ComponentType<{
    size?: number | string;
    className?: string;
    "aria-hidden"?: React.AriaAttributes["aria-hidden"];
  }>
> = {
  run: Play,
  invocation: Terminal,
  artifact: FileText,
  agent: Bot,
  change: GitCommitVertical,
  target: Target,
  action: Zap,
  cache_event: Database,
  failure: TriangleAlert,
  worker: Server,
  worker_readiness: Server,
  remote_execution_config: Server,
};

/** Real recorded command line for invocation cards; node label otherwise. */
function cardLabel(node: ProjectionNode): string {
  if (node.kind === "invocation") {
    const command = node.payload?.command;
    if (Array.isArray(command) && command.every((part) => typeof part === "string")) {
      return command.join(" ");
    }
  }
  return node.label;
}

/**
 * Graph node card (boards 1c/1d/1o): rounded radius-12 card, source-hue
 * border, kind-icon plate on source tint (hexagon-clipped for worker/remote
 * kinds), label + faint mono suffix, and a meta row consuming the P2 truth
 * primitives — SourceGlyph (shape+hue) + ConfidenceMeter + mono kind/duration
 * + StatusGlyph. Truth is never re-encoded here.
 */
function GraphCard({
  card,
  selected,
  dimmed,
  onSelect,
  onToggle,
}: {
  card: GraphSceneCard;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
  onToggle: () => void;
}) {
  const node = card.node;
  const remoteWorker = isRemoteWorkerKind(node.kind);
  const sourceMeta = SOURCE_KIND_META[node.source_kind] ?? SOURCE_KIND_META.unknown;
  const agentBadge = node.kind === "agent" ? provenanceBadge(node.payload) : null;
  const Icon = KIND_ICONS[node.kind] ?? Box;
  const compactPlate = node.kind === "invocation" || node.kind === "artifact";
  const label = cardLabel(node);

  return (
    <g
      className={`gnode${selected ? " selected" : ""}${dimmed ? " dimmed" : ""}`}
      style={{ transform: `translate(${card.x}px, ${card.y}px)` }}
      data-graph-node-id={node.id}
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`${labelKind(node.kind)}: ${node.label}`}
    >
      <foreignObject
        className="gcard-fo"
        width={card.w}
        height={card.h + (agentBadge ? 32 : 0)}
      >
        <div
          className={`gcard truth-src--${sourceMeta.tone} gkind-${node.kind}${remoteWorker ? " gcard--worker" : ""}${card.expanded ? " gcard--open" : ""}${compactPlate ? " gcard--compact" : ""}`}
        >
          <span className={`gcard-plate truth--${sourceMeta.tone}`} aria-hidden="true">
            <Icon size={compactPlate ? 13 : 14} />
          </span>
          <span className="gcard-body">
            <span
              className={`gcard-label${MONO_LABEL_KINDS.has(node.kind) ? " gcard-label--mono" : ""}`}
              title={label}
            >
              <span className="gcard-label-text">{label}</span>
              {card.suffix && <span className="gcard-suffix">{card.suffix}</span>}
            </span>
            <span className="gcard-meta">
              <SourceGlyph kind={node.source_kind} size={8} />
              <ConfidenceMeter confidence={node.confidence} size="sm" />
              <span className="gcard-kindline" title={card.metaLine || undefined}>{card.metaLine}</span>
              {card.statusDisplay !== null && (
                <StatusGlyph status={card.statusDisplay} showLabel={false} />
              )}
              {card.expandable && (
                <button
                  type="button"
                  className="gcard-chevron"
                  aria-expanded={card.expanded}
                  aria-label={card.expanded ? "collapse grouped evidence" : "expand grouped evidence"}
                  onClick={(event) => {
                    event.stopPropagation();
                    onToggle();
                  }}
                >
                  <ChevronRight size={11} className="gcard-chevron-icon" aria-hidden="true" />
                </button>
              )}
            </span>
          </span>
        </div>
        {agentBadge && (
          <span
            className="gcard-badge"
            data-testid="agent-provenance-badge"
            data-provenance-class={agentBadge.provenanceClass}
            aria-label={`agent provenance: ${agentBadge.label}`}
          >
            <ProvenanceBadge badge={agentBadge} />
          </span>
        )}
      </foreignObject>
    </g>
  );
}

/**
 * Collapsed cluster (board 1c): a dashed source-hue capsule whose label is
 * derived from the REAL member nodes ("2 invocations · 6 artifacts"), or the
 * stacked-halo cluster card for the collapsed change column. Collapsed is
 * never gone — the counts keep every member discoverable, and clicking
 * expands the group (~200ms ease-out).
 */
function ClusterCapsule({
  cluster,
  dimmed,
  onExpand,
}: {
  cluster: GraphSceneCluster;
  dimmed: boolean;
  onExpand: () => void;
}) {
  const sourceMeta = SOURCE_KIND_META[cluster.sourceKind] ?? SOURCE_KIND_META.unknown;
  const leadKind = cluster.counts[0]?.kind ?? "artifact";
  const LeadIcon = KIND_ICONS[leadKind] ?? Box;
  const tooltip = `${cluster.memberIds.length} collapsed nodes (${cluster.label}) · dominant source_kind: ${sourceMeta.enum} — click to expand`;

  return (
    <g
      className={`gcluster${dimmed ? " dimmed" : ""}`}
      style={{ transform: `translate(${cluster.x}px, ${cluster.y}px)` }}
      data-graph-cluster-id={cluster.id}
      data-cluster-count={cluster.memberIds.length}
      onClick={(event) => {
        event.stopPropagation();
        onExpand();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onExpand();
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`collapsed group: ${cluster.label} — click to expand`}
    >
      <foreignObject className="gcard-fo" width={cluster.w} height={cluster.h}>
        {cluster.cardStyle ? (
          <div className={`gcard gcluster-card truth-src--${sourceMeta.tone}`} title={tooltip}>
            <span className={`gcard-plate truth--${sourceMeta.tone}`} aria-hidden="true">
              <LeadIcon size={14} />
            </span>
            <span className="gcard-body">
              <span className="gcard-label">
                <span className="gcard-label-text">{cluster.label}</span>
                {cluster.sampleLabel && <span className="gcard-suffix">· {cluster.sampleLabel}</span>}
              </span>
              <span className="gcard-meta">
                <SourceGlyph kind={cluster.sourceKind} size={8} />
                <span className="gcard-kindline">
                  {labelKind(leadKind)} ×{cluster.memberIds.length}
                </span>
                <ChevronDown size={11} className="gcluster-card-chevron" aria-hidden="true" />
              </span>
            </span>
          </div>
        ) : (
          <div className={`gcapsule truth-src--${sourceMeta.tone}`} title={tooltip}>
            <LeadIcon size={12} className="gcapsule-icon" aria-hidden="true" />
            <span className="gcapsule-label">{cluster.label}</span>
            <ChevronRight size={10} className="gcapsule-chevron" aria-hidden="true" />
          </div>
        )}
      </foreignObject>
    </g>
  );
}

export function TruthLegendPanel(instance: ComponentInstance) {
  const items = parseListProp(instance.props?.items) as SourceKind[];
  return <TruthLegend items={items.length ? items : undefined} />;
}

/**
 * Proof-lens overlay over the graph. In the P5 redesign the source-kind rollup
 * it used to carry now lives — richer and scannable — in the proof drawer
 * header (ProofDrawerPanel Zone A), and the graph behind the drawer is dimmed
 * rather than covered by a second card. So this overlay intentionally renders
 * nothing; the instance is kept in the view spec (its data-testid resolves) to
 * avoid a shell/spec change (P3 owns regions), and the proof lens identity is
 * carried by the active rail button + the drawer itself.
 */
export function ProofConstellationPanel(_instance: ComponentInstance) {
  return null;
}

/** Max chips a lane renders inline before an honest "· N more" overflow
 *  capsule — the lane gutter always states the FULL count, so nothing is
 *  hidden, only deferred. */
const RUNWAY_LANE_PREVIEW = 12;

/** "HH:MM" from an ISO timestamp, else null. */
function clockLabel(iso: unknown): string | null {
  if (typeof iso !== "string" || iso.length < 16) return null;
  return iso.slice(11, 16);
}

/** Ordered lane nodes: sequence (projection order) or by recorded start time
 *  when the scale toggle is on "time" — real payload timestamps only. */
function orderLaneNodes(lane: RunwayLane, scale: "sequence" | "time"): ProjectionNode[] {
  if (scale === "sequence") return lane.nodes;
  const withTime = lane.nodes.map((node, index) => ({
    node,
    index,
    started: typeof node.payload?.started_at === "string" ? String(node.payload.started_at) : null,
  }));
  withTime.sort((a, b) => {
    if (a.started && b.started) return a.started < b.started ? -1 : a.started > b.started ? 1 : a.index - b.index;
    if (a.started) return -1;
    if (b.started) return 1;
    return a.index - b.index;
  });
  return withTime.map((entry) => entry.node);
}

function RunwayChip({
  node,
  selected,
  onSelect,
}: {
  node: ProjectionNode;
  selected: boolean;
  onSelect: () => void;
}) {
  const clock = clockLabel(node.payload?.started_at);
  return (
    <button
      type="button"
      className={`runway-chip truth-src--${SOURCE_KIND_META[node.source_kind]?.tone ?? "unknown"}${selected ? " selected" : ""}`}
      onClick={onSelect}
      title={`${labelKind(node.kind)}: ${node.label}`}
    >
      <SourceGlyph kind={node.source_kind} size={9} />
      <span className="runway-chip-label">{node.label}</span>
      {clock && <span className="runway-chip-clock">{clock}</span>}
      {node.status !== null && node.status !== undefined && (
        <StatusGlyph status={node.status} showLabel={false} />
      )}
    </button>
  );
}

/**
 * Validation Runway (redesign P6 — DESIGN-SYSTEM.md §3, board 1j). A real lane
 * timeline over the loaded projection: fixed ordered lanes (runs / invocations
 * / targets / actions / cache / failures / artifacts), each a row of truth-
 * labelled chips or, when empty, ONE honest full-width dashed statement — an
 * empty lane states its emptiness, never blank. Selection is shared with the
 * graph. Real projection data only.
 */
export function ValidationRunwayPanel(_instance: ComponentInstance) {
  const { bindings, route, routeActions } = useViewContext();
  const projection = bindings.actionGraph;
  const lanes = useMemo(() => runwayLanes(projection.nodes), [projection.nodes]);
  // Per-run artifact counts for the artifacts lane's count pills (board 1j),
  // resolved through the real recorded run→invocation→artifact edges/refs.
  const artifactColumns = useMemo(
    () => runwayArtifactColumns(projection.nodes, projection.edges),
    [projection.nodes, projection.edges],
  );
  const [scale, setScale] = useState<"sequence" | "time">("sequence");

  const summary = projection.summary;
  const runs = Number(summary.runs ?? lanes.find((lane) => lane.kind === "run")?.count ?? 0);
  const invocations = lanes.find((lane) => lane.kind === "invocation")?.count ?? 0;
  const artifacts = lanes.find((lane) => lane.kind === "artifact")?.count ?? 0;

  // Axis ticks from recorded run start times (HH:MM), deduped in order — real
  // timestamps only; skipped entirely when no run carries one.
  const ticks = useMemo(() => {
    const runNodes = lanes.find((lane) => lane.kind === "run")?.nodes ?? [];
    const labels: string[] = [];
    for (const node of runNodes) {
      const clock = clockLabel(node.payload?.started_at);
      if (clock && !labels.includes(clock)) labels.push(clock);
    }
    return labels;
  }, [lanes]);

  return (
    <aside className="runway-panel" aria-label="validation runway">
      <button
        className="close-button runway-close"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close validation runway"
      >
        <X size={16} />
      </button>
      <header className="runway-head">
        <div className="runway-head-lead">
          <span className="runway-overline">VALIDATION RUNWAY</span>
          <h2 className="runway-heading">Validation runway</h2>
          <span className="runway-meta">
            {runs} runs · {invocations} invocations · {artifacts} artifacts
          </span>
        </div>
        <div className="runway-head-right">
          <span className="runway-shared">selection shared with graph</span>
          <div className="runway-scale" role="group" aria-label="runway scale">
            <button
              type="button"
              className={`runway-scale-btn${scale === "sequence" ? " active" : ""}`}
              onClick={() => setScale("sequence")}
              aria-pressed={scale === "sequence"}
            >
              sequence
            </button>
            <button
              type="button"
              className={`runway-scale-btn${scale === "time" ? " active" : ""}`}
              onClick={() => setScale("time")}
              aria-pressed={scale === "time"}
            >
              time
            </button>
          </div>
        </div>
      </header>
      <div className="runway-lanes">
        {lanes.map((lane) => {
          const ordered = orderLaneNodes(lane, scale);
          const shown = ordered.slice(0, RUNWAY_LANE_PREVIEW);
          const overflow = lane.count - shown.length;
          return (
            <div key={lane.kind} className="runway-lane">
              <div className="runway-lane-gutter">
                <span className="runway-lane-name">{lane.name}</span>
                <span className="runway-lane-count">{lane.count}</span>
              </div>
              <div className="runway-lane-track">
                {lane.empty ? (
                  <div className="runway-lane-empty">
                    <SourceGlyph kind="future" size={11} title={null} />
                    <span>{lane.emptyMessage}</span>
                  </div>
                ) : lane.kind === "artifact" ? (
                  // Per-run count pills aligned to the run columns (board 1j),
                  // not a flat filename list — a file icon + the run's real
                  // artifact count. An honest remainder pill covers any
                  // artifact that resolves to no run (redesign P6 fix M3).
                  <div className="runway-artifact-cols">
                    {artifactColumns.columns.map((col) => (
                      <span
                        key={col.runId}
                        className="runway-artifact-pill"
                        title={`${col.count} artifact${col.count === 1 ? "" : "s"} recorded under run ${col.label}`}
                      >
                        <FileText size={12} aria-hidden="true" />
                        <span className="runway-artifact-run">{col.label}</span>
                        <span className="runway-artifact-count">{col.count}</span>
                      </span>
                    ))}
                    {artifactColumns.unattributed > 0 && (
                      <span
                        className="runway-artifact-pill runway-artifact-pill--loose"
                        title="artifacts not attributable to a specific run in this projection"
                      >
                        <FileText size={12} aria-hidden="true" />
                        <span className="runway-artifact-run">·</span>
                        <span className="runway-artifact-count">{artifactColumns.unattributed}</span>
                      </span>
                    )}
                  </div>
                ) : (
                  <>
                    {shown.map((node) => (
                      <RunwayChip
                        key={node.id}
                        node={node}
                        selected={route.selectedId === node.id}
                        onSelect={() => routeActions.setSelectedId(node.id)}
                      />
                    ))}
                    {overflow > 0 && (
                      <span
                        className="runway-lane-overflow"
                        title={`${overflow} more ${lane.name} in this projection — expand on the graph`}
                      >
                        · {overflow} more
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {ticks.length > 0 && (
        <div className="runway-axis" aria-hidden="true">
          {ticks.map((tick, index) => (
            <span key={`${tick}-${index}`} className="runway-tick">
              {tick}
            </span>
          ))}
        </div>
      )}
    </aside>
  );
}

export type ChartPanelKind =
  | "projection_notice"
  | "topbar_summary"
  | "mode_rail"
  | "zoom_controls"
  | "action_graph_canvas"
  | "truth_legend"
  | "proof_constellation"
  | "validation_runway";

export const CHART_PANELS: Record<ChartPanelKind, (instance: ComponentInstance) => React.ReactNode> = {
  projection_notice: ProjectionNoticePanel,
  topbar_summary: TopbarSummaryPanel,
  mode_rail: ModeRailPanel,
  zoom_controls: ZoomControlsPanel,
  action_graph_canvas: ActionGraphCanvasPanel,
  truth_legend: TruthLegendPanel,
  proof_constellation: ProofConstellationPanel,
  validation_runway: ValidationRunwayPanel,
};
