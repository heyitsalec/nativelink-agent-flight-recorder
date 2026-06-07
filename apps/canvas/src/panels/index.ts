import type { ReactNode } from "react";
import { createElement } from "react";
import type { ComponentInstance, ComponentKind } from "../view/types";
import { CHART_PANELS } from "./ChartPanel";
import { OPERATOR_PANELS } from "./OperatorPanel";
import { TABLE_PANELS } from "./TablePanel";

const PANEL_REGISTRY: Partial<Record<ComponentKind, (instance: ComponentInstance) => ReactNode>> = {
  ...CHART_PANELS,
  ...TABLE_PANELS,
  ...OPERATOR_PANELS,
};

export function renderPanel(instance: ComponentInstance): ReactNode {
  const render = PANEL_REGISTRY[instance.component_kind];
  if (!render) {
    return createElement(
      "p",
      { role: "alert" },
      "Unknown component kind: ",
      createElement("code", null, instance.component_kind),
    );
  }
  return render(instance);
}

export { CHART_PANELS, TABLE_PANELS, OPERATOR_PANELS, PANEL_REGISTRY };
