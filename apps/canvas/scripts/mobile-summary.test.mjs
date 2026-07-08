/**
 * Unit tests for the P8 mobile bottom-sheet summary helper (redesign P8 —
 * DESIGN-SYSTEM.md §"Mobile 390w", board 1m). `mobileSummary` is the pure
 * function behind the mobile sheet's one-line readout. Kept in pageModel.ts
 * (no JSX) so `node --test` can import it directly. Run with
 * `npm --prefix apps/canvas run test:unit`. Proves:
 *   - the real default projection yields the board string
 *     "7 runs · 70 nodes · 0 failures · remote execution not observed"
 *     from RECORDED counts (never fabricated);
 *   - singular/plural agreement for runs + failures;
 *   - remote-observed flips only the remote clause (metric-driven by the caller).
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { mobileSummary } from "../src/pageModel.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projection = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "..", "public", "projections", "action-graph.json"),
    "utf8",
  ),
);

test("mobileSummary: real default projection matches the board 1m readout", () => {
  const summary = mobileSummary(projection.summary, projection.nodes.length, false);
  assert.equal(
    summary,
    "7 runs · 70 nodes · 0 failures · remote execution not observed",
  );
});

test("mobileSummary: numbers come from the recorded summary, not fabricated", () => {
  // The real recorded counts — asserted so a projection change is caught here.
  assert.equal(Number(projection.summary.runs), 7);
  assert.equal(Number(projection.summary.nodes), 70);
  assert.equal(Number(projection.summary.failures), 0);
});

test("mobileSummary: singular/plural agreement for runs and failures", () => {
  const s = mobileSummary({ runs: 1, nodes: 12, failures: 1 }, 12, false);
  assert.equal(s, "1 run · 12 nodes · 1 failure · remote execution not observed");
});

test("mobileSummary: remoteObserved flips only the remote clause", () => {
  const s = mobileSummary({ runs: 2, nodes: 9, failures: 0 }, 9, true);
  assert.equal(s, "2 runs · 9 nodes · 0 failures · remote execution observed");
});

test("mobileSummary: falls back to node count when summary.nodes is absent", () => {
  const s = mobileSummary({ runs: 3, failures: 0 }, 42, false);
  assert.equal(s, "3 runs · 42 nodes · 0 failures · remote execution not observed");
});
