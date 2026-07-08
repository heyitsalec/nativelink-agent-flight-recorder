/**
 * Unit test for evidenceMix (truth-label rollup honesty guard, redesign P3).
 *
 * Guards the "never under-represent" rule: the context-banner mix bar must
 * always account for EVERY node — segments must sum to `total` even when a
 * projection carries a non-null source_kind outside the known enum (such
 * kinds bucket into the honest slate "unknown" catch-all, never silently
 * dropped). Run with `npm --prefix apps/canvas run test:unit` (Node strips
 * the TS types on import). Imports the source directly so the shipped
 * function is under test.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { evidenceMix } from "../src/pageModel.ts";

/** Minimal projection stub — evidenceMix only reads nodes[].source_kind. */
function projectionWith(kinds) {
  return { run_group: "test", nodes: kinds.map((source_kind, i) => ({ id: `n${i}`, source_kind })) };
}

function segmentSum(mix) {
  return mix.segments.reduce((sum, seg) => sum + seg.count, 0);
}

test("mixed in-enum input: segments sum to total, counts and order correct", () => {
  const mix = evidenceMix(
    projectionWith(["collectable_v1", "collectable_v1", "derived_v1", "simulated_v1", "future", "unknown"]),
  );
  assert.equal(mix.total, 6);
  assert.equal(segmentSum(mix), mix.total, "segments must sum to total");
  assert.deepEqual(
    mix.segments.map((s) => [s.kind, s.count]),
    [["collectable_v1", 2], ["derived_v1", 1], ["simulated_v1", 1], ["future", 1], ["unknown", 1]],
  );
  assert.equal(mix.dominant, "collectable_v1");
});

test("out-of-enum source_kind is bucketed into unknown, NOT dropped", () => {
  const mix = evidenceMix(
    projectionWith(["collectable_v1", "collectable_v1", "collectable_v2", "mystery_kind"]),
  );
  assert.equal(mix.total, 4);
  assert.equal(segmentSum(mix), mix.total, "out-of-enum kinds must not under-fill the bar");
  const unknown = mix.segments.find((s) => s.kind === "unknown");
  assert.ok(unknown, "unrecognized kinds must surface as an honest unknown segment");
  assert.equal(unknown.count, 2, "both out-of-enum nodes count into unknown");
  assert.equal(mix.dominant, "collectable_v1");
});

test("null/undefined source_kind still lands in unknown (existing rescue)", () => {
  const mix = evidenceMix(projectionWith(["derived_v1", null, undefined]));
  assert.equal(mix.total, 3);
  assert.equal(segmentSum(mix), mix.total);
  assert.equal(mix.segments.find((s) => s.kind === "unknown")?.count, 2);
});

test("out-of-enum majority folds into unknown and dominant reflects it honestly", () => {
  const mix = evidenceMix(projectionWith(["alien_a", "alien_b", "alien_c", "collectable_v1"]));
  assert.equal(mix.total, 4);
  assert.equal(segmentSum(mix), mix.total);
  assert.equal(mix.segments.find((s) => s.kind === "unknown")?.count, 3);
  assert.equal(mix.dominant, "unknown", "dominant must not mispick when unknowns lead");
});

test("fractions are real node fractions and sum to 1 for non-empty input", () => {
  const mix = evidenceMix(projectionWith(["collectable_v1", "weird", "weird", "future"]));
  const fractionSum = mix.segments.reduce((sum, seg) => sum + seg.fraction, 0);
  assert.ok(Math.abs(fractionSum - 1) < 1e-9, `fractions sum to 1 (got ${fractionSum})`);
  assert.equal(mix.segments.find((s) => s.kind === "unknown")?.fraction, 0.5);
});

test("empty projection: total 0, no segments, dominant unknown", () => {
  const mix = evidenceMix(projectionWith([]));
  assert.equal(mix.total, 0);
  assert.deepEqual(mix.segments, []);
  assert.equal(mix.dominant, "unknown");
});
