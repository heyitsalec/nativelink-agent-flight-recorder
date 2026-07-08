/**
 * Unit tests for the P6 lens model helpers (redesign P6 — DESIGN-SYSTEM.md
 * §3/§5/§6). These are the pure functions the redesigned Validation Runway,
 * Remote Boundary, and Compare Runs lenses are built from — kept in pageModel.ts
 * (no JSX) so `node --test` can import them directly (Node strips TS types on
 * import). Run with `npm --prefix apps/canvas run test:unit`. Covers:
 *   - runwayLanes: fixed ordered lanes over REAL nodes; empty lanes STATE their
 *     emptiness (cache/failures with the board copy); never blank.
 *   - remoteBoundaryView: dashed slate metrics over the real remote block;
 *     "not observed" flags, honest observed line, boundary shape-encoding.
 *   - compareHeadline: left/delta/right derived from real recorded fields;
 *     an unrecognised dimension falls back to honest "—", never a fabricated
 *     number.
 *   - redactedPayloadFields: surfaces real `[REDACTED:...]` values (incl. from
 *     a command array) so the inspector shows the partial path, never "[REDACTED]".
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  compareHeadline,
  redactedPayloadFields,
  remoteBoundaryView,
  runwayLanes,
} from "../src/pageModel.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadProjection(relPath) {
  return JSON.parse(
    fs.readFileSync(path.resolve(__dirname, "..", "public", "projections", relPath), "utf8"),
  );
}

const graph = loadProjection("action-graph.json");
const packet = loadProjection("proof.json");
const compare = loadProjection("compare-projection.json");

/* ── runwayLanes ─────────────────────────────────────────────────────── */

test("runwayLanes returns the 7 fixed lanes in board order", () => {
  const lanes = runwayLanes(graph.nodes);
  assert.deepEqual(
    lanes.map((lane) => lane.kind),
    ["run", "invocation", "target", "action", "cache_event", "failure", "artifact"],
  );
});

test("runwayLanes counts match the real projection node distribution", () => {
  const lanes = runwayLanes(graph.nodes);
  const byKind = Object.fromEntries(lanes.map((lane) => [lane.kind, lane.count]));
  // action-graph.json default = run 7, invocation 14, artifact 42, changes 7.
  assert.equal(byKind.run, 7);
  assert.equal(byKind.invocation, 14);
  assert.equal(byKind.artifact, 42);
  // A lane sums exactly its nodes — nothing invented, nothing dropped.
  for (const lane of lanes) assert.equal(lane.count, lane.nodes.length);
});

test("empty lanes state their emptiness honestly — never blank", () => {
  const lanes = runwayLanes(graph.nodes);
  const cache = lanes.find((lane) => lane.kind === "cache_event");
  const failures = lanes.find((lane) => lane.kind === "failure");
  assert.equal(cache.empty, true);
  assert.equal(cache.emptyMessage, "no cache events recorded in this projection");
  assert.equal(failures.empty, true);
  // Failures lane names the recorded command count rather than leaving a gap.
  assert.equal(failures.emptyMessage, "no failures recorded — 14 of 14 commands completed");
});

/* ── remoteBoundaryView ──────────────────────────────────────────────── */

test("remoteBoundaryView is all not-observed for the default packet, never red", () => {
  const view = remoteBoundaryView(graph, packet);
  assert.equal(view.observed, false);
  assert.equal(view.statement, "No remote execution was observed in recorded invocations.");
  // 3 count cells all 0, 3 flag cells all "not observed" — nothing observed.
  assert.equal(view.countCells.length, 3);
  assert.equal(view.flagCells.length, 3);
  for (const cell of view.countCells) assert.equal(cell.value, "0");
  for (const cell of view.flagCells) {
    assert.equal(cell.observed, false);
    assert.equal(cell.value, "not observed");
  }
  // Honest observed line names the real invocation total (14 recorded commands).
  assert.equal(view.observedLine, "0 of 14 recorded invocations used remote execution.");
  // The remote block ships 5 unsupported claims — named, not hidden.
  assert.equal(view.unsupportedClaims.length, 5);
});

test("remoteBoundaryView surfaces the block's requirement claims (what would earn)", () => {
  const view = remoteBoundaryView(graph, packet);
  assert.ok(view.earnClaims.length >= 1);
  assert.ok(view.earnClaims.some((claim) => /remote_executor/i.test(claim)));
});

/* ── compareHeadline ─────────────────────────────────────────────────── */

test("compareHeadline derives run_counts headline from real fields", () => {
  const dimension = compare.dimensions.find((d) => d.id === "run_counts");
  const headline = compareHeadline(dimension);
  assert.equal(headline.left, "6");
  assert.equal(headline.right, "2");
  assert.equal(headline.delta, "Δ -4");
  assert.equal(headline.deltaTone, "decrease");
});

test("compareHeadline reports worker_identity as a match / not-observed pair", () => {
  const dimension = compare.dimensions.find((d) => d.id === "worker_identity");
  const headline = compareHeadline(dimension);
  assert.equal(headline.left, "not observed");
  assert.equal(headline.right, "not observed");
  assert.equal(headline.delta, "match");
});

test("compareHeadline falls back to honest '—' for an unrecognised dimension", () => {
  const headline = compareHeadline({
    id: "unheard_of",
    title: "Mystery",
    summary: "n/a",
    source_kind: "derived_v1",
    confidence: "medium",
    redaction_state: "safe",
    evidence_refs: [],
    claims: [],
    left: {},
    right: {},
    delta: {},
  });
  assert.equal(headline.left, "—");
  assert.equal(headline.right, "—");
  assert.equal(headline.delta, null);
});

/* ── redactedPayloadFields ───────────────────────────────────────────── */

test("redactedPayloadFields surfaces real [REDACTED:...] values from a command array", () => {
  const payload = {
    command: ["[REDACTED:abs_path]/bazel", "test", "//..."],
    cwd: "[REDACTED:abs_path]/workspace",
    exit_code: 3,
  };
  const fields = redactedPayloadFields(payload);
  // Never a bare "[REDACTED]" — the partial path is kept.
  assert.ok(fields.some((f) => f.value === "[REDACTED:abs_path]/bazel"));
  assert.ok(fields.some((f) => f.label === "cwd" && f.value === "[REDACTED:abs_path]/workspace"));
  // Non-redacted scalars are not surfaced.
  assert.ok(!fields.some((f) => f.label === "exit code"));
});

test("redactedPayloadFields returns nothing for a clean payload", () => {
  assert.deepEqual(redactedPayloadFields({ command: ["npm", "run", "build"], exit_code: 0 }), []);
  assert.deepEqual(redactedPayloadFields(null), []);
});
