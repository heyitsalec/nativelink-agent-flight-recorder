import { useMemo, useState } from "react";
import { ChevronUp, TerminalSquare } from "lucide-react";
import { mobileSummary, remoteLensModel } from "../../pageModel";
import { useViewContext } from "../../view/ViewContext";
import { SourceGlyph, TruthLegend } from "./truth";
import type { SourceKind } from "../../types";

/**
 * Mobile bottom sheet (redesign P8, board 1m). The mobile replacement for the
 * desktop operator bar + floating truth legend: an E3 sheet pinned to the
 * bottom with a grab handle. Collapsed it shows the four source glyphs, a
 * "Truth legend" toggle (chevron expands the full P2 <TruthLegend/>), a primary
 * "Commands" ink pill that opens the ⌘K palette FULL-SCREEN, and a one-line
 * honest summary of the SAME recorded projection (never fabricated). The legend
 * is reachable here — it is NOT hidden on mobile, only relocated off the graph.
 *
 * Rendered (portaled to <body>) by the operator panel and shown only at mobile
 * widths via CSS (`@media max-width:720px`); at desktop it is display:none, so
 * desktop layout and the truth-guard (which runs at 1440px) are untouched.
 */
const SHEET_GLYPHS: SourceKind[] = [
  "collectable_v1",
  "derived_v1",
  "simulated_v1",
  "future",
];

export function MobileBottomSheet() {
  const { bindings, overlayActions } = useViewContext();
  const [expanded, setExpanded] = useState(false);

  const projection = bindings.actionGraph;
  const remoteLens = useMemo(
    () => remoteLensModel(projection, bindings.proofPacket),
    [projection, bindings.proofPacket],
  );
  const remoteInvocations =
    remoteLens.metrics.find((m) => m.label === "remote invocations")?.value ?? "0";
  const remoteObserved = remoteInvocations !== "0" && remoteInvocations !== "n/a";
  const summary = mobileSummary(projection.summary, projection.nodes.length, remoteObserved);

  return (
    <aside
      className={`mobile-sheet${expanded ? " mobile-sheet--expanded" : ""}`}
      data-testid="mobile-bottom-sheet"
      data-expanded={expanded}
      aria-label="mobile canvas sheet"
    >
      <span className="mobile-sheet-grab" aria-hidden="true" />
      <div className="mobile-sheet-row">
        <button
          type="button"
          className="mobile-sheet-legend-toggle"
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse truth legend" : "Expand truth legend"}
          data-testid="mobile-legend-toggle"
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="mobile-sheet-glyphs" aria-hidden="true">
            {SHEET_GLYPHS.map((kind) => (
              <SourceGlyph key={kind} kind={kind} size={13} title={null} />
            ))}
          </span>
          <span className="mobile-sheet-legend-label">Truth legend</span>
          <ChevronUp
            size={16}
            aria-hidden="true"
            className="mobile-sheet-chevron"
          />
        </button>
        <button
          type="button"
          className="mobile-sheet-commands"
          data-testid="mobile-commands"
          onClick={() => overlayActions.openPalette()}
        >
          <TerminalSquare size={14} aria-hidden="true" />
          <span>Commands</span>
        </button>
      </div>

      {expanded && (
        <div className="mobile-sheet-legend" data-testid="mobile-legend">
          <TruthLegend />
        </div>
      )}

      <p className="mobile-sheet-summary" data-testid="mobile-summary" role="status">
        {summary}
      </p>
    </aside>
  );
}
