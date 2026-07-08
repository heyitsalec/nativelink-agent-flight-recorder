/**
 * Unit tests for the "focus applied" system-state helpers (redesign P7 §9). The
 * focus pill's honest match count is a pure function in pageModel.ts, imported
 * directly by `node --test` (Node strips the TS types).
 *
 * Proves the honesty contract: the count reflects what the filter TRULY matched
 * and NEVER falls back to "all nodes" when a category is empty (an empty focus
 * says "0 of N" — the graph dims non-matches, it never silently hides). "all"
 * counts everything; each filter counts only its real node kinds.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { focusMatchCount, focusLabel } from "../src/pageModel.ts";

const NODES = [
  { id: "r1", kind: "run", source_kind: "collectable_v1" },
  { id: "i1", kind: "invocation", source_kind: "collectable_v1" },
  { id: "f1", kind: "failure", source_kind: "collectable_v1" },
  { id: "a1", kind: "agent", source_kind: "simulated_v1" },
  { id: "c1", kind: "change", source_kind: "simulated_v1" },
  { id: "ce1", kind: "cache_event", source_kind: "derived_v1" },
  { id: "d1", kind: "artifact", source_kind: "derived_v1" },
];

test("focus=all counts every node", () => {
  assert.equal(focusMatchCount(NODES, "all"), NODES.length);
});

test("focus=failures counts only recorded failures", () => {
  assert.equal(focusMatchCount(NODES, "failures"), 1);
});

test("focus=cache counts only cache_event nodes", () => {
  assert.equal(focusMatchCount(NODES, "cache"), 1);
});

test("focus=agent counts agent + change nodes", () => {
  assert.equal(focusMatchCount(NODES, "agent"), 2);
});

test("focus=derived counts derived_v1 source nodes", () => {
  assert.equal(focusMatchCount(NODES, "derived"), 2);
});

test("empty match is HONEST 0 — never the all-nodes fallback", () => {
  // No remote_execution_config / worker_readiness nodes present.
  assert.equal(focusMatchCount(NODES, "remote"), 0);
  // No failures in a clean projection → 0 of N, not a silently-hidden graph.
  const clean = NODES.filter((n) => n.kind !== "failure");
  assert.equal(focusMatchCount(clean, "failures"), 0);
});

test("remote match counts real remote nodes when present", () => {
  const withRemote = [
    ...NODES,
    { id: "rc1", kind: "remote_execution_config", source_kind: "future" },
    { id: "wr1", kind: "worker_readiness", source_kind: "future" },
  ];
  assert.equal(focusMatchCount(withRemote, "remote"), 2);
});

test("focusLabel is human copy for the pill", () => {
  assert.equal(focusLabel("failures"), "failures");
  assert.equal(focusLabel("cache"), "cache misses");
  assert.equal(focusLabel("agent"), "agent loop");
  assert.equal(focusLabel("all"), "all evidence");
});
