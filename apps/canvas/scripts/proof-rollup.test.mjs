/**
 * Unit test for proofRollup (proof-packet header honesty, redesign P5). Guards
 * the "counts are real, never fabricated" rule for the header rollup pills:
 * every block is counted into exactly one bucket, out-of-enum source_kinds
 * fall into the honest `unknown` bucket (never dropped), and the buckets always
 * sum to the true block total. Run with `npm --prefix apps/canvas run
 * test:unit` (Node strips the TS types on import). Also checks the REAL shipped
 * proof.json so the pills the drawer prints match the packet on disk.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { proofRollup } from "../src/pageModel.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function blocksOf(...kinds) {
  return kinds.map((source_kind, i) => ({ id: `b${i}`, source_kind }));
}

function bucketSum(r) {
  return r.recorded + r.computed + r.simulated + r.notCollected + r.unknown;
}

test("counts each source_kind into its bucket and sums to total", () => {
  const r = proofRollup(blocksOf("collectable_v1", "collectable_v1", "collectable_v1", "future", "future", "future", "future"));
  assert.deepEqual(
    { recorded: r.recorded, computed: r.computed, simulated: r.simulated, notCollected: r.notCollected, unknown: r.unknown },
    { recorded: 3, computed: 0, simulated: 0, notCollected: 4, unknown: 0 },
  );
  assert.equal(r.total, 7);
  assert.equal(bucketSum(r), r.total, "buckets must sum to total");
});

test("derived and simulated land in computed/simulated buckets", () => {
  const r = proofRollup(blocksOf("derived_v1", "derived_v1", "simulated_v1"));
  assert.equal(r.computed, 2);
  assert.equal(r.simulated, 1);
  assert.equal(bucketSum(r), r.total);
});

test("out-of-enum / unknown source_kind is counted, never dropped", () => {
  const r = proofRollup(blocksOf("collectable_v1", "unknown", "mystery_kind"));
  assert.equal(r.recorded, 1);
  assert.equal(r.unknown, 2, "both the explicit unknown and the out-of-enum kind bucket into unknown");
  assert.equal(bucketSum(r), r.total, "unknown kinds must not under-fill the rollup");
});

test("empty packet: all zero, total 0", () => {
  const r = proofRollup([]);
  assert.equal(r.total, 0);
  assert.equal(bucketSum(r), 0);
});

test("REAL shipped proof.json: rollup matches the packet on disk", () => {
  const packet = JSON.parse(
    fs.readFileSync(path.resolve(__dirname, "..", "public", "projections", "proof.json"), "utf8"),
  );
  const r = proofRollup(packet.blocks);
  assert.equal(r.total, packet.blocks.length, "total must equal real block count");
  assert.equal(bucketSum(r), r.total, "buckets must sum to the real total");
  // The canvas-dev packet is 3 recorded + 4 not-yet-collected (the flagship
  // honesty example in DESIGN-SYSTEM.md §4).
  assert.equal(r.recorded, 3);
  assert.equal(r.notCollected, 4);
  assert.equal(r.computed, 0);
  assert.equal(r.simulated, 0);
});
