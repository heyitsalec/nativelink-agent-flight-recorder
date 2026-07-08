import type { ProvenanceBadge as ProvenanceBadgeModel } from "../../../receiptModel";
import { PROVENANCE_META } from "./copy";
import { GLYPH_VIEWBOX, glyphShapeElements } from "./glyphShapes";

/**
 * provenance_class → SAME shape/hue families as source_kind (DESIGN-SYSTEM.md
 * §4) so agent provenance is not a fourth language: verified→collectable
 * circle, asserted→derived diamond, stub→simulated triangle. Pill badge with
 * a tint bg + tinted border. Consumes the shared receiptModel badge so the
 * live-receipt affordance and honest hint stay 1:1 with recorded fields.
 */
export function ProvenanceBadge({ badge }: { badge: ProvenanceBadgeModel }) {
  const meta = PROVENANCE_META[badge.provenanceClass];
  const tooltip = badge.hint;

  return (
    <span
      className={`provenance-chip provenance--${badge.tone}`}
      data-provenance-class={badge.provenanceClass}
      title={tooltip}
    >
      <svg
        className={`truth-glyph truth--${meta.family}`}
        width={11}
        height={11}
        viewBox={`0 0 ${GLYPH_VIEWBOX} ${GLYPH_VIEWBOX}`}
        aria-hidden="true"
        focusable="false"
      >
        {glyphShapeElements(meta.shape)}
      </svg>
      {badge.live && <span className="provenance-live-dot" aria-label="live receipt" />}
      <span>{badge.label}</span>
    </span>
  );
}
