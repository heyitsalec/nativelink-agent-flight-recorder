/**
 * Unit test for statusTone (truth-language honesty guard, redesign P2).
 *
 * Guards the "never round UP to pass" rule: a status must never render the
 * teal pass check unless it is an unambiguous, un-negated positive. Run with
 * `npm --prefix apps/canvas run test:unit` (Node strips the TS types on
 * import). Imports the source directly so the shipped function is under test.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { statusTone } from "../src/panels/shared/truth/copy.ts";

test("unambiguous positives → pass", () => {
  for (const s of ["completed", "PASSED", "success", "succeeded", "ok", "done", "0", "exit 0", 0]) {
    assert.equal(statusTone(s), "pass", `${JSON.stringify(s)} should be pass`);
  }
});

test("negated positives never pass (neutral — not a recorded failure)", () => {
  for (const s of ["not ok", "not completed", "not passed", "no success", "not yet completed"]) {
    assert.notEqual(statusTone(s), "pass", `${JSON.stringify(s)} must not read as pass`);
    assert.equal(statusTone(s), "neutral", `${JSON.stringify(s)} should be neutral`);
  }
});

test("recorded failures → fail", () => {
  for (const s of ["failed", "error", "unsuccessful", "cancelled", "canceled", "aborted", "timed out", "timeout", "3", "exit 1", 3, -1]) {
    assert.equal(statusTone(s), "fail", `${JSON.stringify(s)} should be fail`);
  }
});

test("negative markers are never over-toned to pass", () => {
  // The specific redteam cases: each must be fail or neutral, never pass.
  for (const s of ["unsuccessful", "not ok", "not completed", "cancelled", "aborted", "timed out", "3"]) {
    assert.notEqual(statusTone(s), "pass", `${JSON.stringify(s)} must never render a pass check`);
  }
});

test("unknown / empty / nullish → neutral", () => {
  for (const s of ["unknown", "", "   ", null, undefined, "pending", "queued", "running", NaN]) {
    assert.equal(statusTone(s), "neutral", `${JSON.stringify(s)} should be neutral`);
  }
});

test("substring false-positives are rejected (word boundaries)", () => {
  // "unsuccessful" contains "success"; "broken" contains no positive word we
  // accept — both must not pass.
  assert.notEqual(statusTone("unsuccessful"), "pass");
  assert.equal(statusTone("broken"), "fail");
});
