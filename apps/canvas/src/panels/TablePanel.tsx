import { GitCompare, Maximize2, Network, ShieldCheck, X } from "lucide-react";
import {
  formatMetricValue,
  labelKind,
  type RemoteLensModel,
  unsupportedClaimsFromPayload,
} from "../pageModel";
import type { CompareProjection, PositionedNode, ProofBlock, ProofMetricValue } from "../types";
import type { ComponentInstance } from "../view/types";
import { useViewComponent, useViewContext } from "../view/ViewContext";
import { stringProp } from "./shared/props";

export function EvidenceInspectorPanel(_instance: ComponentInstance) {
  const { graph, route, routeActions } = useViewContext();
  const selectedNode = graph.nodes.find((node) => node.id === route.selectedId) ?? null;
  if (!selectedNode) return null;

  return (
    <Inspector node={selectedNode} onClose={() => routeActions.setSelectedId(null)} />
  );
}

function Inspector({ node, onClose }: { node: PositionedNode; onClose: () => void }) {
  return (
    <aside className="inspector" aria-label="selected evidence">
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

export function ProofDrawerPanel(_instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const packet = bindings.proofPacket;
  const summaryEntries = Object.entries(packet.summary).filter(
    ([, value]) => typeof value === "number" || typeof value === "string",
  );

  return (
    <aside className="proof-drawer" aria-label="proof packet">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close proof drawer"
      >
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

export function ProofBlockCardPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const blockId = stringProp(instance.props, "block_id");
  const block = bindings.proofPacket.blocks.find((entry) => entry.id === blockId);
  if (!block) return null;
  return <ProofBlockView block={block} />;
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

export function RemoteBoundaryLensPanel(_instance: ComponentInstance) {
  const { routeActions } = useViewContext();
  const lens = useViewComponent(_instance) as RemoteLensModel | null;
  if (!lens) return null;

  return (
    <aside className="remote-lens" aria-label="remote execution boundary">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close remote boundary"
      >
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

export function CompareLensPanel(instance: ComponentInstance) {
  const { bindings, routeActions } = useViewContext();
  const projection = bindings.compareProjection;
  void stringProp(instance.props, "empty_state_path_hint");

  return (
    <aside className="compare-lens" aria-label="multi-run compare">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close compare lens"
      >
        <X size={16} />
      </button>
      <div className="compare-lens-heading">
        <GitCompare size={18} />
        <p>Multi-run Compare</p>
        <h2>
          {projection
            ? `${projection.left_run_group} vs ${projection.right_run_group}`
            : "No compare projection loaded"}
        </h2>
      </div>
      {!projection ? (
        <p className="compare-empty">
          Place <code>compare-projection.json</code> under <code>public/projections/</code> to enable
          derived proof-packet diffs.
        </p>
      ) : (
        <>
          <div className="compare-state-line">
            <span className={`truth-dot ${projection.source_kind}`} />
            <strong>{projection.source_kind}</strong>
            <span>{projection.confidence}</span>
          </div>
          <div className="compare-dimension-list">
            {projection.dimensions.map((dimension) => (
              <CompareDimensionView key={dimension.id} dimension={dimension} />
            ))}
          </div>
        </>
      )}
    </aside>
  );
}

export function CompareDimensionCardPanel(instance: ComponentInstance) {
  const { bindings } = useViewContext();
  const dimensionId = stringProp(instance.props, "dimension_id");
  const projection = bindings.compareProjection;
  const dimension = projection?.dimensions.find((entry) => entry.id === dimensionId);
  if (!dimension) return null;
  return <CompareDimensionView dimension={dimension} />;
}

function CompareDimensionView({ dimension }: { dimension: CompareProjection["dimensions"][number] }) {
  const deltaEntries = Object.entries(dimension.delta ?? {}).filter(
    ([, value]) => value !== null && typeof value !== "object",
  );
  return (
    <section className={`compare-dimension ${dimension.source_kind}`}>
      <div className="compare-dimension-heading">
        <span className={`truth-dot ${dimension.source_kind}`} />
        <div>
          <p>{dimension.id}</p>
          <h3>{dimension.title}</h3>
        </div>
      </div>
      <p className="compare-dimension-summary">{dimension.summary}</p>
      <dl className="truth-grid compare-dimension-truth">
        <div>
          <dt>Source</dt>
          <dd>{dimension.source_kind}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{dimension.confidence}</dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd>{dimension.redaction_state}</dd>
        </div>
      </dl>
      {deltaEntries.length > 0 && (
        <div className="compare-delta-metrics" aria-label={`${dimension.title} delta`}>
          {deltaEntries.map(([key, value]) => (
            <span key={key}>
              <strong>{formatMetricValue(value as ProofMetricValue)}</strong>
              {labelKind(key)}
            </span>
          ))}
        </div>
      )}
      {(dimension.claims?.length ?? 0) > 0 && (
        <ul className="proof-claims">
          {dimension.claims.map((claim) => (
            <li key={claim}>{claim}</li>
          ))}
        </ul>
      )}
      {dimension.evidence_refs.length > 0 && (
        <div className="evidence-list proof-evidence">
          <span>Evidence refs</span>
          {dimension.evidence_refs.map((ref) => (
            <code key={ref}>{ref}</code>
          ))}
        </div>
      )}
    </section>
  );
}

export type TablePanelKind =
  | "evidence_inspector"
  | "proof_drawer"
  | "proof_block_card"
  | "remote_boundary_lens"
  | "compare_lens"
  | "compare_dimension_card";

export const TABLE_PANELS: Record<TablePanelKind, (instance: ComponentInstance) => React.ReactNode> = {
  evidence_inspector: EvidenceInspectorPanel,
  proof_drawer: ProofDrawerPanel,
  proof_block_card: ProofBlockCardPanel,
  remote_boundary_lens: RemoteBoundaryLensPanel,
  compare_lens: CompareLensPanel,
  compare_dimension_card: CompareDimensionCardPanel,
};
