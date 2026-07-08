import type {
  ActionGraphProjection,
  FocusFilter,
  ProjectionNode,
  ProofBlock,
  ProofMetricValue,
  ProofPacket,
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
        "Fixture fallback active — projection fetch failed; showing simulated sample data.",
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
