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

export type CanvasMode = "graph" | "runway" | "proof" | "remote";
export type FocusFilter = "all" | "cache" | "failures" | "derived" | "remote" | "agent";
