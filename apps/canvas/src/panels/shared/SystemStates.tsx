import { X, MousePointerClick } from "lucide-react";
import { focusLabel, focusMatchCount } from "../../pageModel";
import { useViewContext } from "../../view/ViewContext";

/**
 * Non-blocking system-state overlays (redesign P7 §9, board 1l):
 *
 *  - Focus applied — a dismissible pill naming the active focus filter and the
 *    HONEST match count ("N of M nodes match"). An empty match SAYS "0 of M";
 *    the graph dims non-matches but never silently hides evidence.
 *  - Resting / no selection — a calm, pointer-through hint inviting the operator
 *    to open a node's evidence dossier. Only shown on the resting graph (no
 *    focus, no selection) so it never competes with an active filter or lens.
 *
 * Both are portaled above the canvas by the operator panel. Neither is
 * evidence; they reflect ephemeral route state only.
 */
export function SystemStates() {
  const { route, routeActions, bindings } = useViewContext();
  const nodes = bindings.actionGraph.nodes;
  const total = nodes.length;

  const focusActive = route.focus !== "all";
  const restingHint =
    route.mode === "graph" && route.selectedId === null && route.focus === "all";

  return (
    <>
      {focusActive && (
        <div className="focus-pill" role="status" data-testid="focus-applied">
          <button
            type="button"
            className="focus-pill-tag"
            aria-label={`Clear focus: ${focusLabel(route.focus)}`}
            onClick={() => routeActions.setFocus("all")}
          >
            <span className="focus-pill-label">focus: {focusLabel(route.focus)}</span>
            <X size={12} aria-hidden="true" />
          </button>
          <span className="focus-pill-count" data-testid="focus-match-count">
            {focusMatchCount(nodes, route.focus)} of {total} node{total === 1 ? "" : "s"} match
          </span>
        </div>
      )}

      {restingHint && (
        <div className="resting-hint" role="note" data-testid="resting-hint" aria-hidden="true">
          <span className="resting-hint-plate">
            <MousePointerClick size={16} />
          </span>
          <span className="resting-hint-text">Select any node to open its evidence dossier</span>
        </div>
      )}
    </>
  );
}
