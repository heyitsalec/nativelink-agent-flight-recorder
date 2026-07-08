import { CircleSlash } from "lucide-react";

/**
 * Unsupported-claims chip (DESIGN-SYSTEM.md §"Unsupported-claims chip"):
 * named, not hidden. Mono, failure colour, slash-circle icon — e.g.
 * `⊘ worker identity`. This is one of the only two surfaces (with recorded
 * failures) where red is allowed.
 */
export function UnsupportedClaimChip({ claim }: { claim: string }) {
  return (
    <span
      className="unsupported-chip"
      data-unsupported-claim={claim}
      title={`unsupported claim: ${claim} — named explicitly, never silently dropped`}
    >
      <CircleSlash size={11} aria-hidden="true" />
      <span>{claim}</span>
    </span>
  );
}
