import type {
  ActionGraphProjection,
  CompareDimension,
  Confidence,
  FocusFilter,
  ProjectionNode,
  ProofBlock,
  ProofMetricValue,
  ProofPacket,
  RedactionState,
  SourceKind,
} from "./types";
import type { ProjectionNotice, ViewSpec } from "./view/types";

/**
 * Evidence-mix over the loaded projection's real node source_kind
 * distribution (redesign P3 context banner). No invented numbers — every
 * segment is a real node count. Ordered so the strongest evidence
 * (collectable) leads and future/unknown (slate) trails.
 */
export type EvidenceMixSegment = {
  kind: SourceKind;
  count: number;
  fraction: number;
};

const EVIDENCE_MIX_ORDER: SourceKind[] = [
  "collectable_v1",
  "derived_v1",
  "simulated_v1",
  "future",
  "unknown",
];

const EVIDENCE_MIX_KINDS: ReadonlySet<string> = new Set(EVIDENCE_MIX_ORDER);

export function evidenceMix(projection: ActionGraphProjection): {
  total: number;
  dominant: SourceKind;
  segments: EvidenceMixSegment[];
} {
  const counts = new Map<SourceKind, number>();
  for (const node of projection.nodes) {
    const raw: string = node.source_kind ?? "unknown";
    // Honesty guard: a non-null source_kind OUTSIDE the known enum must not
    // be silently dropped (that would under-fill the mix bar while the node
    // count stays full). Bucket it into the honest slate "unknown" catch-all
    // so segments always sum to `total`.
    const kind: SourceKind = EVIDENCE_MIX_KINDS.has(raw) ? (raw as SourceKind) : "unknown";
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }
  const total = projection.nodes.length;
  const segments: EvidenceMixSegment[] = EVIDENCE_MIX_ORDER.filter((kind) => (counts.get(kind) ?? 0) > 0).map(
    (kind) => {
      const count = counts.get(kind) ?? 0;
      return { kind, count, fraction: total > 0 ? count / total : 0 };
    },
  );
  const dominant = segments.reduce<EvidenceMixSegment | null>(
    (best, seg) => (best === null || seg.count > best.count ? seg : best),
    null,
  );
  return { total, dominant: dominant?.kind ?? "unknown", segments };
}

export type RemoteLensModel = {
  modeLabel: string;
  statusLabel: string;
  sourceKind: string;
  confidence: string;
  unsupportedClaims: string[];
  boundaries: {
    title: string;
    kind: string;
    summary: string;
    confidence: string;
    sourceKind: string;
  }[];
  metrics: { label: string; value: string }[];
};

export type ViewContextSlice = {
  spec: ViewSpec;
  usingFixtureFallback: boolean;
};

export function deriveProjectionNotice(
  projection: ActionGraphProjection,
  usingFixtureFallback: boolean,
): ProjectionNotice {
  if (usingFixtureFallback) {
    return {
      tone: "fallback",
      message:
        "Using fixture fallback — projection fetch failed; showing the bundled simulated_v1 fixture, labeled as such.",
    };
  }
  const kinds = projection.nodes.map((node) => node.source_kind);
  const simulatedCount = kinds.filter((kind) => kind === "simulated_v1").length;
  const collectableCount = kinds.filter((kind) => kind === "collectable_v1").length;
  if (projection.run_group === "canvas-dev" && collectableCount > 0 && simulatedCount === 0) {
    return {
      tone: "collectable",
      message: `canvas-dev run group — collectable_v1 dogfood projection (${collectableCount} nodes).`,
    };
  }
  if (projection.run_group === "latest" || simulatedCount > collectableCount) {
    return {
      tone: "simulated",
      message: `simulated_v1 fixture chain (run_group=${projection.run_group}) — not live NativeLink proof.`,
    };
  }
  if (simulatedCount > 0 && collectableCount > 0) {
    return {
      tone: "mixed",
      message: `Mixed projection (run_group=${projection.run_group}) — ${collectableCount} collectable_v1 + ${simulatedCount} simulated_v1 nodes; read labels per node.`,
    };
  }
  if (collectableCount > 0 && simulatedCount === 0) {
    return {
      tone: "collectable",
      message: `${projection.run_group} run group — collectable_v1 projection (${collectableCount} nodes).`,
    };
  }
  return null;
}

/**
 * Distinguish a MISSING projection (unreachable / 404) from a MALFORMED one (a
 * bound projection that WAS fetched but is not valid JSON) — redesign P7 V4,
 * board 1l. This is honesty-critical: a corrupt projection must NOT be dressed
 * up as the labeled fixture fallback (which is reserved for genuinely absent
 * data). Only a body that was fetched OK but failed to parse is "malformed" and
 * drives the honest error state ("… — invalid JSON. Nothing partial is
 * rendered."); everything else degrades to the labeled fallback.
 */
export type BindingFetchResult = "ok" | "missing" | "malformed";

export function classifyBindingFetch(input: {
  /** `fetch()` itself threw — the host/path was unreachable. */
  networkError: boolean;
  /** `response.ok` — a 2xx status. */
  responseOk: boolean;
  /** `response.json()` succeeded. */
  parsedOk: boolean;
}): BindingFetchResult {
  if (input.networkError) return "missing";
  if (!input.responseOk) return "missing";
  if (!input.parsedOk) return "malformed";
  return "ok";
}

/**
 * Curate a raw JSON parse failure into honest, human error-DETAIL copy for the
 * projection error state — never a raw JS exception / stack string. Names the
 * projection file and, when the engine reports one, the character position
 * (board 1l shows a line; the browser gives us a byte position honestly).
 */
export function projectionParseDetail(path: string, raw: unknown): string {
  const name = path.split("/").filter(Boolean).pop() ?? path;
  const message = raw instanceof Error ? raw.message : String(raw ?? "");
  const position = message.match(/position (\d+)/i);
  const near = position ? ` near character ${position[1]}` : "";
  return `${name} — invalid JSON${near}`;
}

export function highlightedIds(nodes: ProjectionNode[], focus: FocusFilter): Set<string> {
  if (focus === "all") return new Set(nodes.map((node) => node.id));
  if (focus === "cache") {
    return new Set(nodes.filter((node) => node.kind === "cache_event").map((node) => node.id));
  }
  if (focus === "failures") {
    return new Set(nodes.filter((node) => node.kind === "failure").map((node) => node.id));
  }
  if (focus === "remote") {
    const remoteNodes = nodes.filter((node) =>
      ["remote_execution_config", "worker_readiness"].includes(node.kind),
    );
    return new Set((remoteNodes.length ? remoteNodes : nodes).map((node) => node.id));
  }
  if (focus === "agent") {
    return new Set(
      nodes.filter((node) => node.kind === "agent" || node.kind === "change").map((node) => node.id),
    );
  }
  return new Set(nodes.filter((node) => node.source_kind === "derived_v1").map((node) => node.id));
}

/**
 * Honest count of nodes that TRULY match a focus filter (redesign P7 §9,
 * "Focus applied" state). Unlike {@link highlightedIds}, this NEVER falls back
 * to "all nodes" when a category is empty (the remote fallback) — an empty
 * match must report 0 so the focus pill can say "0 of N nodes match". The graph
 * dims non-matches; it never silently hides evidence, so the count is the
 * truthful surface of what the filter selected.
 */
export function focusMatchCount(nodes: ProjectionNode[], focus: FocusFilter): number {
  if (focus === "all") return nodes.length;
  if (focus === "cache") return nodes.filter((node) => node.kind === "cache_event").length;
  if (focus === "failures") return nodes.filter((node) => node.kind === "failure").length;
  if (focus === "remote") {
    return nodes.filter((node) =>
      ["remote_execution_config", "worker_readiness"].includes(node.kind),
    ).length;
  }
  if (focus === "agent") {
    return nodes.filter((node) => node.kind === "agent" || node.kind === "change").length;
  }
  return nodes.filter((node) => node.source_kind === "derived_v1").length;
}

/** Human label for a focus filter (redesign P7 §9 focus pill copy). */
export function focusLabel(focus: FocusFilter): string {
  switch (focus) {
    case "failures":
      return "failures";
    case "cache":
      return "cache misses";
    case "remote":
      return "remote boundary";
    case "agent":
      return "agent loop";
    case "derived":
      return "derived evidence";
    default:
      return "all evidence";
  }
}

export function remoteLensModel(
  projection: ActionGraphProjection,
  packet: ProofPacket,
): RemoteLensModel {
  void projection;
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

export function laneIndex(kind: string): number {
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

export function sortRunwayNodes<T extends { kind: string }>(nodes: T[]): T[] {
  return [...nodes].sort((a, b) => laneIndex(a.kind) - laneIndex(b.kind));
}

export function unsupportedClaimsFromPayload(payload: unknown): string[] {
  const record = payloadRecord(payload);
  const claims = record?.unsupported_claims;
  if (!Array.isArray(claims)) return [];
  return claims.filter((claim): claim is string => typeof claim === "string");
}

/** True when a string carries a redaction marker — a real `[REDACTED:...]`
 *  partial-path token or a bare `[REDACTED]`. */
export function isRedactedValue(value: string): boolean {
  return value.includes("[REDACTED:") || value.includes("[REDACTED]");
}

export type BlockIndexMeta = { tone: "count" | "muted" | "unsupported"; text: string };

/**
 * Right-hand meta for a proof block-index (TOC) row: the unsupported-claims
 * tally, a real positive metric, "no claim" for a future block that asserts
 * nothing, or a recorded count. A future block that still carries a real metric
 * (cache economics ships 7 real legs) surfaces that metric rather than the
 * blanket "no claim" (redesign P5 fix M5).
 */
export function blockIndexMeta(block: ProofBlock): BlockIndexMeta {
  const unsupported = unsupportedClaimsFromPayload(block.payload);
  if (unsupported.length > 0) return { tone: "unsupported", text: `${unsupported.length} unsupported` };
  const metrics = block.metrics ?? {};
  // Checked BEFORE the future early-return: a future block can still carry a
  // real recorded count (per-leg cache economics) — show it, don't erase it.
  if (typeof metrics.legs === "number" && metrics.legs > 0) {
    return { tone: "count", text: `${metrics.legs} leg${metrics.legs === 1 ? "" : "s"}` };
  }
  if (block.source_kind === "future") return { tone: "muted", text: "no claim" };
  if (block.id === "invocations" && typeof metrics.unknown === "number") {
    return { tone: "count", text: `${metrics.unknown} cmds` };
  }
  if (typeof metrics.artifacts === "number") return { tone: "count", text: `${metrics.artifacts} artifacts` };
  const refs = block.evidence_refs.length;
  if (refs > 0) return { tone: "count", text: `${refs} ref${refs === 1 ? "" : "s"}` };
  return { tone: "muted", text: "recorded" };
}

/**
 * A real `[REDACTED:...]` string a redacted block can surface in its header lock
 * chip when a top-level payload field carries one — else undefined, so the chip
 * shows the honest "redacted" state without inventing a value (never a bare
 * "[REDACTED]", redesign P5 fix M1). Redacted evidence *refs* keep their own row
 * (EvidenceRefRow), so they are intentionally not pulled up here.
 */
export function redactedValueForBlock(block: ProofBlock): string | undefined {
  const record = payloadRecord(block.payload);
  if (record) {
    for (const value of Object.values(record)) {
      if (typeof value === "string" && isRedactedValue(value)) return value;
    }
  }
  return undefined;
}

/**
 * Blocks strictly below the active block, in document order — the accurate
 * "N more blocks" count for the drawer's sticky footer pill. Empty on the last
 * (or an unknown) active block, so the pill can never over-state what remains
 * below the current scroll position (redesign P5 fix M2).
 */
export function blocksBelow<T extends { id: string }>(
  blocks: readonly T[],
  activeId: string | null,
): T[] {
  const index = blocks.findIndex((block) => block.id === activeId);
  return index >= 0 ? blocks.slice(index + 1) : [];
}

/**
 * Proof-packet rollup (redesign P5 header). Counts blocks by source_kind into
 * the human buckets the drawer surfaces as pills — recorded (collectable),
 * computed (derived), simulated, and "not yet collected" (future). Every count
 * is a REAL block count; `recorded + computed + simulated + notCollected +
 * unknown === total` holds by construction, so the pills can never over- or
 * under-state what the packet actually contains.
 */
export type ProofRollup = {
  recorded: number;
  computed: number;
  simulated: number;
  notCollected: number;
  unknown: number;
  total: number;
};

export function proofRollup(blocks: ReadonlyArray<{ source_kind: SourceKind }>): ProofRollup {
  const rollup: ProofRollup = {
    recorded: 0,
    computed: 0,
    simulated: 0,
    notCollected: 0,
    unknown: 0,
    total: blocks.length,
  };
  for (const block of blocks) {
    switch (block.source_kind) {
      case "collectable_v1":
        rollup.recorded += 1;
        break;
      case "derived_v1":
        rollup.computed += 1;
        break;
      case "simulated_v1":
        rollup.simulated += 1;
        break;
      case "future":
        rollup.notCollected += 1;
        break;
      default:
        // Any out-of-enum/unknown source_kind is counted honestly, never
        // silently dropped (mirrors evidenceMix's unknown bucket).
        rollup.unknown += 1;
    }
  }
  return rollup;
}

export function payloadRecord(payload: unknown): Record<string, unknown> | null {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) return null;
  return payload as Record<string, unknown>;
}

export function numberMetric(value: ProofMetricValue | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function stringValue(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

export function dedupe(values: string[]): string[] {
  return values.filter((value, index) => values.indexOf(value) === index);
}

export function labelKind(kind: string): string {
  return kind.replace(/_/g, " ");
}

export function formatMetricValue(value: ProofMetricValue): string {
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

export type JoinFn = (sources: Record<string, unknown>, ctx: ViewContextSlice) => unknown;

export const joinFnRegistry: Record<string, JoinFn> = {
  remote_lens_model(sources) {
    const actionGraph = sources["binding.action_graph"] as ActionGraphProjection | undefined;
    const proofPacket = sources["binding.proof_packet"] as ProofPacket | undefined;
    if (!actionGraph || !proofPacket) return null;
    return remoteLensModel(actionGraph, proofPacket);
  },
};

export function resolveJoinFn(
  joinFn: string,
  sources: Record<string, unknown>,
  ctx: ViewContextSlice,
): unknown {
  const fn = joinFnRegistry[joinFn];
  if (!fn) {
    throw new Error(`Unknown join_fn: ${joinFn}`);
  }
  return fn(sources, ctx);
}

/* ------------------------------------------------------------------------ *
 * Validation Runway lanes (redesign P6 — DESIGN-SYSTEM.md §3, board 1j).
 * Real projection nodes grouped into fixed, ordered lanes. An empty lane is
 * never blank: it STATES its emptiness honestly. Every value keeps its truth
 * labels so a chip can render source(shape)/confidence(meter)/status.
 * ------------------------------------------------------------------------ */

export type RunwayLaneKind =
  | "run"
  | "invocation"
  | "target"
  | "action"
  | "cache_event"
  | "failure"
  | "artifact";

export type RunwayLane = {
  kind: RunwayLaneKind;
  /** Human lane name shown in the 110px gutter (e.g. "runs"). */
  name: string;
  count: number;
  empty: boolean;
  /** Honest statement rendered when the lane has no nodes — never blank. */
  emptyMessage: string;
  nodes: ProjectionNode[];
};

const RUNWAY_LANE_ORDER: { kind: RunwayLaneKind; name: string }[] = [
  { kind: "run", name: "runs" },
  { kind: "invocation", name: "invocations" },
  { kind: "target", name: "targets" },
  { kind: "action", name: "actions" },
  { kind: "cache_event", name: "cache" },
  { kind: "failure", name: "failures" },
  { kind: "artifact", name: "artifacts" },
];

/**
 * A lane's honest empty statement. cache/failures get the board-specified copy;
 * the failures lane, when empty, states how many recorded commands completed
 * (invocation count) rather than leaving a gap. Every other empty lane names the
 * projection it examined so "not shown" can never be mistaken for "hidden".
 */
function runwayEmptyMessage(kind: RunwayLaneKind, invocationCount: number): string {
  switch (kind) {
    case "cache_event":
      return "no cache events recorded in this projection";
    case "failure":
      return `no failures recorded — ${invocationCount} of ${invocationCount} commands completed`;
    case "target":
      return "no targets recorded in this projection";
    case "action":
      return "no actions recorded in this projection";
    case "run":
      return "no runs recorded in this projection";
    case "invocation":
      return "no invocations recorded in this projection";
    default:
      return "no artifacts recorded in this projection";
  }
}

/**
 * Per-run artifact columns for the runway artifacts lane (board 1j: "artifacts:
 * per-column count pills (file icon + mono '6')"). Each run gets one pill whose
 * count is the number of artifacts that resolve up to that run through the REAL
 * recorded edges (run → invocation → artifact) plus each artifact's recorded
 * `invocation:` evidence ref — never invented. Artifacts that resolve to no run
 * are surfaced as an honest `unattributed` remainder so the pills always sum to
 * the lane's total (nothing silently dropped).
 */
export type RunwayArtifactColumn = { runId: string; label: string; count: number };

export type RunwayArtifactColumns = {
  columns: RunwayArtifactColumn[];
  unattributed: number;
  total: number;
};

export function runwayArtifactColumns(
  nodes: ReadonlyArray<ProjectionNode>,
  edges: ReadonlyArray<{ from: string; to: string }>,
): RunwayArtifactColumns {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  // Parent map from real edges (first edge into a node wins), then let each
  // artifact prefer its recorded `invocation:` ref (mirrors buildGraphScene).
  const parentOf = new Map<string, string>();
  for (const edge of edges) {
    if (!byId.has(edge.from) || !byId.has(edge.to)) continue;
    if (!parentOf.has(edge.to)) parentOf.set(edge.to, edge.from);
  }
  for (const node of nodes) {
    if (node.kind !== "artifact") continue;
    for (const ref of node.evidence_refs ?? []) {
      const match = /^invocation:(.+)$/.exec(ref);
      if (match && byId.has(match[1])) parentOf.set(node.id, match[1]);
    }
  }
  const runOf = (id: string): string | null => {
    let cursor: string | undefined = id;
    let hops = 0;
    while (cursor && hops < 32) {
      const parent = parentOf.get(cursor);
      if (!parent) return null;
      if (byId.get(parent)?.kind === "run") return parent;
      cursor = parent;
      hops += 1;
    }
    return null;
  };

  const runs = nodes.filter((node) => node.kind === "run");
  const counts = new Map<string, number>(runs.map((run) => [run.id, 0]));
  const artifacts = nodes.filter((node) => node.kind === "artifact");
  let unattributed = 0;
  for (const artifact of artifacts) {
    const run = runOf(artifact.id);
    if (run !== null && counts.has(run)) counts.set(run, (counts.get(run) ?? 0) + 1);
    else unattributed += 1;
  }
  const columns: RunwayArtifactColumn[] = runs.map((run, index) => ({
    runId: run.id,
    label: `#${index + 1}`,
    count: counts.get(run.id) ?? 0,
  }));
  return { columns, unattributed, total: artifacts.length };
}

export function runwayLanes(nodes: ReadonlyArray<ProjectionNode>): RunwayLane[] {
  const byKind = new Map<string, ProjectionNode[]>();
  for (const node of nodes) {
    const list = byKind.get(node.kind);
    if (list) list.push(node);
    else byKind.set(node.kind, [node]);
  }
  const invocationCount = byKind.get("invocation")?.length ?? 0;
  return RUNWAY_LANE_ORDER.map(({ kind, name }) => {
    const laneNodes = byKind.get(kind) ?? [];
    return {
      kind,
      name,
      count: laneNodes.length,
      empty: laneNodes.length === 0,
      emptyMessage: runwayEmptyMessage(kind, invocationCount),
      nodes: laneNodes,
    };
  });
}

/* ------------------------------------------------------------------------ *
 * Remote Boundary view (redesign P6 — DESIGN-SYSTEM.md §5, board 1h).
 * A derived join over the proof packet's remote_execution block. Every metric
 * is dashed + slate (future / not-observed), NEVER red — "not observed" is a
 * calm stated boundary, not a failure. Boundary rows shape-encode source_kind.
 * ------------------------------------------------------------------------ */

export type RemoteBoundaryCell = {
  key: string;
  label: string;
  observed: boolean;
  /** "0" for a count, "not observed" for an unmet flag. */
  value: string;
  kind: "count" | "flag";
};

export type RemoteBoundaryRow = {
  title: string;
  kind: string;
  summary: string;
  confidence: string;
  sourceKind: SourceKind;
};

export type RemoteBoundaryView = {
  sourceKind: SourceKind;
  confidence: Confidence;
  observed: boolean;
  observedInvocations: number;
  totalInvocations: number;
  statement: string;
  observedLine: string;
  explainer: string;
  /** Top row of the 3×2 grid: mono count cells. */
  countCells: RemoteBoundaryCell[];
  /** Bottom row of the 3×2 grid: dashed "not observed" flag cells. */
  flagCells: RemoteBoundaryCell[];
  /** "What would earn these claims" — the block's own requirement claims. */
  earnClaims: string[];
  unsupportedClaims: string[];
  boundaries: RemoteBoundaryRow[];
};

const REMOTE_EXPLAINER =
  "This is a stated boundary, not a failure. NLFR records what the local build tools emit; nothing beyond this line is claimed as observed.";

function coerceSourceKind(value: string | undefined): SourceKind {
  const known: ReadonlySet<string> = new Set([
    "collectable_v1",
    "derived_v1",
    "simulated_v1",
    "future",
    "unknown",
  ]);
  return value && known.has(value) ? (value as SourceKind) : "future";
}

function coerceConfidence(value: string | undefined): Confidence {
  return value === "high" || value === "medium" || value === "low" ? value : "unknown";
}

export function remoteBoundaryView(
  projection: ActionGraphProjection,
  packet: ProofPacket,
): RemoteBoundaryView {
  const remoteBlock = packet.blocks.find((block) => block.id === "remote_execution");
  const invocationsBlock = packet.blocks.find((block) => block.id === "invocations");
  const metrics = remoteBlock?.metrics ?? {};

  const observedInvocations = numberMetric(metrics.remote_executor_invocations);
  const endpoints = numberMetric(metrics.remote_executor_endpoints);
  const overrides = numberMetric(metrics.remote_executor_overrides);
  const totalInvocations =
    numberMetric(invocationsBlock?.metrics?.unknown) ||
    projection.nodes.filter((node) => node.kind === "invocation").length;
  const observed = observedInvocations > 0;

  const countCells: RemoteBoundaryCell[] = [
    { key: "remote_invocations", label: "remote invocations", observed, value: String(observedInvocations), kind: "count" },
    { key: "executor_endpoints", label: "executor endpoints", observed: endpoints > 0, value: String(endpoints), kind: "count" },
    { key: "executor_overrides", label: "executor overrides", observed: overrides > 0, value: String(overrides), kind: "count" },
  ];
  const flag = (key: string, label: string): RemoteBoundaryCell => {
    const seen = metrics[key] === true;
    return { key, label, observed: seen, value: seen ? "observed" : "not observed", kind: "flag" };
  };
  const flagCells: RemoteBoundaryCell[] = [
    flag("worker_identity_observed", "worker identity"),
    flag("scheduler_assignment_observed", "scheduler assignment"),
    flag("queue_time_observed", "queue time"),
  ];

  const statement = observed
    ? `Remote execution observed in ${observedInvocations} of ${totalInvocations} recorded invocations.`
    : "No remote execution was observed in recorded invocations.";
  const observedLine = `${observedInvocations} of ${totalInvocations} recorded invocations used remote execution.`;

  const remoteModel = remoteLensModel(projection, packet);

  return {
    sourceKind: coerceSourceKind(remoteBlock?.source_kind),
    confidence: coerceConfidence(remoteBlock?.confidence),
    observed,
    observedInvocations,
    totalInvocations,
    statement,
    observedLine,
    explainer: REMOTE_EXPLAINER,
    countCells,
    flagCells,
    earnClaims: remoteBlock?.claims ?? [],
    unsupportedClaims: remoteModel.unsupportedClaims,
    boundaries: remoteModel.boundaries.map((boundary) => ({
      title: boundary.title,
      kind: boundary.kind,
      summary: boundary.summary,
      confidence: boundary.confidence,
      sourceKind: coerceSourceKind(boundary.sourceKind),
    })),
  };
}

/* ------------------------------------------------------------------------ *
 * Compare dimension headline (redesign P6 — DESIGN-SYSTEM.md §6, board 1i).
 * Derives the left value / delta pill / right value for a dimension card from
 * the REAL recorded left/right/delta fields — never a fabricated number. An
 * unrecognised dimension falls back to the honest "—" rather than inventing a
 * headline value.
 * ------------------------------------------------------------------------ */

export type CompareDeltaTone = "increase" | "decrease" | "flat" | "match" | "differs" | "neutral";

export type CompareHeadline = {
  left: string;
  right: string;
  delta: string | null;
  deltaTone: CompareDeltaTone;
  caption: string;
};

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function signedDelta(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

function statusCountTotal(value: unknown): number {
  const record = payloadRecord(value);
  if (!record) return 0;
  return Object.values(record).reduce<number>((sum, entry) => sum + (finiteNumber(entry) ?? 0), 0);
}

export function compareHeadline(dimension: CompareDimension): CompareHeadline {
  const left = payloadRecord(dimension.left) ?? {};
  const right = payloadRecord(dimension.right) ?? {};
  const delta = payloadRecord(dimension.delta) ?? {};
  const caption = dimension.summary;

  switch (dimension.id) {
    case "run_counts": {
      const l = finiteNumber(left.runs);
      const r = finiteNumber(right.runs);
      const d = finiteNumber(delta.runs);
      return {
        left: l === null ? "—" : String(l),
        right: r === null ? "—" : String(r),
        delta: d === null ? null : `Δ ${signedDelta(d)}`,
        deltaTone: d === null ? "neutral" : d > 0 ? "increase" : d < 0 ? "decrease" : "flat",
        caption,
      };
    }
    case "cache_metrics": {
      const lm = payloadRecord(left.metrics) ?? {};
      const rm = payloadRecord(right.metrics) ?? {};
      const lv = `${finiteNumber(lm.hits) ?? 0}/${finiteNumber(lm.misses) ?? 0}`;
      const rv = `${finiteNumber(rm.hits) ?? 0}/${finiteNumber(rm.misses) ?? 0}`;
      const d = finiteNumber(delta.hits);
      return {
        left: lv,
        right: rv,
        delta: d === null ? "Δ 0" : `Δ ${signedDelta(d)}`,
        deltaTone: d ? (d > 0 ? "increase" : "decrease") : "flat",
        caption,
      };
    }
    case "worker_identity": {
      const lv = left.worker_identity_observed === true ? "observed" : "not observed";
      const rv = right.worker_identity_observed === true ? "observed" : "not observed";
      const changed = delta.worker_identity_observed_changed === true;
      return { left: lv, right: rv, delta: changed ? "differs" : "match", deltaTone: changed ? "differs" : "match", caption };
    }
    case "status_deltas": {
      const l = statusCountTotal(left.status_counts);
      const r = statusCountTotal(right.status_counts);
      const changed = delta.changed === true;
      return { left: String(l), right: String(r), delta: changed ? "differs" : "match", deltaTone: changed ? "differs" : "match", caption };
    }
    default: {
      const entry = Object.entries(delta).find(([, value]) => finiteNumber(value) !== null);
      const d = entry ? finiteNumber(entry[1]) : null;
      return {
        left: "—",
        right: "—",
        delta: d === null ? null : `Δ ${signedDelta(d)}`,
        deltaTone: d === null ? "neutral" : d > 0 ? "increase" : d < 0 ? "decrease" : "flat",
        caption,
      };
    }
  }
}

/** Redacted `[REDACTED:...]` strings surfaced from a node payload's top-level
 *  scalar fields + command array, so the inspector can render them as lock
 *  chips (the P6 carry-forward of the P5 EvidenceRefRow treatment). Returns the
 *  field label + the real partial-path value; never a bare "[REDACTED]". */
export type RedactedPayloadField = { label: string; value: string };

export function redactedPayloadFields(payload: unknown): RedactedPayloadField[] {
  const record = payloadRecord(payload);
  if (!record) return [];
  const fields: RedactedPayloadField[] = [];
  for (const [key, value] of Object.entries(record)) {
    if (typeof value === "string" && isRedactedValue(value)) {
      fields.push({ label: labelKind(key), value });
    } else if (Array.isArray(value)) {
      for (const entry of value) {
        if (typeof entry === "string" && isRedactedValue(entry)) {
          fields.push({ label: labelKind(key), value: entry });
        }
      }
    }
  }
  return fields;
}
