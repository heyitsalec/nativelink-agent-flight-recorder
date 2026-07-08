import type { SourceKind } from "../../../types";
import { SOURCE_KIND_META } from "./copy";
import { GLYPH_VIEWBOX, glyphShapeElements } from "./glyphShapes";

/**
 * source_kind → shape + hue, NEVER colour alone (DESIGN-SYSTEM.md §1).
 * Filled circle/diamond/triangle for recorded/computed/simulated; a dashed
 * outline circle for `future` — the dashing is the guarantee simulated/future
 * can't be mistaken for collectable. Inline SVG stays crisp at 8-11px.
 */
export function SourceGlyph({
  kind,
  size = 11,
  title,
  className,
}: {
  kind: SourceKind;
  size?: number;
  /** Override the default enum+definition tooltip (pass null to suppress). */
  title?: string | null;
  className?: string;
}) {
  const meta = SOURCE_KIND_META[kind] ?? SOURCE_KIND_META.unknown;
  const tip = title === undefined ? meta.tooltip : title;
  return (
    <svg
      className={`truth-glyph truth--${meta.tone}${className ? ` ${className}` : ""}`}
      width={size}
      height={size}
      viewBox={`0 0 ${GLYPH_VIEWBOX} ${GLYPH_VIEWBOX}`}
      role="img"
      aria-label={`source ${meta.enum}`}
      data-source-kind={meta.enum}
      focusable="false"
    >
      {tip != null && <title>{tip}</title>}
      {glyphShapeElements(meta.shape)}
    </svg>
  );
}
