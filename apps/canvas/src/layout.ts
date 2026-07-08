import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from "d3";
import type {
  ActionGraphProjection,
  PositionedEdge,
  PositionedNode,
  ProjectionEdge,
  ProjectionNode,
  SourceKind,
} from "./types";

const anchors: Record<string, { x: number; y: number }> = {
  agent: { x: -660, y: -210 },
  change: { x: -560, y: 120 },
  run: { x: -430, y: -40 },
  invocation: { x: -260, y: -230 },
  target: { x: -70, y: -20 },
  action: { x: 150, y: -120 },
  cache_event: { x: 350, y: -20 },
  remote_execution_config: { x: 420, y: -215 },
  worker_readiness: { x: 470, y: 130 },
  failure: { x: 260, y: 190 },
  artifact: { x: -40, y: 230 },
};

export function layoutProjection(projection: ActionGraphProjection): {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
} {
  const nodes: PositionedNode[] = projection.nodes.map((node, index) => {
    const anchor = anchors[node.kind] ?? {
      x: Math.cos(index) * 220,
      y: Math.sin(index) * 170,
    };
    return {
      ...node,
      x: anchor.x + (index % 4) * 26,
      y: anchor.y + (index % 3) * 32,
      radius: radiusFor(node.kind),
    };
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const linkData = projection.edges
    .map((edge) => {
      const source = byId.get(edge.from);
      const target = byId.get(edge.to);
      if (!source || !target) {
        return null;
      }
      return { ...edge, source, target };
    })
    .filter((edge): edge is ProjectionEdge & { source: PositionedNode; target: PositionedNode } =>
      Boolean(edge),
    );

  forceSimulation(nodes)
    .force(
      "link",
      forceLink<PositionedNode, ProjectionEdge & { source: PositionedNode; target: PositionedNode }>(
        linkData,
      )
        .id((node) => node.id)
        .distance((edge) => (edge.kind.includes("cache") ? 150 : 190))
        .strength(0.36),
    )
    .force("charge", forceManyBody().strength(-420))
    .force("collide", forceCollide<PositionedNode>().radius((node) => node.radius + 34))
    .force("x", forceX<PositionedNode>((node) => (anchors[node.kind]?.x ?? 0)).strength(0.14))
    .force("y", forceY<PositionedNode>((node) => (anchors[node.kind]?.y ?? 0)).strength(0.14))
    .force("center", forceCenter(0, 0))
    .stop()
    .tick(220);

  return {
    nodes,
    edges: linkData as PositionedEdge[],
  };
}

function radiusFor(kind: string): number {
  if (kind === "run") return 54;
  if (kind === "agent") return 50;
  if (kind === "change") return 40;
  if (kind === "failure") return 46;
  if (kind === "remote_execution_config") return 48;
  if (kind === "worker_readiness") return 46;
  if (kind === "cache_event") return 42;
  if (kind === "artifact") return 38;
  return 44;
}

/* ------------------------------------------------------------------------ *
 * Action-graph density scene (redesign P4).
 *
 * Replaces the hard 8-node visibility cap: nodes group BY RUN, collapsed
 * groups render as cluster capsules whose counts are derived from the REAL
 * member node ids (never invented), and every projection node is placed in
 * exactly ONE of {card, capsule membership} — so `cards + clustered ===
 * total` holds by construction. That identity is the honest invariant the
 * truth guard enforces: collapsed is never gone, and nothing is silently
 * hidden.
 * ------------------------------------------------------------------------ */

/** Kinds that may collapse into cluster capsules. Everything else (runs,
 *  changes, agents, failures, worker/remote boundary nodes …) always renders
 *  as a card — recorded failures and trust boundaries are never folded away. */
const GROUPABLE_KINDS = new Set(["invocation", "artifact", "target", "action", "cache_event"]);

/** Expansion key for the collapsed multi-change cluster card (board 1c). */
export const EXPAND_CHANGES_KEY = "kind:change";

/** Changes collapse into one stacked-halo cluster card at or above this. */
const CHANGE_CLUSTER_MIN = 4;

const COL_PITCH = 300;
const CARD_H = 54;
const CAPSULE_H = 32;
const V_GAP = 18;
/** Collapsed run pitch = CARD_H + BAND_GAP = 95px (board 1c). */
const BAND_GAP = 41;

function cardWidth(kind: string): number {
  if (kind === "invocation") return 190;
  if (kind === "run") return 172;
  if (kind === "agent") return 164;
  if (kind === "action") return 160;
  if (kind === "failure" || kind === "worker" || kind === "worker_readiness" || kind === "remote_execution_config") {
    return 182;
  }
  return 168;
}

export type GraphSceneCard = {
  entity: "card";
  node: ProjectionNode;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Faint mono suffix: "#1" for runs, "cmd:0" for invocations. */
  suffix: string | null;
  /** Mono meta line, e.g. "run · 5.4s". */
  metaLine: string;
  /** Recorded status for the glyph; exit codes surface as "exit N". */
  statusDisplay: string | number | null;
  /** Card owns a collapsed/expandable group of descendants. */
  expandable: boolean;
  expanded: boolean;
  /** Expansion key toggled by this card's chevron (usually node.id). */
  expandKey: string | null;
};

export type GraphSceneCluster = {
  entity: "cluster";
  id: string;
  /** Parent node the capsule hangs off; null for the global changes cluster. */
  ownerId: string | null;
  /** Expansion key that reveals this cluster's members. */
  expandKey: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** REAL member node ids — counts/labels derive from this, nothing else. */
  memberIds: string[];
  counts: { kind: string; count: number }[];
  label: string;
  /** Dominant member source_kind (drives hue; shape comes from the glyph). */
  sourceKind: SourceKind;
  /** Board-1c card-style cluster (the "7 changes" card) vs dashed capsule. */
  cardStyle: boolean;
  /** Sample member label rendered faintly on card-style clusters. */
  sampleLabel: string | null;
};

export type GraphSceneEdge = {
  id: string;
  kind: string;
  source_kind: SourceKind;
  fromId: string;
  toId: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  /** Edges into/out of a collapsed capsule are dashed (future-style geometry). */
  dashed: boolean;
};

export type GraphScene = {
  cards: GraphSceneCard[];
  clusters: GraphSceneCluster[];
  edges: GraphSceneEdge[];
  totals: { total: number; cards: number; clustered: number; clusters: number };
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
};

function parseTs(value: unknown): number | null {
  if (typeof value !== "string" || !value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function durationLabel(node: ProjectionNode): string | null {
  const payload = node.payload;
  if (!payload) return null;
  const start = parseTs(payload.started_at);
  const end = parseTs(payload.ended_at);
  if (start === null || end === null || end < start) return null;
  const seconds = (end - start) / 1000;
  if (seconds >= 90) {
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${Math.round(seconds - minutes * 60)}s`;
  }
  return `${(Math.round(seconds * 10) / 10).toFixed(1)}s`;
}

function invocationSuffix(node: ProjectionNode): string | null {
  for (const ref of node.evidence_refs ?? []) {
    const match = /^command:(\d+)$/.exec(ref);
    if (match) return `cmd:${match[1]}`;
  }
  return null;
}

function statusDisplayFor(node: ProjectionNode): string | number | null {
  if (node.status !== undefined && node.status !== null) return node.status;
  const exitCode = node.payload?.exit_code;
  if (typeof exitCode === "number") return `exit ${exitCode}`;
  return null;
}

const CLUSTER_KIND_ORDER = ["invocation", "artifact", "target", "action", "cache_event"];

function clusterCounts(memberIds: string[], byId: Map<string, ProjectionNode>): { kind: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const id of memberIds) {
    const kind = byId.get(id)?.kind ?? "unknown";
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }
  const ordered = [...counts.entries()].sort((a, b) => {
    const ai = CLUSTER_KIND_ORDER.indexOf(a[0]);
    const bi = CLUSTER_KIND_ORDER.indexOf(b[0]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
  return ordered.map(([kind, count]) => ({ kind, count }));
}

function clusterLabel(counts: { kind: string; count: number }[]): string {
  return counts
    .map(({ kind, count }) => `${count} ${kind.replace(/_/g, " ")}${count === 1 ? "" : "s"}`)
    .join(" · ");
}

function dominantSourceKind(memberIds: string[], byId: Map<string, ProjectionNode>): SourceKind {
  const counts = new Map<string, number>();
  for (const id of memberIds) {
    const kind = byId.get(id)?.source_kind ?? "unknown";
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }
  let best: SourceKind = "unknown";
  let bestCount = -1;
  for (const [kind, count] of counts) {
    if (count > bestCount) {
      best = kind as SourceKind;
      bestCount = count;
    }
  }
  return best;
}

function capsuleWidth(label: string): number {
  // pad 12+12, glyph 12, gaps 7+7, chevron 12, mono 11px ≈ 6.7px/char.
  return Math.round(24 + 12 + 14 + 12 + label.length * 6.7);
}

/** Owner-node id an artifact's evidence_refs pins it to, when recorded. */
function invocationRefParent(node: ProjectionNode, byId: Map<string, ProjectionNode>): string | null {
  for (const ref of node.evidence_refs ?? []) {
    const match = /^invocation:(.+)$/.exec(ref);
    if (match && byId.has(match[1])) return match[1];
  }
  return null;
}

export function buildGraphScene(
  projection: ActionGraphProjection,
  options: { expanded: ReadonlySet<string>; selectedId?: string | null },
): GraphScene {
  const nodes = projection.nodes;
  const byId = new Map(nodes.map((node) => [node.id, node]));

  // Parent map from real edges; artifacts prefer their recorded
  // `invocation:` evidence ref so they group under the producing command.
  const parentOf = new Map<string, string>();
  for (const edge of projection.edges) {
    if (!byId.has(edge.from) || !byId.has(edge.to)) continue;
    if (!parentOf.has(edge.to)) parentOf.set(edge.to, edge.from);
  }
  for (const node of nodes) {
    if (node.kind !== "artifact") continue;
    const refParent = invocationRefParent(node, byId);
    if (refParent) parentOf.set(node.id, refParent);
  }
  const childrenOf = new Map<string, string[]>();
  for (const node of nodes) {
    const parent = parentOf.get(node.id);
    if (!parent) continue;
    const list = childrenOf.get(parent);
    if (list) list.push(node.id);
    else childrenOf.set(parent, [node.id]);
  }

  const runs = nodes.filter((node) => node.kind === "run");
  const changes = nodes.filter((node) => node.kind === "change");
  const agents = nodes.filter((node) => node.kind === "agent");

  // Effective expansion: caller's set, plus every ancestor of the selection —
  // a selected node is always revealed (collapsed never hides the selection).
  const expanded = new Set(options.expanded);
  const selectedId = options.selectedId ?? null;
  if (selectedId && byId.has(selectedId)) {
    let cursor: string | undefined = selectedId;
    let hops = 0;
    while (cursor && hops < 32) {
      const parent = parentOf.get(cursor);
      if (parent) expanded.add(parent);
      cursor = parent;
      hops += 1;
    }
    if (byId.get(selectedId)?.kind === "change") expanded.add(EXPAND_CHANGES_KEY);
  }

  const changesClustered =
    changes.length >= CHANGE_CLUSTER_MIN && !expanded.has(EXPAND_CHANGES_KEY);

  const depthOf = (node: ProjectionNode): number => {
    if (node.kind === "agent") return 0;
    if (node.kind === "change") return 1;
    if (node.kind === "run") return 2;
    let depth = 3;
    let cursor = parentOf.get(node.id);
    let hops = 0;
    while (cursor && hops < 32) {
      const parent = byId.get(cursor);
      if (!parent) break;
      if (parent.kind === "run") return depth;
      depth += 1;
      cursor = parentOf.get(cursor);
      hops += 1;
    }
    return Math.min(depth, 6);
  };

  type PendingCard = {
    node: ProjectionNode;
    depth: number;
    expandable: boolean;
    expanded: boolean;
    expandKey: string | null;
  };
  type PendingCluster = {
    id: string;
    ownerId: string | null;
    expandKey: string;
    depth: number;
    memberIds: string[];
    cardStyle: boolean;
    sampleLabel: string | null;
  };
  type Band = { cards: PendingCard[]; clusters: PendingCluster[] };

  const visited = new Set<string>();
  const bands: Band[] = [];

  const groupableDescendants = (id: string): string[] => {
    const out: string[] = [];
    const stack = [...(childrenOf.get(id) ?? [])];
    while (stack.length > 0) {
      const next = stack.pop()!;
      const node = byId.get(next);
      if (!node) continue;
      if (GROUPABLE_KINDS.has(node.kind)) out.push(next);
      stack.push(...(childrenOf.get(next) ?? []));
    }
    return out;
  };

  const descend = (parent: ProjectionNode, band: Band) => {
    const parentExpanded = expanded.has(parent.id);
    const capsuleMembers: string[] = [];
    for (const childId of childrenOf.get(parent.id) ?? []) {
      const child = byId.get(childId);
      if (!child || visited.has(childId)) continue;
      if (!GROUPABLE_KINDS.has(child.kind)) {
        // Spine kinds (failures, worker boundaries …) are never capsuled.
        visited.add(childId);
        band.cards.push(makePending(child));
        descend(child, band);
        continue;
      }
      if (parentExpanded) {
        visited.add(childId);
        band.cards.push(makePending(child));
        descend(child, band);
      } else {
        // Collapse the child's whole groupable subtree into the capsule;
        // non-groupable descendants (if any) still surface as cards.
        collapseInto(child, band, capsuleMembers);
      }
    }
    if (capsuleMembers.length > 0) {
      band.clusters.push({
        id: `cluster:${parent.id}`,
        ownerId: parent.id,
        expandKey: parent.id,
        depth: depthOf(parent) + 1,
        memberIds: capsuleMembers,
        cardStyle: false,
        sampleLabel: null,
      });
    }
  };

  const collapseInto = (node: ProjectionNode, band: Band, members: string[]) => {
    visited.add(node.id);
    members.push(node.id);
    for (const childId of childrenOf.get(node.id) ?? []) {
      const child = byId.get(childId);
      if (!child || visited.has(childId)) continue;
      if (GROUPABLE_KINDS.has(child.kind)) {
        collapseInto(child, band, members);
      } else {
        visited.add(childId);
        band.cards.push(makePending(child));
        descend(child, band);
      }
    }
  };

  const makePending = (node: ProjectionNode): PendingCard => {
    const hasGroup = groupableDescendants(node.id).length > 0;
    return {
      node,
      depth: depthOf(node),
      expandable: hasGroup,
      expanded: hasGroup && expanded.has(node.id),
      expandKey: hasGroup ? node.id : null,
    };
  };

  // 1. One band per run, in projection order (runs column, 95px pitch).
  for (const run of runs) {
    if (visited.has(run.id)) continue;
    visited.add(run.id);
    const band: Band = { cards: [makePending(run)], clusters: [] };
    descend(run, band);
    bands.push(band);
  }

  // 2. Orphans — anything unreachable from a run/change/agent still renders
  //    honestly as cards in a trailing band (never dropped).
  const orphanBand: Band = { cards: [], clusters: [] };
  for (const node of nodes) {
    if (visited.has(node.id) || node.kind === "change" || node.kind === "agent") continue;
    visited.add(node.id);
    orphanBand.cards.push(makePending(node));
    descend(node, orphanBand);
  }
  if (orphanBand.cards.length > 0) bands.push(orphanBand);

  // ---- Vertical layout: stack each band's columns, center columns in band.
  const cards: GraphSceneCard[] = [];
  const clusters: GraphSceneCluster[] = [];
  const centerOf = new Map<string, { x: number; y: number; w: number; h: number }>();

  const runIndex = new Map(runs.map((run, index) => [run.id, index]));

  const placeCard = (pending: PendingCard, x: number, y: number) => {
    const node = pending.node;
    const w = cardWidth(node.kind);
    const duration = durationLabel(node);
    const metaLine = `${node.kind.replace(/_/g, " ")}${duration ? ` · ${duration}` : ""}`;
    const suffix =
      node.kind === "run"
        ? `#${(runIndex.get(node.id) ?? 0) + 1}`
        : node.kind === "invocation"
          ? invocationSuffix(node)
          : null;
    cards.push({
      entity: "card",
      node,
      x,
      y,
      w,
      h: CARD_H,
      suffix,
      metaLine,
      statusDisplay: statusDisplayFor(node),
      expandable: pending.expandable,
      expanded: pending.expanded,
      expandKey: pending.expandKey,
    });
    centerOf.set(node.id, { x, y, w, h: CARD_H });
  };

  const placeCluster = (pending: PendingCluster, x: number, y: number) => {
    const counts = clusterCounts(pending.memberIds, byId);
    const label = pending.cardStyle
      ? `${pending.memberIds.length} ${byId.get(pending.memberIds[0])?.kind ?? "node"}${pending.memberIds.length === 1 ? "" : "s"}`
      : clusterLabel(counts);
    const w = pending.cardStyle ? 176 : capsuleWidth(label);
    const h = pending.cardStyle ? CARD_H : CAPSULE_H;
    clusters.push({
      entity: "cluster",
      id: pending.id,
      ownerId: pending.ownerId,
      expandKey: pending.expandKey,
      x,
      y,
      w,
      h,
      memberIds: pending.memberIds,
      counts,
      label,
      sourceKind: dominantSourceKind(pending.memberIds, byId),
      cardStyle: pending.cardStyle,
      sampleLabel: pending.sampleLabel,
    });
    centerOf.set(pending.id, { x, y, w, h });
  };

  let bandY = 0;
  for (const band of bands) {
    type Item = { kind: "card"; card: PendingCard; h: number } | { kind: "cluster"; cluster: PendingCluster; h: number };
    const columns = new Map<number, Item[]>();
    const push = (depth: number, item: Item) => {
      const list = columns.get(depth);
      if (list) list.push(item);
      else columns.set(depth, [item]);
    };
    for (const card of band.cards) push(card.depth, { kind: "card", card, h: CARD_H });
    for (const cluster of band.clusters) push(cluster.depth, { kind: "cluster", cluster, h: CAPSULE_H });

    let bandHeight = CARD_H;
    for (const items of columns.values()) {
      const height = items.reduce((sum, item) => sum + item.h, 0) + (items.length - 1) * V_GAP;
      bandHeight = Math.max(bandHeight, height);
    }
    for (const [depth, items] of columns) {
      const colHeight = items.reduce((sum, item) => sum + item.h, 0) + (items.length - 1) * V_GAP;
      let y = bandY + (bandHeight - colHeight) / 2;
      for (const item of items) {
        if (item.kind === "card") placeCard(item.card, depth * COL_PITCH, y);
        else placeCluster(item.cluster, depth * COL_PITCH, y);
        y += item.h + V_GAP;
      }
    }
    bandY += bandHeight + BAND_GAP;
  }

  // 3. Ancestor columns — changes center on their runs, agents on changes.
  const childCenters = (ids: string[]): number[] =>
    ids
      .map((id) => centerOf.get(id))
      .filter((box): box is NonNullable<typeof box> => Boolean(box))
      .map((box) => box.y + box.h / 2);

  const settleColumn = (
    entries: { place: (x: number, y: number) => void; idealCenter: number; h: number }[],
    x: number,
  ) => {
    const sorted = [...entries].sort((a, b) => a.idealCenter - b.idealCenter);
    let cursor = -Infinity;
    for (const entry of sorted) {
      let top = entry.idealCenter - entry.h / 2;
      if (top < cursor) top = cursor;
      entry.place(x, top);
      cursor = top + entry.h + V_GAP;
    }
  };

  const runCenters = childCenters(runs.map((run) => run.id));
  const runsMid =
    runCenters.length > 0 ? (Math.min(...runCenters) + Math.max(...runCenters)) / 2 : 0;

  if (changesClustered && changes.length > 0) {
    for (const change of changes) visited.add(change.id);
    const pending: PendingCluster = {
      id: "cluster:changes",
      ownerId: null,
      expandKey: EXPAND_CHANGES_KEY,
      depth: 1,
      memberIds: changes.map((change) => change.id),
      cardStyle: true,
      sampleLabel: changes[0]?.label ? changes[0].label.split("/").pop() ?? null : null,
    };
    placeCluster(pending, 1 * COL_PITCH, runsMid - CARD_H / 2);
  } else {
    const entries = changes.map((change) => {
      visited.add(change.id);
      const targets = (childrenOf.get(change.id) ?? []).filter((id) => centerOf.has(id));
      const centers = childCenters(targets);
      const ideal = centers.length > 0 ? centers.reduce((a, b) => a + b, 0) / centers.length : runsMid;
      return {
        h: CARD_H,
        idealCenter: ideal,
        place: (x: number, y: number) => placeCard(makePending(change), x, y),
      };
    });
    settleColumn(entries, 1 * COL_PITCH);
  }

  const agentEntries = agents.map((agent) => {
    visited.add(agent.id);
    const childIds = (childrenOf.get(agent.id) ?? []).map((id) =>
      centerOf.has(id) ? id : changesClustered && byId.get(id)?.kind === "change" ? "cluster:changes" : id,
    );
    const centers = childCenters(childIds);
    const ideal = centers.length > 0 ? centers.reduce((a, b) => a + b, 0) / centers.length : runsMid;
    return {
      h: CARD_H,
      idealCenter: ideal,
      place: (x: number, y: number) => placeCard(makePending(agent), x, y),
    };
  });
  settleColumn(agentEntries, 0);

  // ---- Edges between visible entities; collapsed endpoints resolve to their
  // capsule and render dashed. Duplicate (from,to) pairs merge into one path.
  const capsuleOf = new Map<string, string>();
  for (const cluster of clusters) {
    for (const memberId of cluster.memberIds) capsuleOf.set(memberId, cluster.id);
  }
  const representative = (id: string): string | null =>
    centerOf.has(id) ? id : capsuleOf.get(id) ?? null;

  const edges: GraphSceneEdge[] = [];
  const seenPairs = new Set<string>();
  for (const edge of projection.edges) {
    const fromId = representative(edge.from);
    const toId = representative(edge.to);
    if (!fromId || !toId || fromId === toId) continue;
    const pair = `${fromId}→${toId}`;
    if (seenPairs.has(pair)) continue;
    seenPairs.add(pair);
    const from = centerOf.get(fromId)!;
    const to = centerOf.get(toId)!;
    const leftToRight = from.x + from.w / 2 <= to.x + to.w / 2;
    edges.push({
      id: `scene:${pair}`,
      kind: edge.kind,
      source_kind: edge.source_kind,
      fromId,
      toId,
      x1: leftToRight ? from.x + from.w : from.x,
      y1: from.y + from.h / 2,
      x2: leftToRight ? to.x : to.x + to.w,
      y2: to.y + to.h / 2,
      dashed: fromId.startsWith("cluster:") || toId.startsWith("cluster:"),
    });
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const box of centerOf.values()) {
    minX = Math.min(minX, box.x);
    minY = Math.min(minY, box.y);
    maxX = Math.max(maxX, box.x + box.w);
    maxY = Math.max(maxY, box.y + box.h);
  }
  if (!Number.isFinite(minX)) {
    minX = 0;
    minY = 0;
    maxX = 0;
    maxY = 0;
  }

  const clustered = clusters.reduce((sum, cluster) => sum + cluster.memberIds.length, 0);
  return {
    cards,
    clusters,
    edges,
    totals: {
      total: nodes.length,
      cards: cards.length,
      clustered,
      clusters: clusters.length,
    },
    bounds: { minX, minY, maxX, maxY },
  };
}
