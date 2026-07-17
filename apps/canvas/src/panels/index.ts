import type { FunctionComponent, ReactNode } from "react";
import { createElement } from "react";
import type { ComponentInstance, ComponentKind } from "../view/types";
import { CHART_PANELS } from "./ChartPanel";
import { OPERATOR_PANELS } from "./OperatorPanel";
import { REPLAY_PANELS } from "./ReplayPanel";
import { TABLE_PANELS } from "./TablePanel";

const PANEL_REGISTRY: Partial<Record<ComponentKind, FunctionComponent<ComponentInstance>>> = {
  ...CHART_PANELS,
  ...TABLE_PANELS,
  ...OPERATOR_PANELS,
  ...REPLAY_PANELS,
};

export function renderPanel(instance: ComponentInstance): ReactNode {
  const Panel = PANEL_REGISTRY[instance.component_kind];
  if (!Panel) {
    return createElement(
      "p",
      { role: "alert" },
      "Unknown component kind: ",
      createElement("code", null, instance.component_kind),
    );
  }
  // Render as a React element (not a bare function call) so each panel owns
  // its own hooks list. Calling Panel(instance) inline attributed every
  // panel's hooks to GridShell and broke the Rules of Hooks whenever
  // selection toggled which panels are visible.
  return createElement(Panel, instance);
}

export { CHART_PANELS, TABLE_PANELS, OPERATOR_PANELS, REPLAY_PANELS, PANEL_REGISTRY };
