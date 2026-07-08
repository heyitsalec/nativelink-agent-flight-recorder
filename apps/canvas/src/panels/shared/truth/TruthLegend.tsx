import { Lock } from "lucide-react";
import type { SourceKind } from "../../../types";
import { SOURCE_KIND_META } from "./copy";
import { SourceGlyph } from "./SourceGlyph";
import { ConfidenceMeter } from "./ConfidenceMeter";

/**
 * The truth legend (DESIGN-SYSTEM.md board 1b): teaches ALL FOUR truth labels
 * in one place — the four source_kinds (glyph + human label + faint
 * descriptor, tooltip carries the raw enum) plus a bottom row that names the
 * confidence meter, the redaction lock, and the provenance ●◆▲ trio. `⌘L`
 * keycap advertises the toggle.
 */
const LEGEND_SOURCE_ORDER: SourceKind[] = [
  "collectable_v1",
  "derived_v1",
  "simulated_v1",
  "future",
];

export function TruthLegend({ items }: { items?: SourceKind[] }) {
  const kinds =
    items && items.length ? LEGEND_SOURCE_ORDER.filter((k) => items.includes(k)) : LEGEND_SOURCE_ORDER;

  return (
    <aside className="truth-legend" aria-label="truth label legend">
      <div className="truth-legend-header">
        <span className="truth-legend-title">Truth legend</span>
        <kbd className="truth-legend-key" aria-hidden="true">⌘L</kbd>
      </div>
      <ul className="truth-legend-sources">
        {kinds.map((kind) => {
          const meta = SOURCE_KIND_META[kind];
          return (
            <li key={kind} data-source-kind={kind} title={meta.tooltip}>
              <SourceGlyph kind={kind} size={13} title={null} />
              <span className="truth-legend-label">{meta.label}</span>
              <span className="truth-legend-hint">{meta.descriptor}</span>
            </li>
          );
        })}
      </ul>
      <div className="truth-legend-divider" />
      <div className="truth-legend-encodings">
        <span className="truth-legend-encoding" title="confidence: high ▮▮▮ · medium ▮▮ · low ▮ · unknown ?">
          <ConfidenceMeter confidence="high" title={null} />
          <span className="truth-legend-encoding-label">Confidence</span>
        </span>
        <span
          className="truth-legend-encoding"
          title="redaction_state: safe · redacted (lock chip) · blocked · unknown"
        >
          <Lock className="truth-legend-lock" size={13} aria-hidden="true" />
          <span className="truth-legend-encoding-label">Redaction</span>
        </span>
        <span
          className="truth-legend-encoding"
          title="provenance_class reuses the source shapes: ● verified · ◆ asserted · ▲ stub"
        >
          <span className="truth-legend-provenance-trio" aria-hidden="true">
            <SourceGlyph kind="collectable_v1" size={11} title={null} />
            <SourceGlyph kind="derived_v1" size={11} title={null} />
            <SourceGlyph kind="simulated_v1" size={11} title={null} />
          </span>
          <span className="truth-legend-encoding-label">Provenance</span>
        </span>
      </div>
    </aside>
  );
}
