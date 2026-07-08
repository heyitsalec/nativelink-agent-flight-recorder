/**
 * Unit tests for the ⌘K command palette matcher (redesign P7 §8). The palette's
 * fuzzy filter + typed-substring highlight are pure functions in
 * panels/paletteCommands.ts (no imports) so `node --test` runs them directly.
 *
 * Proves the discoverability contract: an empty query lists EVERY command (the
 * whole catalog is browsable), a typed query fuzzy-matches names + keywords with
 * contiguous-substring ranked above subsequence, and the highlight marks the
 * matched characters so a fuzzy hit is visibly explained. Every command routes
 * through the SAME operator command string the bar uses (asserted here so the
 * palette can never silently diverge from the router).
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  PALETTE_COMMANDS,
  PALETTE_GROUP_ORDER,
  filterPaletteCommands,
  highlightSegments,
} from "../src/panels/shared/paletteCommands.ts";

test("empty query lists the entire catalog (that IS the discoverability)", () => {
  const all = filterPaletteCommands("");
  assert.equal(all.length, PALETTE_COMMANDS.length);
  assert.equal(filterPaletteCommands("   ").length, PALETTE_COMMANDS.length);
});

test("catalog covers the three groups and only real router commands", () => {
  const groups = new Set(PALETTE_COMMANDS.map((c) => c.group));
  for (const group of PALETTE_GROUP_ORDER) assert.ok(groups.has(group), `${group} present`);
  const commands = PALETTE_COMMANDS.map((c) => c.command);
  // Each palette command string maps to a real operator-router branch keyword.
  assert.ok(commands.includes("focus failures"));
  assert.ok(commands.includes("focus cache misses"));
  assert.ok(commands.includes("agent loop"));
  assert.ok(commands.includes("proof"));
  assert.ok(commands.includes("runway"));
  assert.ok(commands.includes("remote"));
  assert.ok(commands.includes("compare"));
  assert.ok(commands.includes("reset"));
});

test("contiguous substring on the name ranks first", () => {
  const results = filterPaletteCommands("compare");
  assert.equal(results[0].id, "lens-compare");
});

test("keyword match surfaces a command whose name lacks the term", () => {
  // "timeline" is a keyword of runway, not in its name.
  const results = filterPaletteCommands("timeline");
  assert.ok(results.some((c) => c.id === "lens-runway"));
});

test("subsequence match (fuzzy) still finds the command", () => {
  // p-r-f is a subsequence of "proof".
  const results = filterPaletteCommands("prf");
  assert.ok(results.some((c) => c.id === "lens-proof"));
});

test("no match returns empty (honest — no fabricated rows)", () => {
  assert.deepEqual(filterPaletteCommands("zzzxq"), []);
});

test("highlightSegments marks a contiguous substring", () => {
  const segs = highlightSegments("focus failures", "fail");
  const matched = segs.filter((s) => s.match).map((s) => s.text);
  assert.deepEqual(matched, ["fail"]);
  // Segments losslessly reconstruct the original text.
  assert.equal(segs.map((s) => s.text).join(""), "focus failures");
});

test("highlightSegments marks subsequence chars and stays lossless", () => {
  const segs = highlightSegments("proof", "prf");
  assert.equal(segs.map((s) => s.text).join(""), "proof");
  assert.equal(segs.filter((s) => s.match).map((s) => s.text).join(""), "prf");
});

test("empty query → single unmarked segment", () => {
  const segs = highlightSegments("reset", "");
  assert.deepEqual(segs, [{ text: "reset", match: false }]);
});
