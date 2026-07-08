/**
 * Unit tests for the proof-drawer honesty helpers (redesign P5 review fixes).
 * These are the pure functions the drawer's TOC row meta, redacted header chip,
 * and sticky "N more blocks" footer pill are built from — kept in pageModel.ts
 * (no JSX) so `node --test` can import them directly. Run with
 * `npm --prefix apps/canvas run test:unit` (Node strips the TS types on
 * import). Covers:
 *   - M5: a future block that carries a real metric surfaces it (not "no claim")
 *   - M1: a redacted block with no payload value falls back to the honest
 *         "redacted" treatment rather than inventing / baring "[REDACTED]"
 *   - M2: the "N more blocks" count is exactly the blocks below the active one
 *         (empty on the last block)
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { blockIndexMeta, blocksBelow, redactedValueForBlock } from "../src/pageModel.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadPacket(relPath) {
  return JSON.parse(
    fs.readFileSync(path.resolve(__dirname, "..", "public", "projections", relPath), "utf8"),
  );
}

/** Minimal ProofBlock-shaped object for the synthetic cases. */
function mkBlock(overrides) {
  return {
    id: "b",
    kind: "generic",
    title: "Block",
    summary: "",
    source_kind: "future",
    confidence: "unknown",
    redaction_state: "unknown",
    evidence_refs: [],
    metrics: {},
    payload: undefined,
    ...overrides,
  };
}

/* ── M5: future block with a real metric ─────────────────────────────────── */

test("blockIndexMeta: REAL cache_economics (future, 7 legs) shows the legs count, not 'no claim'", () => {
  const packet = loadPacket("proof.json");
  const econ = packet.blocks.find((b) => b.id === "cache_economics");
  assert.ok(econ, "proof.json must ship a cache_economics block");
  assert.equal(econ.source_kind, "future", "cache_economics is a future block");
  assert.equal(econ.metrics.legs, 7, "and it carries 7 real legs");
  assert.deepEqual(blockIndexMeta(econ), { tone: "count", text: "7 legs" });
});

test("blockIndexMeta: a future block with no real metric still reads 'no claim'", () => {
  const block = mkBlock({ id: "cache", source_kind: "future", metrics: { hits: 0, misses: 0 } });
  assert.deepEqual(blockIndexMeta(block), { tone: "muted", text: "no claim" });
});

test("blockIndexMeta: the invocations block reports its command count", () => {
  const block = mkBlock({ id: "invocations", source_kind: "collectable_v1", metrics: { unknown: 14 } });
  assert.deepEqual(blockIndexMeta(block), { tone: "count", text: "14 cmds" });
});

test("blockIndexMeta: unsupported claims take precedence over any metric", () => {
  const block = mkBlock({
    id: "remote_execution",
    source_kind: "future",
    metrics: { legs: 3 },
    payload: { unsupported_claims: ["remote_executor_invocations", "queue_time_observed"] },
  });
  assert.deepEqual(blockIndexMeta(block), { tone: "unsupported", text: "2 unsupported" });
});

/* ── M1: redacted block honesty ──────────────────────────────────────────── */

test("redactedValueForBlock: REAL two-act artifacts (redacted, no payload) yields no value → honest 'redacted' fallback", () => {
  const packet = loadPacket("two-act/act1-proof.json");
  const artifacts = packet.blocks.find((b) => b.id === "artifacts");
  assert.ok(artifacts, "act1-proof.json must ship an artifacts block");
  assert.equal(artifacts.redaction_state, "redacted", "the artifact chain is redacted in the two-act demo");
  assert.equal(
    redactedValueForBlock(artifacts),
    undefined,
    "no payload value to surface — the header chip must show the honest 'redacted' label, never a fabricated or bare '[REDACTED]'",
  );
});

test("redactedValueForBlock: surfaces a real [REDACTED:...] payload value where one exists (keeps the slot)", () => {
  const block = mkBlock({
    redaction_state: "redacted",
    payload: { cwd: "[REDACTED:/abs/home]/project", note: "not redacted" },
  });
  assert.equal(redactedValueForBlock(block), "[REDACTED:/abs/home]/project");
});

/* ── M2: accurate "N more blocks" count ──────────────────────────────────── */

test("blocksBelow: empty on the last (or unknown) active block, accurate subset otherwise", () => {
  const blocks = ["a", "b", "c"].map((id) => ({ id }));
  assert.deepEqual(blocksBelow(blocks, "c").map((b) => b.id), [], "on the last block there is nothing below");
  assert.deepEqual(blocksBelow(blocks, "b").map((b) => b.id), ["c"]);
  assert.deepEqual(blocksBelow(blocks, "a").map((b) => b.id), ["b", "c"]);
  assert.deepEqual(blocksBelow(blocks, null).map((b) => b.id), [], "no active block → nothing claimed below");
  assert.deepEqual(blocksBelow(blocks, "missing").map((b) => b.id), []);
});
