import { useEffect, useMemo, useRef, useState } from "react";
import { select, zoom, zoomIdentity, type ZoomTransform } from "d3";
import {
  Bot,
  Braces,
  FileCheck2,
  Focus,
  GitBranch,
  Maximize2,
  MessageCircle,
  Network,
  Route,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { layoutProjection } from "./layout";
import { sampleProofPacket, sampleProjection } from "./sampleProjection";
import type {
  ActionGraphProjection,
  CanvasMode,
  FocusFilter,
  PositionedNode,
  ProofBlock,
  ProofMetricValue,
  ProofPacket,
  SourceKind,
} from "./types";

const projectionPath = "/projections/action-graph.json";
const proofPath = "/projections/proof.json";

export function App() {
  const [projection, setProjection] = useState<ActionGraphProjection>(sampleProjection);
  const [proofPacket, setProofPacket] = useState<ProofPacket>(sampleProofPacket);
  const [mode, setMode] = useState<CanvasMode>("graph");
  const [focus, setFocus] = useState<FocusFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [operatorNote, setOperatorNote] = useState("Ask for cache, failures, proof, runway, or reset.");
  const [usingFixtureFallback, setUsingFixtureFallback] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomRef = useRef<ReturnType<typeof zoom<SVGSVGElement, unknown>> | null>(null);
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity);

  useEffect(() => {
    let active = true;
    fetch(projectionPath)
      .then((response) => {
        if (!response.ok) throw new Error("projection missing");
        return response.json() as Promise<ActionGraphProjection>;
      })
      .then((payload) => {
        if (active) {
          setProjection(payload);
          setUsingFixtureFallback(false);
        }
      })
      .catch(() => {
        if (active) {
          setProjection(sampleProjection);
          setUsingFixtureFallback(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    fetch(proofPath)
      .then((response) => {
        if (!response.ok) throw new Error("proof packet missing");
        return response.json() as Promise<ProofPacket>;
      })
      .then((payload) => {
        if (active) {
          setProofPacket(payload);
          setUsingFixtureFallback(false);
        }
      })
      .catch(() => {
        if (active) {
          setProofPacket(sampleProofPacket);
          setUsingFixtureFallback(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const graph = useMemo(() => layoutProjection(projection), [projection]);
  const selectedNode = graph.nodes.find((node) => node.id === selectedId) ?? null;
  const highlighted = useMemo(() => highlightedIds(graph.nodes, focus), [graph.nodes, focus]);
  const remoteLens = useMemo(() => remoteLensModel(projection, proofPacket), [projection, proofPacket]);

  useEffect(() => {
    if (!svgRef.current) return;
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.55, 2.35])
      .on("zoom", (event) => setTransform(event.transform));
    zoomRef.current = behavior;
    select(svgRef.current).call(behavior);
    select(svgRef.current).call(behavior.transform, centerTransform(svgRef.current));
  }, []);

  function applyZoom(next: "in" | "out" | "reset") {
    if (!svgRef.current || !zoomRef.current) return;
    const selection = select(svgRef.current);
    if (next === "reset") {
      selection.transition().duration(420).call(zoomRef.current.transform, centerTransform(svgRef.current));
      return;
    }
    selection.transition().duration(220).call(zoomRef.current.scaleBy, next === "in" ? 1.18 : 0.84);
  }

  function runOperatorCommand() {
    const value = command.trim().toLowerCase();
    if (!value) return;
    if (value.includes("cache")) {
      setFocus("cache");
      setMode("graph");
      setOperatorNote("Cache evidence is highlighted; derived events stay amber.");
    } else if (value.includes("fail")) {
      setFocus("failures");
      setMode("graph");
      const firstFailure = graph.nodes.find((node) => node.kind === "failure");
      setSelectedId(firstFailure?.id ?? null);
      setOperatorNote("Failure path is isolated with its evidence refs open.");
    } else if (value.includes("proof")) {
      setMode("proof");
      setFocus("derived");
      setOperatorNote("Proof lens is open; unsupported claims remain explicit.");
    } else if (value.includes("remote") || value.includes("worker") || value.includes("execution")) {
      setMode("remote");
      setFocus("remote");
      setOperatorNote("Remote boundary is isolated; worker claims stay gated.");
    } else if (value.includes("runway") || value.includes("timeline")) {
      setMode("runway");
      setFocus("all");
      setOperatorNote("Validation runway is projected over the same graph evidence.");
    } else {
      setMode("graph");
      setFocus("all");
      setSelectedId(null);
      applyZoom("reset");
      setOperatorNote("Canvas reset to the full Action Graph.");
    }
    setCommand("");
  }

  return (
    <main className="app-shell" data-testid="nlfr-canvas-app">
      {usingFixtureFallback && (
        <p className="fixture-fallback-banner" role="status">
          Fixture fallback active — projection fetch failed; showing simulated sample data.
        </p>
      )}
      <header className="topbar">
        <div className="brand-mark">
          <Network size={18} />
          <span>NativeLink Agent Flight Recorder</span>
        </div>
        <div className="run-strip" aria-label="projection summary">
          <span>{String(projection.summary.runs ?? 0)} run</span>
          <span>{String(projection.summary.nodes ?? projection.nodes.length)} nodes</span>
          <span>{String(projection.summary.cache_events ?? 0)} cache events</span>
          <span>{String(projection.summary.failures ?? 0)} failures</span>
          <span>{remoteLens.modeLabel}</span>
        </div>
      </header>

      <div className="mode-rail" aria-label="canvas tools" data-testid="canvas-mode-rail">
        <IconButton
          label="Action Graph"
          active={mode === "graph"}
          icon={<GitBranch size={18} />}
          onClick={() => setMode("graph")}
        />
        <IconButton
          label="Validation Runway"
          active={mode === "runway"}
          icon={<Route size={18} />}
          onClick={() => setMode("runway")}
        />
        <IconButton
          label="Proof Packet"
          active={mode === "proof"}
          icon={<FileCheck2 size={18} />}
          onClick={() => setMode("proof")}
        />
        <IconButton
          label="Remote Boundary"
          active={mode === "remote"}
          icon={<Network size={18} />}
          onClick={() => {
            setMode("remote");
            setFocus("remote");
          }}
        />
        <span className="rail-break" />
        <IconButton label="Zoom in" icon={<ZoomIn size={18} />} onClick={() => applyZoom("in")} />
        <IconButton label="Zoom out" icon={<ZoomOut size={18} />} onClick={() => applyZoom("out")} />
        <IconButton label="Reset view" icon={<RotateCcw size={18} />} onClick={() => applyZoom("reset")} />
      </div>

      <section className="canvas-stage" aria-label="NativeLink evidence canvas">
        <svg
          ref={svgRef}
          className="graph-canvas"
          role="img"
          aria-label="Action Graph projection"
          data-testid="action-graph-svg"
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
                  dimmed={focus !== "all" && !highlighted.has(node.id)}
                  onSelect={() => setSelectedId(node.id)}
                />
              ))}
            </g>
            {mode === "proof" && <ProofConstellation packet={proofPacket} />}
          </g>
        </svg>
        {mode === "runway" && <RunwayOverlay projection={projection} onSelect={setSelectedId} />}
        {mode === "proof" && <ProofDrawer packet={proofPacket} onClose={() => setMode("graph")} />}
        {mode === "remote" && <RemoteLens lens={remoteLens} onClose={() => setMode("graph")} />}
        {selectedNode && mode !== "proof" && mode !== "remote" && (
          <Inspector node={selectedNode} onClose={() => setSelectedId(null)} />
        )}
      </section>

      <div className="operator" data-testid="operator-chat">
        <MessageCircle size={18} />
        <div className="operator-copy">
          <span>{operatorNote}</span>
          <input
            aria-label="operator command"
            value={command}
            placeholder="focus cache misses"
            onChange={(event) => setCommand(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") runOperatorCommand();
            }}
          />
        </div>
        <button className="operator-run" onClick={runOperatorCommand} aria-label="Run operator command">
          <Search size={17} />
        </button>
      </div>
    </main>
  );
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
  const shortLabel = node.label.length > 26 ? `${node.label.slice(0, 24)}...` : node.label;
  return (
    <g
      className={`graph-node ${node.kind} ${node.source_kind} ${selected ? "selected" : ""} ${dimmed ? "dimmed" : ""}`}
      transform={`translate(${node.x},${node.y})`}
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      tabIndex={0}
      role="button"
      aria-label={`${node.kind}: ${node.label}`}
    >
      <circle className="node-halo" r={node.radius + 12} />
      <circle className="node-body" r={node.radius} />
      <text className="node-kind" textAnchor="middle" y={-5}>
        {labelKind(node.kind)}
      </text>
      <text className="node-label" textAnchor="middle" y={15}>
        {shortLabel}
      </text>
      <text className="node-confidence" textAnchor="middle" y={node.radius + 24}>
        {node.confidence}
      </text>
    </g>
  );
}

function Inspector({ node, onClose }: { node: PositionedNode; onClose: () => void }) {
  return (
    <aside className="inspector" aria-label="selected evidence" data-testid="evidence-inspector">
      <button className="close-button" onClick={onClose} aria-label="Close inspector">
        <Maximize2 size={16} />
      </button>
      <div className="inspector-heading">
        <span className={`truth-dot ${node.source_kind}`} />
        <p>{labelKind(node.kind)}</p>
        <h2>{node.label}</h2>
      </div>
      <dl className="truth-grid">
        <div>
          <dt>Source</dt>
          <dd>{node.source_kind}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{node.confidence}</dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd>{node.redaction_state}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{String(node.status ?? "unknown")}</dd>
        </div>
      </dl>
      <div className="evidence-list">
        <span>Evidence refs</span>
        {node.evidence_refs.map((ref) => (
          <code key={ref}>{ref}</code>
        ))}
      </div>
      {node.payload && Object.keys(node.payload).length > 0 && (
        <pre className="payload">{JSON.stringify(node.payload, null, 2)}</pre>
      )}
    </aside>
  );
}

function RunwayOverlay({
  projection,
  onSelect,
}: {
  projection: ActionGraphProjection;
  onSelect: (id: string) => void;
}) {
  const ordered = [...projection.nodes].sort((a, b) => laneIndex(a.kind) - laneIndex(b.kind));
  return (
    <aside className="runway-overlay" aria-label="validation runway" data-testid="validation-runway">
      <div className="runway-title">
        <Route size={17} />
        <span>Validation Runway</span>
      </div>
      <div className="runway-track">
        {ordered.map((node) => (
          <button
            key={node.id}
            className={`runway-event ${node.source_kind}`}
            onClick={() => onSelect(node.id)}
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

function ProofConstellation({ packet }: { packet: ProofPacket }) {
  const collectable = packet.blocks.filter((block) => block.source_kind === "collectable_v1").length;
  const derived = packet.blocks.filter((block) => block.source_kind === "derived_v1").length;
  const simulated = packet.blocks.filter((block) => block.source_kind === "simulated_v1").length;
  const future = packet.blocks.filter((block) => block.source_kind === "future").length;
  const scope = packet.blocks.find((block) => block.id === "scope");
  return (
    <g className="proof-constellation" transform="translate(-420,-330)">
      <foreignObject width="360" height="216">
        <div className="proof-panel">
          <div className="proof-title">
            <ShieldCheck size={17} />
            <span>Proof Lens</span>
          </div>
          <p>{scope?.summary ?? "Claims stay bounded to recorded evidence."}</p>
          <div className="proof-metrics">
            <span><Braces size={14} /> {collectable} collectable</span>
            <span><Sparkles size={14} /> {derived} derived</span>
            <span><Bot size={14} /> {simulated} simulated</span>
            <span><Focus size={14} /> {future} future</span>
          </div>
        </div>
      </foreignObject>
    </g>
  );
}

function ProofDrawer({ packet, onClose }: { packet: ProofPacket; onClose: () => void }) {
  const summaryEntries = Object.entries(packet.summary).filter(
    ([, value]) => typeof value === "number" || typeof value === "string",
  );
  return (
    <aside className="proof-drawer" aria-label="proof packet" data-testid="proof-drawer">
      <button className="close-button" onClick={onClose} aria-label="Close proof drawer">
        <X size={16} />
      </button>
      <div className="proof-drawer-heading">
        <ShieldCheck size={18} />
        <p>Proof Packet</p>
        <h2>{packet.run_group}</h2>
      </div>
      <div className="proof-summary" aria-label="proof summary">
        {summaryEntries.map(([key, value]) => (
          <span key={key}>
            <strong>{formatMetricValue(value as ProofMetricValue)}</strong>
            {labelKind(key)}
          </span>
        ))}
      </div>
      <div className="proof-block-list">
        {packet.blocks.map((block) => (
          <ProofBlockView key={block.id} block={block} />
        ))}
      </div>
    </aside>
  );
}

function RemoteLens({
  lens,
  onClose,
}: {
  lens: ReturnType<typeof remoteLensModel>;
  onClose: () => void;
}) {
  return (
    <aside className="remote-lens" aria-label="remote execution boundary" data-testid="remote-execution-lens">
      <button className="close-button" onClick={onClose} aria-label="Close remote boundary">
        <X size={16} />
      </button>
      <div className="remote-lens-heading">
        <Network size={18} />
        <p>Remote Boundary</p>
        <h2>{lens.statusLabel}</h2>
      </div>
      <div className="remote-state-line">
        <span className={`truth-dot ${lens.sourceKind}`} />
        <strong>{lens.modeLabel}</strong>
        <span>{lens.confidence}</span>
      </div>
      <div className="remote-metrics">
        {lens.metrics.map((metric) => (
          <span key={metric.label}>
            <strong>{metric.value}</strong>
            {metric.label}
          </span>
        ))}
      </div>
      <div className="remote-boundaries">
        {lens.boundaries.map((boundary) => (
          <section key={boundary.title} className={`remote-boundary ${boundary.sourceKind}`}>
            <div>
              <p>{boundary.kind}</p>
              <h3>{boundary.title}</h3>
            </div>
            <span>{boundary.confidence}</span>
            <p>{boundary.summary}</p>
          </section>
        ))}
      </div>
      <div className="unsupported-list">
        <span>Unsupported claims</span>
        <div>
          {lens.unsupportedClaims.map((claim) => (
            <code key={claim}>{labelKind(claim)}</code>
          ))}
        </div>
      </div>
    </aside>
  );
}

function ProofBlockView({ block }: { block: ProofBlock }) {
  const metrics = Object.entries(block.metrics ?? {});
  const unsupportedClaims = unsupportedClaimsFromPayload(block.payload);
  return (
    <section className={`proof-block ${block.source_kind}`}>
      <div className="proof-block-heading">
        <span className={`truth-dot ${block.source_kind}`} />
        <div>
          <p>{block.kind}</p>
          <h3>{block.title}</h3>
        </div>
      </div>
      <p className="proof-block-summary">{block.summary}</p>
      <dl className="truth-grid proof-block-truth">
        <div>
          <dt>Source</dt>
          <dd>{block.source_kind}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{block.confidence}</dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd>{block.redaction_state}</dd>
        </div>
      </dl>
      {metrics.length > 0 && (
        <div className="proof-block-metrics" aria-label={`${block.title} metrics`}>
          {metrics.map(([key, value]) => (
            <span key={key}>
              <strong>{formatMetricValue(value)}</strong>
              {labelKind(key)}
            </span>
          ))}
        </div>
      )}
      {(block.claims?.length ?? 0) > 0 && (
        <ul className="proof-claims">
          {block.claims?.map((claim) => (
            <li key={claim}>{claim}</li>
          ))}
        </ul>
      )}
      {unsupportedClaims.length > 0 && (
        <div className="unsupported-list proof-unsupported">
          <span>Unsupported claims</span>
          <div>
            {unsupportedClaims.map((claim) => (
              <code key={claim}>{labelKind(claim)}</code>
            ))}
          </div>
        </div>
      )}
      {block.evidence_refs.length > 0 && (
        <div className="evidence-list proof-evidence">
          <span>Evidence refs</span>
          {block.evidence_refs.map((ref) => (
            <code key={ref}>{ref}</code>
          ))}
        </div>
      )}
    </section>
  );
}

function IconButton({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`icon-button ${active ? "active" : ""}`} onClick={onClick} aria-label={label} title={label}>
      {icon}
    </button>
  );
}

function highlightedIds(nodes: PositionedNode[], focus: FocusFilter): Set<string> {
  if (focus === "all") return new Set(nodes.map((node) => node.id));
  if (focus === "cache") return new Set(nodes.filter((node) => node.kind === "cache_event").map((node) => node.id));
  if (focus === "failures") return new Set(nodes.filter((node) => node.kind === "failure").map((node) => node.id));
  if (focus === "remote") {
    const remoteNodes = nodes.filter((node) =>
      ["remote_execution_config", "worker_readiness"].includes(node.kind),
    );
    return new Set((remoteNodes.length ? remoteNodes : nodes).map((node) => node.id));
  }
  return new Set(nodes.filter((node) => node.source_kind === "derived_v1").map((node) => node.id));
}

function remoteLensModel(projection: ActionGraphProjection, packet: ProofPacket) {
  const remoteBlock = packet.blocks.find((block) => block.id === "remote_execution");
  const workerBlock = packet.blocks.find((block) => block.title === "Worker Readiness Boundary");
  const remoteMetrics = remoteBlock?.metrics ?? {};
  const remoteInvocations = numberMetric(remoteMetrics.remote_executor_invocations);
  const remoteEndpoints = numberMetric(remoteMetrics.remote_executor_endpoints);
  const workerPayload = payloadRecord(workerBlock?.payload);
  const workerStatus = stringValue(workerPayload?.status) ?? "not recorded";
  const sourceKind = workerBlock?.source_kind ?? remoteBlock?.source_kind ?? "future";
  const confidence = workerBlock?.confidence ?? remoteBlock?.confidence ?? "unknown";
  const modeLabel =
    remoteBlock?.summary ??
    (remoteInvocations > 0
      ? "Remote execution boundary recorded in proof packet."
      : "No remote execution boundary in proof packet.");
  const statusLabel =
    workerBlock?.summary ??
    (workerStatus === "worker_endpoints_ready"
      ? "Worker readiness boundary recorded in proof packet."
      : remoteBlock?.summary ?? "Remote boundary evidence not recorded.");
  const unsupportedClaims = dedupe([
    ...unsupportedClaimsFromPayload(remoteBlock?.payload),
    ...unsupportedClaimsFromPayload(workerBlock?.payload),
  ]);
  const boundaries = [remoteBlock, workerBlock]
    .filter((block): block is ProofBlock => Boolean(block))
    .map((block) => ({
      title: block.title,
      kind: block.kind,
      summary: block.summary,
      confidence: block.confidence,
      sourceKind: block.source_kind,
    }));

  return {
    modeLabel,
    statusLabel,
    sourceKind,
    confidence,
    unsupportedClaims,
    boundaries,
    metrics: [
      { label: "remote invocations", value: formatMetricValue(remoteInvocations) },
      { label: "endpoints", value: formatMetricValue(remoteEndpoints) },
      { label: "worker gate", value: labelKind(workerStatus) },
      {
        label: "worker identity",
        value: formatMetricValue(remoteMetrics.worker_identity_observed ?? false),
      },
      {
        label: "scheduler assignment",
        value: formatMetricValue(remoteMetrics.scheduler_assignment_observed ?? false),
      },
      { label: "queue time", value: formatMetricValue(remoteMetrics.queue_time_observed ?? false) },
    ],
  };
}

function unsupportedClaimsFromPayload(payload: unknown): string[] {
  const record = payloadRecord(payload);
  const claims = record?.unsupported_claims;
  if (!Array.isArray(claims)) return [];
  return claims.filter((claim): claim is string => typeof claim === "string");
}

function payloadRecord(payload: unknown): Record<string, unknown> | null {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) return null;
  return payload as Record<string, unknown>;
}

function numberMetric(value: ProofMetricValue | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function dedupe(values: string[]): string[] {
  return values.filter((value, index) => values.indexOf(value) === index);
}

function labelKind(kind: string) {
  return kind.replace(/_/g, " ");
}

function formatMetricValue(value: ProofMetricValue): string {
  if (value === null) return "n/a";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") {
    if (Number.isFinite(value) && value > 0 && value < 1) {
      return `${Math.round(value * 100)}%`;
    }
    return String(value);
  }
  return value;
}

function laneIndex(kind: string): number {
  return [
    "run",
    "invocation",
    "target",
    "action",
    "remote_execution_config",
    "worker_readiness",
    "cache_event",
    "failure",
    "artifact",
  ].indexOf(kind);
}

function centerTransform(svg: SVGSVGElement): ZoomTransform {
  const box = svg.getBoundingClientRect();
  const scale = box.width < 720 ? 0.44 : 0.95;
  return zoomIdentity.translate(box.width / 2, box.height / 2).scale(scale);
}
