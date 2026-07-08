import { useState } from "react";
import { Copy, GitCompare, Maximize2, Network, ReceiptText, ShieldCheck, X } from "lucide-react";
import {
  formatMetricValue,
  labelKind,
  type RemoteLensModel,
  unsupportedClaimsFromPayload,
} from "../pageModel";
import {
  agentReceiptModel,
  provenanceSide,
  truncateHash,
  type AgentReceiptModel,
  type ProvenanceBadge as ProvenanceBadgeModel,
  type ProvenanceBlockSummary,
} from "../receiptModel";
import type {
  CompareProjection,
  Confidence,
  PositionedNode,
  ProofBlock,
  ProofMetricValue,
  SourceKind,
} from "../types";
import type { ComponentInstance } from "../view/types";
import { useViewComponent, useViewContext } from "../view/ViewContext";
import { stringProp } from "./shared/props";
import {
  ConfidenceMeter,
  ProvenanceBadge,
  RedactionChip,
  SourceGlyph,
  StatusGlyph,
  UnsupportedClaimChip,
} from "./shared/truth";

export function EvidenceInspectorPanel(_instance: ComponentInstance) {
  const { graph, route, routeActions } = useViewContext();
  const selectedNode = graph.nodes.find((node) => node.id === route.selectedId) ?? null;
  if (!selectedNode) return null;

  return (
    <Inspector node={selectedNode} onClose={() => routeActions.setSelectedId(null)} />
  );
}

function failureMessage(node: PositionedNode): string | null {
  if (node.kind !== "failure") return null;
  const payloadMessage = node.payload?.message;
  if (typeof payloadMessage === "string" && payloadMessage.trim()) {
    return payloadMessage.trim();
  }
  if (typeof node.status === "string" && node.status.trim()) {
    return node.status.trim();
  }
  return node.label.trim() || null;
}

export function ProvenanceChip({ badge }: { badge: ProvenanceBadgeModel }) {
  // Delegates to the P2 truth primitive so provenance reuses the source-kind
  // shape families (verified→circle, asserted→diamond, stub→triangle).
  return <ProvenanceBadge badge={badge} />;
}

function CopyHash({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="receipt-hash">
      <span className="receipt-hash-label">{label}</span>
      <code title={value}>{truncateHash(value)}</code>
      <button
        className="receipt-hash-copy"
        aria-label={`Copy ${label}`}
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1400);
          });
        }}
      >
        {copied ? "copied" : <Copy size={12} />}
      </button>
    </div>
  );
}

function ReceiptDetailPane({ receipt }: { receipt: AgentReceiptModel }) {
  const fields: { label: string; value: string | null }[] = [
    { label: "Model", value: receipt.model },
    { label: "Session", value: receipt.sessionId },
    { label: "CLI version", value: receipt.cliVersion },
    { label: "Captured at", value: receipt.capturedAt },
  ];
  const present = fields.filter((field) => field.value !== null);

  return (
    <section className="receipt-pane" aria-label="agent receipt" data-testid="receipt-detail-pane">
      <div className="receipt-pane-heading">
        <ReceiptText size={15} />
        <span>Agent receipt</span>
        <ProvenanceChip badge={receipt.badge} />
      </div>
      <p className="receipt-pane-hint">{receipt.badge.hint}</p>
      {present.length > 0 && (
        <dl className="truth-grid receipt-grid">
          {present.map((field) => (
            <div key={field.label}>
              <dt>{field.label}</dt>
              <dd>{field.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {receipt.usage.length > 0 && (
        <div className="receipt-usage lens-metric-strip" aria-label="receipt token usage">
          {receipt.usage.map((entry) => (
            <span key={entry.label}>
              <strong>{entry.value}</strong>
              {entry.label}
            </span>
          ))}
        </div>
      )}
      {receipt.hashes.length > 0 && (
        <div className="receipt-hashes" aria-label="receipt hashes">
          {receipt.hashes.map((hash) => (
            <CopyHash key={hash.label} label={hash.label} value={hash.value} />
          ))}
        </div>
      )}
    </section>
  );
}

function Inspector({ node, onClose }: { node: PositionedNode; onClose: () => void }) {
  const message = failureMessage(node);
  const receipt = node.kind === "agent" ? agentReceiptModel(node.payload) : null;

  return (
    <aside
      className={`inspector ${node.kind === "failure" ? "inspector--failure" : ""}`}
      aria-label="selected evidence"
    >
      <button className="close-button" onClick={onClose} aria-label="Close inspector">
        <Maximize2 size={16} />
      </button>
      <div className="inspector-heading">
        <SourceGlyph kind={node.source_kind} size={11} />
        <p>{labelKind(node.kind)}</p>
        <h2>{node.label}</h2>
      </div>
      {receipt && <ReceiptDetailPane receipt={receipt} />}
      {message && (
        <section className="failure-message-panel" aria-label="failure message">
          <span className="failure-message-label">Failure message</span>
          <p className="failure-message-body">{message}</p>
        </section>
      )}
      <dl className="truth-grid">
        <div>
          <dt>Source</dt>
          <dd className="truth-value">
            <SourceGlyph kind={node.source_kind} size={11} />
            <span>{node.source_kind}</span>
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd className="truth-value">
            <ConfidenceMeter confidence={node.confidence} />
            <span>{node.confidence}</span>
          </dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd className="truth-value">
            <RedactionChip state={node.redaction_state} />
          </dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd className="truth-value">
            <StatusGlyph status={node.status} />
          </dd>
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
    <aside className="proof-drawer lens-panel lens-panel--proof" aria-label="proof packet">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close proof drawer"
      >
        <X size={16} />
      </button>
      <div className="proof-drawer-heading lens-heading">
        <ShieldCheck size={18} />
        <p>Proof Packet</p>
        <h2>{packet.run_group}</h2>
        <span className="lens-meta">
          {packet.blocks.length} block{packet.blocks.length === 1 ? "" : "s"} · derived_v1 summary
        </span>
      </div>
      <div className="proof-summary lens-metric-strip" aria-label="proof summary">
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
    <section className={`proof-block lens-block ${block.source_kind}`}>
      <div className="proof-block-heading lens-block-heading">
        <SourceGlyph kind={block.source_kind} size={11} />
        <div>
          <p>{block.kind}</p>
          <h3>{block.title}</h3>
        </div>
      </div>
      <p className="proof-block-summary">{block.summary}</p>
      <dl className="truth-grid proof-block-truth">
        <div>
          <dt>Source</dt>
          <dd className="truth-value">
            <SourceGlyph kind={block.source_kind} size={11} />
            <span>{block.source_kind}</span>
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd className="truth-value">
            <ConfidenceMeter confidence={block.confidence} />
            <span>{block.confidence}</span>
          </dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd className="truth-value">
            <RedactionChip state={block.redaction_state} />
          </dd>
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
          <span>Unsupported claims — named, not hidden</span>
          <div>
            {unsupportedClaims.map((claim) => (
              <UnsupportedClaimChip key={claim} claim={labelKind(claim)} />
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
    <aside className="remote-lens lens-panel lens-panel--remote" aria-label="remote execution boundary">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close remote boundary"
      >
        <X size={16} />
      </button>
      <div className="remote-lens-heading lens-heading">
        <Network size={18} />
        <p>Remote Boundary</p>
        <h2>{lens.statusLabel}</h2>
        <span className="lens-meta">
          {lens.boundaries.length} boundary{lens.boundaries.length === 1 ? "" : "ies"} · projection join
        </span>
      </div>
      <div className="remote-state-line lens-state-line">
        <SourceGlyph kind={lens.sourceKind as SourceKind} size={11} />
        <strong>{lens.modeLabel}</strong>
        <span className="truth-value">
          <ConfidenceMeter confidence={lens.confidence as Confidence} />
          {lens.confidence}
        </span>
      </div>
      <div className="remote-metrics lens-metric-strip">
        {lens.metrics.map((metric) => (
          <span key={metric.label}>
            <strong>{metric.value}</strong>
            {metric.label}
          </span>
        ))}
      </div>
      <div className="remote-boundaries lens-boundary-list">
        {lens.boundaries.map((boundary) => (
          <section key={boundary.title} className={`remote-boundary lens-boundary ${boundary.sourceKind}`}>
            <div>
              <p>{boundary.kind}</p>
              <h3>{boundary.title}</h3>
            </div>
            <span className="truth-value">
              <ConfidenceMeter confidence={boundary.confidence as Confidence} />
              {boundary.confidence}
            </span>
            <p>{boundary.summary}</p>
          </section>
        ))}
      </div>
      <div className="unsupported-list">
        <span>Unsupported claims — named, not hidden</span>
        <div>
          {lens.unsupportedClaims.map((claim) => (
            <UnsupportedClaimChip key={claim} claim={labelKind(claim)} />
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
    <aside className="compare-lens lens-panel lens-panel--compare" aria-label="multi-run compare">
      <button
        className="close-button"
        onClick={() => routeActions.setMode("graph")}
        aria-label="Close compare lens"
      >
        <X size={16} />
      </button>
      <div className="compare-lens-heading lens-heading">
        <GitCompare size={18} />
        <p>Multi-run Compare</p>
        {projection ? (
          <>
            <h2 className="compare-run-title">Run group deltas</h2>
            <div className="compare-run-pills" aria-label="compared run groups">
              <span className="compare-run-pill compare-run-pill--left">{projection.left_run_group}</span>
              <span className="compare-run-pill compare-run-pill--vs">vs</span>
              <span className="compare-run-pill compare-run-pill--right">{projection.right_run_group}</span>
            </div>
          </>
        ) : (
          <h2>No compare projection loaded</h2>
        )}
      </div>
      {!projection ? (
        <p className="compare-empty lens-empty">
          Place <code>compare-projection.json</code> under <code>public/projections/</code> to enable
          derived proof-packet diffs.
        </p>
      ) : (
        <>
          <div className="compare-state-line lens-state-line">
            <SourceGlyph kind={projection.source_kind} size={11} />
            <strong>{projection.source_kind}</strong>
            <span className="truth-value">
              <ConfidenceMeter confidence={projection.confidence} />
              {projection.confidence}
            </span>
            <span className="compare-dimension-count">
              {projection.dimensions.length} dimension{projection.dimensions.length === 1 ? "" : "s"}
            </span>
          </div>
          <div className="compare-dimension-list">
            {projection.dimensions.map((dimension) => (
              <CompareDimensionView
                key={dimension.id}
                dimension={dimension}
                leftRunGroup={projection.left_run_group}
                rightRunGroup={projection.right_run_group}
              />
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
  if (!dimension || !projection) return null;
  return (
    <CompareDimensionView
      dimension={dimension}
      leftRunGroup={projection.left_run_group}
      rightRunGroup={projection.right_run_group}
    />
  );
}

function ProvenanceBlockCard({ block }: { block: ProvenanceBlockSummary }) {
  return (
    <article className={`provenance-block ${block.sourceKind}`}>
      <div className="provenance-block-heading">
        <SourceGlyph kind={block.sourceKind as SourceKind} size={11} />
        {block.badge ? (
          <ProvenanceChip badge={block.badge} />
        ) : (
          <span className="provenance-chip provenance--asserted">no provenance class</span>
        )}
      </div>
      {block.title && <h4>{block.title}</h4>}
      <dl className="provenance-block-facts">
        {block.model && (
          <div>
            <dt>model</dt>
            <dd>{block.model}</dd>
          </div>
        )}
        {block.sessionId && (
          <div>
            <dt>session</dt>
            <dd>
              <code>{block.sessionId}</code>
            </dd>
          </div>
        )}
        {block.promptSha256Prefix && (
          <div>
            <dt>prompt sha256</dt>
            <dd>
              <code>{block.promptSha256Prefix}…</code>
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}

function ProvenanceSideColumn({
  title,
  side,
}: {
  title: string;
  side: ReturnType<typeof provenanceSide>;
}) {
  return (
    <div className="provenance-side">
      <span className="provenance-side-title">{title}</span>
      {side.blocks.length === 0 ? (
        <p className="provenance-side-empty">
          {side.present
            ? "Provenance blocks recorded without receipt summaries."
            : "No agent provenance block recorded."}
        </p>
      ) : (
        side.blocks.map((block) => <ProvenanceBlockCard key={block.id} block={block} />)
      )}
    </div>
  );
}

function AgentProvenanceCompare({
  dimension,
  leftRunGroup,
  rightRunGroup,
}: {
  dimension: CompareProjection["dimensions"][number];
  leftRunGroup: string;
  rightRunGroup: string;
}) {
  const left = provenanceSide(dimension.left);
  const right = provenanceSide(dimension.right);
  return (
    <div className="compare-provenance" data-testid="compare-agent-provenance">
      <div className="compare-provenance-grid">
        <ProvenanceSideColumn title={leftRunGroup} side={left} />
        <ProvenanceSideColumn title={rightRunGroup} side={right} />
      </div>
    </div>
  );
}

function CompareDimensionView({
  dimension,
  leftRunGroup,
  rightRunGroup,
}: {
  dimension: CompareProjection["dimensions"][number];
  leftRunGroup?: string;
  rightRunGroup?: string;
}) {
  const deltaEntries = Object.entries(dimension.delta ?? {}).filter(
    ([, value]) => value !== null && typeof value !== "object",
  );
  return (
    <section className={`compare-dimension ${dimension.source_kind}`}>
      <div className="compare-dimension-heading">
        <SourceGlyph kind={dimension.source_kind} size={11} />
        <div>
          <p>{dimension.id}</p>
          <h3>{dimension.title}</h3>
        </div>
      </div>
      <p className="compare-dimension-summary">{dimension.summary}</p>
      {dimension.id === "agent_provenance" && (
        <AgentProvenanceCompare
          dimension={dimension}
          leftRunGroup={leftRunGroup ?? "left run group"}
          rightRunGroup={rightRunGroup ?? "right run group"}
        />
      )}
      <dl className="truth-grid compare-dimension-truth">
        <div>
          <dt>Source</dt>
          <dd className="truth-value">
            <SourceGlyph kind={dimension.source_kind} size={11} />
            <span>{dimension.source_kind}</span>
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd className="truth-value">
            <ConfidenceMeter confidence={dimension.confidence} />
            <span>{dimension.confidence}</span>
          </dd>
        </div>
        <div>
          <dt>Redaction</dt>
          <dd className="truth-value">
            <RedactionChip state={dimension.redaction_state} />
          </dd>
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
