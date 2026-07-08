import { Check, Lock, HelpCircle, CircleSlash } from "lucide-react";
import type { RedactionState } from "../../../types";
import { redactionMeta } from "./copy";

/**
 * redaction_state → treatment on the VALUE itself (DESIGN-SYSTEM.md §3).
 *
 * - safe: quiet check + muted "safe", no chrome on the value.
 * - redacted: lock chip carrying the redacted mono value (e.g.
 *   `[REDACTED:abs_path]/bazel-test.log`); withheld ≠ missing, the slot stays.
 * - blocked: solid inverted chip, value NEVER rendered.
 * - unknown: dotted-border chip + "?".
 *
 * `value` is the (already-redacted) string to display for the redacted case;
 * when omitted the chip renders the state label alone (truth-grid cells).
 */
export function RedactionChip({
  state,
  value,
  title,
}: {
  state: RedactionState;
  value?: string | null;
  title?: string | null;
}) {
  const meta = redactionMeta(state);
  const tip = title === undefined ? meta.tooltip : title;
  const tooltip = tip ?? undefined;

  if (meta.tone === "safe") {
    return (
      <span className="redaction redaction--safe" data-redaction-state={state} title={tooltip}>
        <Check size={12} aria-hidden="true" />
        <span>safe</span>
      </span>
    );
  }

  if (meta.tone === "redacted") {
    return (
      <span className="redaction redaction--redacted" data-redaction-state={state} title={tooltip}>
        <Lock size={12} aria-hidden="true" />
        <code>{value ?? "[REDACTED]"}</code>
      </span>
    );
  }

  if (meta.tone === "blocked") {
    // Value is withheld entirely — never rendered, even if one was passed.
    return (
      <span className="redaction redaction--blocked" data-redaction-state={state} title={tooltip}>
        <CircleSlash size={12} aria-hidden="true" />
        <span>blocked</span>
      </span>
    );
  }

  return (
    <span className="redaction redaction--unknown" data-redaction-state={state} title={tooltip}>
      <HelpCircle size={12} aria-hidden="true" />
      <span>unknown</span>
    </span>
  );
}
