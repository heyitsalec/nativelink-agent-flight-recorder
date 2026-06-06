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
} from "./types";

const anchors: Record<string, { x: number; y: number }> = {
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
  if (kind === "failure") return 46;
  if (kind === "remote_execution_config") return 48;
  if (kind === "worker_readiness") return 46;
  if (kind === "cache_event") return 42;
  if (kind === "artifact") return 38;
  return 44;
}
