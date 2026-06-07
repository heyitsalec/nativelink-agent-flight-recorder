import { MessageCircle, Search } from "lucide-react";
import type { ComponentInstance } from "../view/types";
import { useViewContext } from "../view/ViewContext";
import { useOptionalZoomControllerRef } from "./shared/ZoomContext";
import { stringProp } from "./shared/props";

export function OperatorCommandBarPanel(instance: ComponentInstance) {
  const { graph, bindings, route, routeActions } = useViewContext();
  const zoomRef = useOptionalZoomControllerRef();
  const placeholder = stringProp(instance.props, "placeholder", "focus cache misses");

  function runOperatorCommand() {
    const value = route.command.trim().toLowerCase();
    if (!value) return;

    if (value.includes("cache")) {
      routeActions.setFocus("cache");
      routeActions.setMode("graph");
      routeActions.setOperatorNote("Cache evidence is highlighted; derived events stay amber.");
    } else if (value.includes("fail")) {
      routeActions.setFocus("failures");
      routeActions.setMode("graph");
      const firstFailure = graph.nodes.find((node) => node.kind === "failure");
      routeActions.setSelectedId(firstFailure?.id ?? null);
      routeActions.setOperatorNote("Failure path is isolated with its evidence refs open.");
    } else if (value.includes("proof")) {
      routeActions.setMode("proof");
      routeActions.setFocus("derived");
      routeActions.setOperatorNote("Proof lens is open; unsupported claims remain explicit.");
    } else if (value.includes("remote") || value.includes("worker") || value.includes("execution")) {
      routeActions.setMode("remote");
      routeActions.setFocus("remote");
      routeActions.setOperatorNote("Remote boundary is isolated; worker claims stay gated.");
    } else if (value.includes("agent") || value.includes("loop") || value.includes("change")) {
      routeActions.setFocus("agent");
      routeActions.setMode("graph");
      const firstAgent = graph.nodes.find((node) => node.kind === "agent");
      routeActions.setSelectedId(firstAgent?.id ?? null);
      routeActions.setOperatorNote(
        "Agent loop is isolated: agent and change evidence stays simulated until collected.",
      );
    } else if (value.includes("compare") || value.includes("diff")) {
      routeActions.setMode("compare");
      routeActions.setFocus("derived");
      routeActions.setOperatorNote(
        bindings.compareProjection
          ? "Compare lens shows derived proof-packet deltas only."
          : "Compare lens unavailable — compare-projection.json not loaded.",
      );
    } else if (value.includes("runway") || value.includes("timeline")) {
      routeActions.setMode("runway");
      routeActions.setFocus("all");
      routeActions.setOperatorNote("Validation runway is projected over the same graph evidence.");
    } else {
      routeActions.setMode("graph");
      routeActions.setFocus("all");
      routeActions.setSelectedId(null);
      zoomRef?.current?.reset();
      routeActions.setOperatorNote("Canvas reset to the full Action Graph.");
    }
    routeActions.setCommand("");
  }

  return (
    <div className="operator">
      <MessageCircle size={18} />
      <div className="operator-copy">
        <span>{route.operatorNote}</span>
        <input
          aria-label="operator command"
          value={route.command}
          placeholder={placeholder}
          onChange={(event) => routeActions.setCommand(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") runOperatorCommand();
          }}
        />
      </div>
      <button
        className="operator-run"
        onClick={runOperatorCommand}
        aria-label="Run operator command"
      >
        <Search size={17} />
      </button>
    </div>
  );
}

export type OperatorPanelKind = "operator_command_bar";

export const OPERATOR_PANELS: Record<
  OperatorPanelKind,
  (instance: ComponentInstance) => React.ReactNode
> = {
  operator_command_bar: OperatorCommandBarPanel,
};
