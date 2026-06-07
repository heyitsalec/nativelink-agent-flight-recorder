import { useEffect, useMemo, useRef, useState } from "react";
import { select, zoom, zoomIdentity, type ZoomTransform } from "d3";
import {
  Bot,
  Braces,
  FileCheck2,
  Focus,
  GitBranch,
  GitCompare,
  Network,
  Route,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { highlightedIds, labelKind, remoteLensModel, sortRunwayNodes } from "../pageModel";
import type { PositionedNode, SourceKind } from "../types";
import type { ComponentInstance, ViewModeId } from "../view/types";
import { useViewContext } from "../view/ViewContext";
import { IconButton } from "./shared/IconButton";
import { boolProp, parseListProp, stringProp } from "./shared/props";
import { useOptionalZoomControllerRef } from "./shared/ZoomContext";
import { ViewTemplateSelector } from "./shared/ViewTemplateSelector";

const MODE_ICONS: Record<ViewModeId, React.ReactNode> = {
  graph: <GitBranch size={18} />,
  runway: <Route size={18} />,
  proof: <FileCheck2 size={18} />,
  remote: <Network size={18} />,
  compare: <GitCompare size={18} />,
};

export function ProjectionNoticePanel(_instance: ComponentInstance) {
  const { projectionNotice } = useViewContext();
  if (!projectionNotice) return null;
  return (
    <p
      className={`projection-notice projection-notice-${projectionNotice.tone}`}
      role="status"
    >
      {projectionNotice.message}
    </p>
  );
}

export function TopbarSummaryPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const projection = bindings.actionGraph;
  const showRemote = boolProp(instance.props, "show_remote_label", true);
  const remoteLens = useMemo(
    () => remoteLensModel(projection, bindings.proofPacket),
    [projection, bindings.proofPacket],
  );

  return (
    <header className="topbar">
      <div className="brand-mark">
        <Network size={18} />
        <span>NativeLink Agent Flight Recorder</span>
      </div>
      <ViewTemplateSelector />
      <div className="run-strip" aria-label="projection summary">
        <span>{String(projection.summary.runs ?? 0)} run</span>
        <span>{String(projection.summary.nodes ?? projection.nodes.length)} nodes</span>
        <span>{String(projection.summary.cache_events ?? 0)} cache events</span>
        <span>{String(projection.summary.failures ?? 0)} failures</span>
        {showRemote && <span>{remoteLens.modeLabel}</span>}
      </div>
    </header>
  );
}

export function ModeRailPanel(instance: ComponentInstance) {
  const { spec, route, routeActions } = useViewContext();
  const modeIds = parseListProp(instance.props?.modes) as ViewModeId[];
  const modes = spec.modes.filter((entry) => modeIds.length === 0 || modeIds.includes(entry.mode_id));

  return (
    <div className="mode-rail" aria-label="canvas tools">
      {modes.map((mode) => (
        <IconButton
          key={mode.mode_id}
          label={mode.label}
          active={route.mode === mode.mode_id}
          icon={MODE_ICONS[mode.mode_id]}
          onClick={() => {
            routeActions.setMode(mode.mode_id);
            if (mode.mode_id === "remote") routeActions.setFocus("remote");
            if (mode.mode_id === "compare") routeActions.setFocus("derived");
          }}
        />
      ))}
    </div>
  );
}

export function ZoomControlsPanel(instance: ComponentInstance) {
  const zoomRef = useOptionalZoomControllerRef();

  const applyZoom = (next: "in" | "out" | "reset") => {
    const ctrl = zoomRef?.current;
    if (!ctrl) return;
    if (next === "in") ctrl.zoomIn();
    else if (next === "out") ctrl.zoomOut();
    else ctrl.reset();
  };

  void stringProp(instance.props, "target_instance_id");

  return (
    <>
      <span className="rail-break" />
      <IconButton label="Zoom in" icon={<ZoomIn size={18} />} onClick={() => applyZoom("in")} />
      <IconButton label="Zoom out" icon={<ZoomOut size={18} />} onClick={() => applyZoom("out")} />
      <IconButton
        label="Reset view"
        icon={<RotateCcw size={18} />}
        onClick={() => applyZoom("reset")}
      />
    </>
  );
}

function centerTransform(svg: SVGSVGElement): ZoomTransform {
  const box = svg.getBoundingClientRect();
  const scale = box.width < 720 ? 0.44 : 0.95;
  return zoomIdentity.translate(box.width / 2, box.height / 2).scale(scale);
}

export function ActionGraphCanvasPanel(instance: ComponentInstance) {
  const { graph, route, routeActions } = useViewContext();
  const zoomRef = useOptionalZoomControllerRef();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const behaviorRef = useRef<ReturnType<typeof zoom<SVGSVGElement, unknown>> | null>(null);
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);

  const minScale = typeof instance.props?.scale_extent_min === "number" ? instance.props.scale_extent_min : 0.55;
  const maxScale = typeof instance.props?.scale_extent_max === "number" ? instance.props.scale_extent_max : 2.35;

  const highlighted = useMemo(
    () => highlightedIds(graph.nodes, route.focus),
    [graph.nodes, route.focus],
  );
  const selectedId = route.selectedId;

  useEffect(() => {
    if (!svgRef.current) return;
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([minScale, maxScale])
      .on("zoom", (event) => setTransform(event.transform));
    behaviorRef.current = behavior;
    select(svgRef.current).call(behavior);
    select(svgRef.current).call(behavior.transform, centerTransform(svgRef.current));
  }, [minScale, maxScale]);

  useEffect(() => {
    if (!zoomRef) return;
    zoomRef.current = {
      zoomIn: () => {
        if (!svgRef.current || !behaviorRef.current) return;
        select(svgRef.current).transition().duration(220).call(behaviorRef.current.scaleBy, 1.18);
      },
      zoomOut: () => {
        if (!svgRef.current || !behaviorRef.current) return;
        select(svgRef.current).transition().duration(220).call(behaviorRef.current.scaleBy, 0.84);
      },
      reset: () => {
        if (!svgRef.current || !behaviorRef.current) return;
        select(svgRef.current)
          .transition()
          .duration(420)
          .call(behaviorRef.current.transform, centerTransform(svgRef.current));
      },
      getTransform: () => transform,
    };
    return () => {
      if (zoomRef.current) zoomRef.current = null;
    };
  }, [zoomRef, transform]);

  return (
    <section className="canvas-stage" aria-label="NativeLink evidence canvas">
      <svg
        ref={svgRef}
        className="graph-canvas"
        role="img"
        aria-label="Action Graph projection"
      >
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(15, 23, 42, 0.06)" strokeWidth="1" />
          </pattern>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="rgba(15, 23, 42, 0.34)" />
          </marker>
        </defs>
        <rect x="-5000" y="-5000" width="10000" height="10000" fill="url(#grid)" />
        <g transform={transform.toString()}>
          <g className="edge-layer">
            {graph.edges.map((edge) => {
              const isActive =
                selectedId === edge.source.id ||
                selectedId === edge.target.id ||
                highlighted.has(edge.source.id) ||
                highlighted.has(edge.target.id);
              return (
                <line
                  key={edge.id}
                  x1={edge.source.x}
                  y1={edge.source.y}
                  x2={edge.target.x}
                  y2={edge.target.y}
                  className={`edge ${edge.source_kind} ${isActive ? "active" : ""}`}
                  markerEnd="url(#arrow)"
                />
              );
            })}
          </g>
          <g className="node-layer">
            {graph.nodes.map((node) => (
              <GraphNode
                key={node.id}
                node={node}
                selected={node.id === selectedId}
                dimmed={route.focus !== "all" && !highlighted.has(node.id)}
                onSelect={() => routeActions.setSelectedId(node.id)}
              />
            ))}
          </g>
        </g>
      </svg>
    </section>
  );
}

const REMOTE_WORKER_KINDS = new Set(["worker", "worker_readiness", "remote_execution_config"]);

function isRemoteWorkerKind(kind: string): boolean {
  return REMOTE_WORKER_KINDS.has(kind);
}

function hexagonPath(radius: number): string {
  const points: string[] = [];
  for (let index = 0; index < 6; index += 1) {
    const angle = (Math.PI / 3) * index - Math.PI / 6;
    points.push(`${Math.cos(angle) * radius},${Math.sin(angle) * radius}`);
  }
  return `M${points.join("L")}Z`;
}

function workerStatusLabel(node: PositionedNode): string | null {
  if (node.kind === "worker") {
    return String(node.status ?? "observed");
  }
  if (node.kind === "remote_execution_config") {
    const observed = node.payload?.worker_identity_observed;
    if (typeof observed === "boolean") {
      return observed ? "identity observed" : "identity gated";
    }
    return String(node.status ?? "configured");
  }
  if (node.kind === "worker_readiness") {
    return String(node.status ?? node.payload?.status ?? "readiness boundary");
  }
  return null;
}

function GraphNode({
  node,
  selected,
  dimmed,
  onSelect,
}: {
  node: PositionedNode;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
}) {
  const remoteWorker = isRemoteWorkerKind(node.kind);
  const shortLabel =
    node.label.length > (remoteWorker ? 22 : 26)
      ? `${node.label.slice(0, remoteWorker ? 20 : 24)}...`
      : node.label;
  const statusLabel = remoteWorker ? workerStatusLabel(node) : null;
  const labelY = remoteWorker ? 13 : 15;
  const confidenceY = node.radius + (remoteWorker ? 30 : 24);

  return (
    <g
      className={`graph-node ${node.kind} ${node.source_kind} ${remoteWorker ? "remote-worker" : ""} ${selected ? "selected" : ""} ${dimmed ? "dimmed" : ""}`}
      data-graph-node-id={node.id}
      transform={`translate(${node.x},${node.y})`}
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      tabIndex={0}
      role="button"
      aria-label={`${node.kind}: ${node.label}`}
    >
      {remoteWorker ? (
        <>
          <path className="node-halo" d={hexagonPath(node.radius + 12)} />
          <path className="node-body" d={hexagonPath(node.radius)} />
          <g
            className="node-worker-badge"
            transform={`translate(${node.radius - 9},${-node.radius + 9})`}
            aria-hidden="true"
          >
            <circle r={8} />
            <text textAnchor="middle" y={3.5}>
              {node.kind === "worker" ? "W" : "R"}
            </text>
          </g>
        </>
      ) : (
        <>
          <circle className="node-halo" r={node.radius + 12} />
          <circle className="node-body" r={node.radius} />
        </>
      )}
      <text className="node-kind" textAnchor="middle" y={-5}>
        {labelKind(node.kind)}
      </text>
      <text className="node-label" textAnchor="middle" y={labelY}>
        {shortLabel}
      </text>
      {statusLabel && (
        <text className="node-status" textAnchor="middle" y={node.radius + 16}>
          {statusLabel}
        </text>
      )}
      <text className="node-confidence" textAnchor="middle" y={confidenceY}>
        {node.confidence}
      </text>
    </g>
  );
}

export function TruthLegendPanel(instance: ComponentInstance) {
  const items = parseListProp(instance.props?.items) as SourceKind[];
  const catalog: { kind: SourceKind; label: string; hint: string }[] = [
    { kind: "collectable_v1", label: "collectable_v1", hint: "recorded from real tools" },
    { kind: "derived_v1", label: "derived_v1", hint: "computed from artifacts" },
    { kind: "simulated_v1", label: "simulated_v1", hint: "deterministic fixture" },
    { kind: "future", label: "future", hint: "claim not yet collected" },
  ];
  const visible = items.length ? catalog.filter((item) => items.includes(item.kind)) : catalog;

  return (
    <aside className="truth-legend" aria-label="truth label legend">
      <span className="truth-legend-title">Truth labels</span>
      <ul>
        {visible.map((item) => (
          <li key={item.kind} data-source-kind={item.kind}>
            <span className={`truth-dot ${item.kind}`} />
            <span className="truth-legend-label">{item.label}</span>
            <span className="truth-legend-hint">{item.hint}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export function ProofConstellationPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const packet = bindings.proofPacket;
  const scopeBlockId = stringProp(instance.props, "scope_block_id", "scope");
  const collectable = packet.blocks.filter((block) => block.source_kind === "collectable_v1").length;
  const derived = packet.blocks.filter((block) => block.source_kind === "derived_v1").length;
  const simulated = packet.blocks.filter((block) => block.source_kind === "simulated_v1").length;
  const future = packet.blocks.filter((block) => block.source_kind === "future").length;
  const scope = packet.blocks.find((block) => block.id === scopeBlockId);

  return (
    <div className="proof-constellation-overlay">
      <div className="proof-panel">
        <div className="proof-title">
          <ShieldCheck size={17} />
          <span>Proof Lens</span>
        </div>
        <p>{scope?.summary ?? "Claims stay bounded to recorded evidence."}</p>
        <div className="proof-metrics">
          <span>
            <Braces size={14} /> {collectable} collectable
          </span>
          <span>
            <Sparkles size={14} /> {derived} derived
          </span>
          <span>
            <Bot size={14} /> {simulated} simulated
          </span>
          <span>
            <Focus size={14} /> {future} future
          </span>
        </div>
      </div>
    </div>
  );
}

export function ValidationRunwayPanel(_instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const projection = bindings.actionGraph;
  const ordered = useMemo(() => sortRunwayNodes(projection.nodes), [projection.nodes]);

  return (
    <aside className="runway-overlay" aria-label="validation runway">
      <div className="runway-title">
        <Route size={17} />
        <span>Validation Runway</span>
      </div>
      <div className="runway-track">
        {ordered.map((node) => (
          <button
            key={node.id}
            className={`runway-event ${node.source_kind}`}
            onClick={() => routeActions.setSelectedId(node.id)}
            title={node.label}
          >
            <span>{labelKind(node.kind)}</span>
            <strong>{String(node.status ?? node.label)}</strong>
          </button>
        ))}
      </div>
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
