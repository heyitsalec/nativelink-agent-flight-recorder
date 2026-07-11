export type SourceKind =
  | "collectable_v1"
  | "derived_v1"
  | "simulated_v1"
  | "future"
  | "unknown";

export type Confidence = "high" | "medium" | "low" | "unknown";
export type RedactionState = "safe" | "redacted" | "blocked" | "unknown";

export type TruthLabels = {
  source_kind: SourceKind;
  confidence: Confidence;
  evidence_refs: string[];
  redaction_state: RedactionState;
};

export type ProjectionNode = TruthLabels & {
  id: string;
  kind: string;
  label: string;
  status?: string | number | null;
  payload?: Record<string, unknown>;
};

export type ProjectionEdge = TruthLabels & {
  id: string;
  from: string;
  to: string;
  kind: string;
  payload?: unknown;
};

export type ActionGraphProjection = {
  schema_version: 1;
  projection_kind: "action_graph";
  generated_at: string;
  run_group: string;
  summary: Record<string, unknown>;
  nodes: ProjectionNode[];
  edges: ProjectionEdge[];
};

export type ProofMetricValue = string | number | boolean | null;

export type ProofBlock = TruthLabels & {
  id: string;
  kind: string;
  title: string;
  summary: string;
  claims?: string[];
  metrics?: Record<string, ProofMetricValue>;
  payload?: unknown;
};

export type ProofPacket = {
  schema_version: 1;
  projection_kind: "proof_packet";
  generated_at: string;
  run_group: string;
  summary: Record<string, unknown>;
  blocks: ProofBlock[];
};

export type PositionedNode = ProjectionNode & {
  x: number;
  y: number;
  radius: number;
};

export type PositionedEdge = ProjectionEdge & {
  source: PositionedNode;
  target: PositionedNode;
};

export type CanvasMode = "graph" | "runway" | "proof" | "remote" | "compare" | "replay";
export type FocusFilter = "all" | "cache" | "failures" | "derived" | "remote" | "agent";

export type CompareDimension = TruthLabels & {
  id: string;
  title: string;
  summary: string;
  left: Record<string, unknown>;
  right: Record<string, unknown>;
  delta: Record<string, unknown>;
  claims: string[];
};

export type CompareProjection = TruthLabels & {
  schema_version: 1;
  projection_kind: "compare";
  generated_at: string;
  left_run_group: string;
  right_run_group: string;
  summary: Record<string, unknown>;
  dimensions: CompareDimension[];
};

/* ── Timeline projection (contracts/timeline_projection.v1.json) ──────────
 * Mirrors the KNOWN fields of the additive contract; unknown fields are
 * permitted on the wire and simply ignored by these types (tolerant decode).
 */

export type TimelineEventKind = "run" | "verdict" | "receipt";

export type TimelineEvent = TruthLabels & {
  ts: string;
  kind: TimelineEventKind;
  label: string;
  /** Evidence database the event was read from. */
  source: string;
  /** Chronological index assigned by the projector (chapters reference it). */
  index: number;
  detail: Record<string, unknown>;
};

export type TimelineChapter = TruthLabels & {
  kind: "repair_loop";
  label: string;
  start_ts: string;
  /** null while the loop is open (no recorded green close). */
  end_ts: string | null;
  open: boolean;
  /** TimelineEvent.index values belonging to this chapter. */
  event_indexes: number[];
};

export type TimelineProjection = TruthLabels & {
  schema_version: 1;
  projection_kind: "timeline";
  generated_at: string;
  sources: string[];
  span: { start: string | null; end: string | null };
  summary: Record<string, unknown>;
  events: TimelineEvent[];
  chapters: TimelineChapter[];
};
