/**
 * Truth-language primitives (redesign P2).
 *
 * One unified, grayscale-safe encoding of the four truth labels + agent
 * provenance, learned once and read everywhere. Presentational + reusable —
 * P3-P6 consume these; do not re-implement the encoding per panel.
 */
export { SourceGlyph } from "./SourceGlyph";
export { ConfidenceMeter } from "./ConfidenceMeter";
export { RedactionChip } from "./RedactionChip";
export { ProvenanceBadge } from "./ProvenanceBadge";
export { StatusGlyph } from "./StatusGlyph";
export { UnsupportedClaimChip } from "./UnsupportedClaimChip";
export { TruthLegend } from "./TruthLegend";
export {
  SOURCE_KIND_META,
  CONFIDENCE_META,
  REDACTION_META,
  PROVENANCE_META,
  confidenceMeta,
  redactionMeta,
  statusTone,
  statusTooltip,
} from "./copy";
export type { GlyphShape, SourceKindMeta, ConfidenceMeta, RedactionMeta, ProvenanceMeta, StatusTone } from "./copy";
export { glyphShapeElements, GLYPH_VIEWBOX } from "./glyphShapes";
