/**
 * Grayscale-safe glyph geometry (redesign P2).
 *
 * One 12-unit viewBox, drawn with `currentColor` so the caller owns the hue
 * via a `truth--<tone>` class. Shared by the HTML <SourceGlyph> primitive and
 * the SVG graph node so the shape language is byte-identical on the canvas and
 * in the panels. Filled shapes (circle/diamond/triangle) vs. dashed/dotted
 * outlines (future/unknown) are what survive desaturation.
 */
import type { GlyphShape } from "./copy";

export const GLYPH_VIEWBOX = 12;

/** SVG child nodes for a shape, sized to the 12-unit viewBox. */
export function glyphShapeElements(shape: GlyphShape): React.ReactNode {
  switch (shape) {
    case "circle":
      return <circle cx={6} cy={6} r={4.3} fill="currentColor" />;
    case "diamond":
      return (
        <path
          d="M6 1.5 L10.5 6 L6 10.5 L1.5 6 Z"
          fill="currentColor"
          stroke="currentColor"
          strokeWidth={0.6}
          strokeLinejoin="round"
        />
      );
    case "triangle":
      return (
        <path
          d="M6 1.7 L10.7 10.3 L1.3 10.3 Z"
          fill="currentColor"
          stroke="currentColor"
          strokeWidth={0.6}
          strokeLinejoin="round"
        />
      );
    case "dashed-circle":
      return (
        <circle
          cx={6}
          cy={6}
          r={4.1}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.55}
          strokeDasharray="2.1 1.7"
        />
      );
    case "dotted-circle":
      return (
        <circle
          cx={6}
          cy={6}
          r={4.1}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.3}
          strokeDasharray="0.1 1.9"
          strokeLinecap="round"
        />
      );
    default:
      return null;
  }
}
