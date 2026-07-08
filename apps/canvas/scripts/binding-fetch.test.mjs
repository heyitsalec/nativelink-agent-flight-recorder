/**
 * Unit tests for the binding-fetch honesty helpers (redesign P7 V4, board 1l).
 * These are the pure decision + copy functions the resolver uses to tell a
 * MISSING projection (unreachable / 404 → labeled fixture fallback, honest)
 * apart from a MALFORMED one (fetched OK but not valid JSON → honest ERROR
 * state, "Nothing partial is rendered"). They live in pageModel.ts (type-only
 * imports) so `node --test` can import them directly.
 *
 * The honesty contract: a CORRUPT projection must never be dressed up as the
 * bundled fixture fallback, and the error DETAIL must be curated human copy —
 * never a raw JS exception / stack string.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { classifyBindingFetch, projectionParseDetail } from "../src/pageModel.ts";

test("classifyBindingFetch: a network throw is MISSING (→ labeled fallback)", () => {
  assert.equal(
    classifyBindingFetch({ networkError: true, responseOk: false, parsedOk: false }),
    "missing",
  );
});

test("classifyBindingFetch: a non-2xx status is MISSING (→ labeled fallback)", () => {
  assert.equal(
    classifyBindingFetch({ networkError: false, responseOk: false, parsedOk: false }),
    "missing",
  );
});

test("classifyBindingFetch: fetched OK but unparseable is MALFORMED (→ honest error)", () => {
  assert.equal(
    classifyBindingFetch({ networkError: false, responseOk: true, parsedOk: false }),
    "malformed",
  );
});

test("classifyBindingFetch: fetched OK and parsed is OK", () => {
  assert.equal(
    classifyBindingFetch({ networkError: false, responseOk: true, parsedOk: true }),
    "ok",
  );
});

test("classifyBindingFetch: missing and malformed are distinct (never conflated)", () => {
  const missing = classifyBindingFetch({ networkError: false, responseOk: false, parsedOk: false });
  const malformed = classifyBindingFetch({ networkError: false, responseOk: true, parsedOk: false });
  assert.notEqual(missing, malformed);
});

test("projectionParseDetail: names the file and is honest human copy", () => {
  const detail = projectionParseDetail(
    "/projections/proof.json",
    new SyntaxError("Unexpected token < in JSON at position 214"),
  );
  assert.match(detail, /^proof\.json/, "leads with the projection basename");
  assert.match(detail, /invalid JSON/);
  assert.match(detail, /character 214/, "surfaces the reported position honestly");
});

test("projectionParseDetail: never leaks a raw JS exception / stack string", () => {
  const detail = projectionParseDetail(
    "/projections/action-graph.json",
    new SyntaxError("Unexpected token < in JSON at position 5"),
  );
  assert.ok(!/SyntaxError|Unexpected token/.test(detail), "raw exception text is not surfaced");
  assert.match(detail, /^action-graph\.json — invalid JSON near character 5$/);
});

test("projectionParseDetail: omits position when the engine gives none", () => {
  const detail = projectionParseDetail("/projections/compare-projection.json", new Error("bad"));
  assert.equal(detail, "compare-projection.json — invalid JSON");
});
