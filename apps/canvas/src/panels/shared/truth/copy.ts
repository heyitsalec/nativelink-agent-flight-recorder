/**
 * Truth-language copy + metadata (redesign P2).
 *
 * One canonical source for the human labels, shapes, and tooltip strings that
 * every truth primitive renders. Tooltips always name the RAW enum first so
 * the honest machine label is one hover away from every glyph/meter/chip
 * (DESIGN-SYSTEM.md §"The Truth Language"). P3-P6 consume these — do not
 * fork the strings per-panel.
 */

import type { Confidence, RedactionState, SourceKind } from "../../../types";
import type { ProvenanceClass } from "../../../receiptModel";

/** The four glyph shapes. `future`/`unknown` are NEVER filled — the dashed/
 *  hollow geometry is the guarantee they cannot read as `collectable`. */
export type GlyphShape = "circle" | "diamond" | "triangle" | "dashed-circle" | "dotted-circle";

export type SourceKindMeta = {
  /** Machine enum, e.g. "collectable_v1". */
  enum: SourceKind;
  /** Grayscale-safe shape. */
  shape: GlyphShape;
  /** CSS modifier suffix: truth--collectable etc. */
  tone: "collectable" | "derived" | "simulated" | "future" | "unknown";
  /** Human label shown beside the glyph in the legend. */
  label: string;
  /** Faint one-line descriptor. */
  descriptor: string;
  /** Full tooltip: raw enum + definition. */
  tooltip: string;
};

export const SOURCE_KIND_META: Record<SourceKind, SourceKindMeta> = {
  collectable_v1: {
    enum: "collectable_v1",
    shape: "circle",
    tone: "collectable",
    label: "Recorded",
    descriptor: "captured from real tool output",
    tooltip: "source_kind: collectable_v1 — recorded directly from real process/tool output",
  },
  derived_v1: {
    enum: "derived_v1",
    shape: "diamond",
    tone: "derived",
    label: "Computed",
    descriptor: "computed from recorded artifacts",
    tooltip: "source_kind: derived_v1 — computed from recorded artifacts, not observed directly",
  },
  simulated_v1: {
    enum: "simulated_v1",
    shape: "triangle",
    tone: "simulated",
    label: "Simulated",
    descriptor: "deterministic fixture",
    tooltip: "source_kind: simulated_v1 — deterministic fixture, not real evidence",
  },
  future: {
    enum: "future",
    shape: "dashed-circle",
    tone: "future",
    label: "Not yet collected",
    descriptor: "claim not yet collected",
    tooltip: "source_kind: future — not yet collected; never claimed as observed",
  },
  unknown: {
    enum: "unknown",
    shape: "dotted-circle",
    tone: "unknown",
    label: "Unknown",
    descriptor: "no source recorded",
    tooltip: "source_kind: unknown — no source label recorded",
  },
};

export type ConfidenceMeta = {
  /** Filled bar count, 0-3. */
  filled: number;
  /** True when the meter should render a mono "?" suffix. */
  showUnknown: boolean;
  tooltip: string;
};

export const CONFIDENCE_META: Record<Confidence, ConfidenceMeta> = {
  high: { filled: 3, showUnknown: false, tooltip: "confidence: high ▮▮▮" },
  medium: { filled: 2, showUnknown: false, tooltip: "confidence: medium ▮▮" },
  low: { filled: 1, showUnknown: false, tooltip: "confidence: low ▮" },
  unknown: { filled: 0, showUnknown: true, tooltip: "confidence: unknown ?" },
};

export function confidenceMeta(value: string | null | undefined): ConfidenceMeta {
  if (value === "high" || value === "medium" || value === "low" || value === "unknown") {
    return CONFIDENCE_META[value];
  }
  return CONFIDENCE_META.unknown;
}

export type RedactionMeta = {
  tone: "safe" | "redacted" | "blocked" | "unknown";
  label: string;
  tooltip: string;
};

export const REDACTION_META: Record<RedactionState, RedactionMeta> = {
  safe: {
    tone: "safe",
    label: "safe",
    tooltip: "redaction_state: safe — value carries no withheld secret",
  },
  redacted: {
    tone: "redacted",
    label: "redacted",
    tooltip: "redaction_state: redacted — a secret was withheld; the slot is kept, not dropped",
  },
  blocked: {
    tone: "blocked",
    label: "blocked",
    tooltip: "redaction_state: blocked — value withheld entirely and never rendered",
  },
  unknown: {
    tone: "unknown",
    label: "unknown",
    tooltip: "redaction_state: unknown — no redaction label recorded",
  },
};

export function redactionMeta(value: string | null | undefined): RedactionMeta {
  if (value === "safe" || value === "redacted" || value === "blocked" || value === "unknown") {
    return REDACTION_META[value];
  }
  return REDACTION_META.unknown;
}

/** Provenance classes reuse the SAME shape families so agent provenance is not
 *  a fourth language: verified→collectable circle, asserted→derived diamond,
 *  stub→simulated triangle. */
export type ProvenanceMeta = {
  tone: "verified" | "asserted" | "stub";
  shape: GlyphShape;
  /** Truth tone driving the tint/hue. */
  family: SourceKindMeta["tone"];
  label: string;
  tooltip: string;
};

export const PROVENANCE_META: Record<ProvenanceClass, ProvenanceMeta> = {
  receipt_verified_v1: {
    tone: "verified",
    shape: "circle",
    family: "collectable",
    label: "verified",
    tooltip: "provenance_class: receipt_verified_v1 — live CLI receipt, hashes recomputable",
  },
  operator_asserted_v1: {
    tone: "asserted",
    shape: "diamond",
    family: "derived",
    label: "asserted",
    tooltip: "provenance_class: operator_asserted_v1 — asserted by operator, no CLI receipt",
  },
  stub_receipt_v1: {
    tone: "stub",
    shape: "triangle",
    family: "simulated",
    label: "stub",
    tooltip: "provenance_class: stub_receipt_v1 — deterministic stub CLI, not a live model",
  },
};

/** Status → glyph, not colour alone. Red is rationed to recorded failures. */
export type StatusTone = "pass" | "fail" | "neutral";

/**
 * Genuine failure markers (word-bounded). Fail-tone always wins when any of
 * these is present — a recorded failure earns the red glyph.
 */
const HARD_NEGATIVE = [
  /\bfail(ed|ure|ing|s)?\b/,
  /\berror(ed|s)?\b/,
  /\bcancel(l?ed|l?ing|s)?\b/,
  /\babort(ed|ing|s)?\b/,
  /\btime(d)?[\s-]?out\b/,
  /\bunsuccessful\b/,
  /\bdenied\b/,
  /\bblocked\b/,
  /\bbroke(n)?\b/,
  /\bcrash(ed|es|ing)?\b/,
  /\bkilled\b/,
  /\brejected\b/,
];

/**
 * A positive word negated ("not ok", "not completed", "no success"). These
 * must NEVER read as pass; they are also not necessarily recorded failures, so
 * they resolve to the honest, non-committal NEUTRAL rather than red.
 */
const NEGATED_POSITIVE =
  /\b(?:not|no|never|n['’]t|without|non[-\s]?)\s*(?:yet\s+)?(?:ok|okay|complete[d]?|pass(?:ed)?|success(?:ful)?|succeed(?:ed)?|done|finished?|ready)\b/;

/** Unambiguous positives (word-bounded). Only these earn a pass — and only
 *  when no hard-negative and no negation is present. */
const POSITIVE = [
  /\bcomplete[d]?\b/,
  /\bpass(ed)?\b/,
  /\bsuccess(ful)?\b/,
  /\bsucceed(ed)?\b/,
  /\bok\b/,
  /\bokay\b/,
  /\bdone\b/,
  /\bfinished\b/,
  /\bhealthy\b/,
  /\bready\b/,
];

/** Parse an explicit exit code ("exit 0", "exit code 1", "exited: 2"). */
const EXIT_CODE = /\bexit(?:ed)?(?:\s*code)?\s*[:=]?\s*(-?\d+)\b/;

/**
 * Robust status → tone. Ordering encodes the honesty rule "never round UP to
 * pass": a real failure wins first; a negated positive drops to neutral; an
 * exit code / bare number is judged by 0-vs-nonzero; only an unambiguous,
 * un-negated positive earns pass; everything else is neutral.
 */
export function statusTone(status: string | number | null | undefined): StatusTone {
  if (typeof status === "number") {
    if (!Number.isFinite(status)) return "neutral";
    return status === 0 ? "pass" : "fail";
  }

  const value = String(status ?? "").trim().toLowerCase();
  if (!value) return "neutral";

  // A recorded failure always wins — red is warranted here.
  if (HARD_NEGATIVE.some((re) => re.test(value))) return "fail";

  // "not ok" / "not completed" etc. — never pass, but not an assertable
  // failure either → neutral (when uncertain, never round up).
  if (NEGATED_POSITIVE.test(value)) return "neutral";

  // Explicit exit code: 0 passes, nonzero is a recorded failure.
  const exitMatch = value.match(EXIT_CODE);
  if (exitMatch) return Number(exitMatch[1]) === 0 ? "pass" : "fail";

  // Bare integer status behaves like an exit code.
  if (/^-?\d+$/.test(value)) return Number(value) === 0 ? "pass" : "fail";

  // Unambiguous, un-negated positive.
  if (POSITIVE.some((re) => re.test(value))) return "pass";

  return "neutral";
}

export function statusTooltip(status: string | number | null | undefined): string {
  const value = String(status ?? "unknown");
  const tone = statusTone(status);
  if (tone === "fail") return `status: ${value} — recorded failure`;
  if (tone === "pass") return `status: ${value} — recorded pass`;
  return `status: ${value}`;
}
