/**
 * Unit test for buildGraphScene's honesty partition (action-graph density
 * model, redesign P4). Proves at the SOURCE what the DOM truth-guard can only
 * partly check: the renderer provably cannot silently drop, double-count, or
 * fabricate ("phantom") a node. Pins the invariant so a future layout refactor
 * cannot quietly break it.
 *
 * The partition invariant, over ANY expansion state:
 *   (a) DISJOINT + EXHAUSTIVE — every projection node id appears EXACTLY ONCE
 *       across {rendered card ids} ∪ {all capsule memberIds}.
 *   (b) NO PHANTOM — every capsule memberId (and every card id) is a real
 *       projection node id; nothing invented.
 *   (c) COUNT IDENTITY — Σ(capsule.memberIds.length) + cards === total, and
 *       scene.totals reports those same numbers.
 *   (d) HONEST LABELS — the digits printed on a capsule label derive from its
 *       real, distinct members (they sum to memberIds.length).
 *
 * Run with `npm --prefix apps/canvas run test:unit` (Node strips the TS types
 * on import). Imports the source directly so the shipped function is tested.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildGraphScene, EXPAND_CHANGES_KEY } from "../src/layout.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const realFixture = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, "..", "public", "projections", "action-graph.json"),
    "utf8",
  ),
);

/**
 * Small synthetic graph with MIXED source_kinds: one run whose invocation +
 * three artifacts collapse into a capsule when the run is unexpanded. Exercises
 * the run-capsule path independent of the real fixture's change-cluster path.
 */
const syntheticMixed = {
  run_group: "synthetic",
  projection_kind: "action_graph",
  summary: { runs: 1, nodes: 6 },
  nodes: [
    { id: "agent:a1", kind: "agent", label: "agent one", source_kind: "simulated_v1", confidence: "high", evidence_refs: [], redaction_state: "safe" },
    { id: "change:c1", kind: "change", label: "src/App.tsx", source_kind: "derived_v1", confidence: "high", evidence_refs: [], redaction_state: "safe" },
    { id: "run:r1", kind: "run", label: "build one", source_kind: "collectable_v1", confidence: "high", evidence_refs: [], redaction_state: "safe" },
    { id: "inv:i1", kind: "invocation", label: "npm build", source_kind: "collectable_v1", confidence: "high", evidence_refs: ["command:0"], redaction_state: "safe" },
    { id: "art:x1", kind: "artifact", label: "out/a.js", source_kind: "collectable_v1", confidence: "medium", evidence_refs: ["invocation:inv:i1"], redaction_state: "safe" },
    { id: "art:x2", kind: "artifact", label: "out/b.js", source_kind: "derived_v1", confidence: "medium", evidence_refs: ["invocation:inv:i1"], redaction_state: "safe" },
    { id: "art:x3", kind: "artifact", label: "out/c.js", source_kind: "future", confidence: "unknown", evidence_refs: ["invocation:inv:i1"], redaction_state: "safe" },
  ],
  edges: [
    { id: "e1", kind: "authored", source_kind: "derived_v1", from: "agent:a1", to: "change:c1" },
    { id: "e2", kind: "triggered", source_kind: "derived_v1", from: "change:c1", to: "run:r1" },
    { id: "e3", kind: "ran", source_kind: "collectable_v1", from: "run:r1", to: "inv:i1" },
    { id: "e4", kind: "produced", source_kind: "collectable_v1", from: "inv:i1", to: "art:x1" },
    { id: "e5", kind: "produced", source_kind: "collectable_v1", from: "inv:i1", to: "art:x2" },
    { id: "e6", kind: "produced", source_kind: "collectable_v1", from: "inv:i1", to: "art:x3" },
  ],
};

/** Expansion states worth pinning: fully collapsed, default (first run), all. */
function expansionStates(projection) {
  const runIds = projection.nodes.filter((n) => n.kind === "run").map((n) => n.id);
  const groupOwners = projection.nodes
    .filter((n) => ["run", "invocation", "artifact", "target", "action"].includes(n.kind))
    .map((n) => n.id);
  return [
    { name: "collapsed", expanded: new Set() },
    { name: "first-run", expanded: new Set(runIds.slice(0, 1)) },
    { name: "all-expanded", expanded: new Set([...groupOwners, ...runIds, EXPAND_CHANGES_KEY]) },
  ];
}

function assertPartition(projection, scene, label) {
  const projectionIds = projection.nodes.map((n) => n.id);
  const projectionSet = new Set(projectionIds);
  assert.equal(projectionSet.size, projectionIds.length, `${label}: fixture has duplicate node ids`);

  const cardIds = scene.cards.map((c) => c.node.id);
  const memberIds = scene.clusters.flatMap((c) => c.memberIds);

  // (b) NO PHANTOM: every emitted id is a real projection node id.
  for (const id of cardIds) {
    assert.ok(projectionSet.has(id), `${label}: card id ${id} is not a real projection node (phantom)`);
  }
  for (const id of memberIds) {
    assert.ok(projectionSet.has(id), `${label}: capsule member ${id} is not a real projection node (phantom)`);
  }

  // (a) DISJOINT: no id is both a card and a member, and none repeats.
  const cardSet = new Set(cardIds);
  assert.equal(cardSet.size, cardIds.length, `${label}: a node is rendered as a card more than once`);
  const memberSet = new Set(memberIds);
  assert.equal(memberSet.size, memberIds.length, `${label}: a node is a member of more than one capsule`);
  for (const id of cardSet) {
    assert.ok(!memberSet.has(id), `${label}: node ${id} is BOTH a card and clustered (double-counted)`);
  }

  // (a) EXHAUSTIVE: the union covers every projection node, nothing dropped.
  const union = new Set([...cardSet, ...memberSet]);
  assert.equal(union.size, projectionSet.size, `${label}: cards ∪ members size ${union.size} !== total ${projectionSet.size}`);
  for (const id of projectionSet) {
    assert.ok(union.has(id), `${label}: projection node ${id} is neither a card nor clustered (silently hidden)`);
  }

  // (c) COUNT IDENTITY: matches, and scene.totals reports the truth.
  assert.equal(
    cardIds.length + memberIds.length,
    projectionSet.size,
    `${label}: cards (${cardIds.length}) + clustered (${memberIds.length}) !== total (${projectionSet.size})`,
  );
  assert.equal(scene.totals.total, projectionSet.size, `${label}: totals.total misreports the node count`);
  assert.equal(scene.totals.cards, cardIds.length, `${label}: totals.cards misreports rendered cards`);
  assert.equal(scene.totals.clustered, memberIds.length, `${label}: totals.clustered misreports clustered members`);
  assert.equal(scene.totals.clusters, scene.clusters.length, `${label}: totals.clusters misreports capsule count`);

  // (d) HONEST LABELS: label digits derive from the real, distinct members.
  for (const cluster of scene.clusters) {
    assert.ok(cluster.memberIds.length > 0, `${label}: capsule ${cluster.id} has no members`);
    assert.equal(
      new Set(cluster.memberIds).size,
      cluster.memberIds.length,
      `${label}: capsule ${cluster.id} lists a member twice`,
    );
    const labelSum = (cluster.label.match(/\d+/g) ?? []).map(Number).reduce((a, b) => a + b, 0);
    assert.equal(
      labelSum,
      cluster.memberIds.length,
      `${label}: capsule ${cluster.id} label "${cluster.label}" sums to ${labelSum}, not member count ${cluster.memberIds.length}`,
    );
  }
}

for (const [fixtureName, projection] of [
  ["real fixture (action-graph.json)", realFixture],
  ["synthetic mixed graph", syntheticMixed],
]) {
  for (const state of expansionStates(projection)) {
    test(`${fixtureName} — partition holds [${state.name}]`, () => {
      const scene = buildGraphScene(projection, { expanded: state.expanded });
      assertPartition(projection, scene, `${fixtureName}/${state.name}`);
    });
  }

  test(`${fixtureName} — partition holds with a node selected (ancestors auto-expand)`, () => {
    const deepest = [...projection.nodes].reverse().find((n) => n.kind === "artifact") ?? projection.nodes[0];
    const scene = buildGraphScene(projection, { expanded: new Set(), selectedId: deepest.id });
    assertPartition(projection, scene, `${fixtureName}/selected`);
    // The selected node is revealed as a card, never left folded inside a capsule.
    const memberIds = new Set(scene.clusters.flatMap((c) => c.memberIds));
    assert.ok(
      scene.cards.some((c) => c.node.id === deepest.id) || !memberIds.has(deepest.id),
      `selected node ${deepest.id} must not be hidden inside a capsule`,
    );
  });
}
