import { Check, TriangleAlert, CircleDashed } from "lucide-react";
import { statusTone, statusTooltip } from "./copy";

/**
 * Status → glyph, not colour alone (DESIGN-SYSTEM.md §5). pass = teal check,
 * fail = alert in failure red. RED IS RATIONED — only recorded failures light
 * up red; a neutral/"not observed" status is slate-dashed and calm, never red.
 */
export function StatusGlyph({
  status,
  showLabel = true,
  title,
}: {
  status: string | number | null | undefined;
  showLabel?: boolean;
  title?: string | null;
}) {
  const tone = statusTone(status);
  const label = String(status ?? "unknown");
  const tip = title === undefined ? statusTooltip(status) : title;
  const tooltip = tip ?? undefined;

  const icon =
    tone === "fail" ? (
      <TriangleAlert size={12} aria-hidden="true" />
    ) : tone === "pass" ? (
      <Check size={12} aria-hidden="true" />
    ) : (
      <CircleDashed size={12} aria-hidden="true" />
    );

  return (
    <span className={`status-glyph status--${tone}`} data-status-tone={tone} title={tooltip}>
      {icon}
      {showLabel && <span className="status-glyph-label">{label}</span>}
    </span>
  );
}
