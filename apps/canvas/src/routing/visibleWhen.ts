import type { BindingKey, ComponentInstance, ViewModeId, VisibleWhen } from "../view/types";

export type BindingStatusMap = Record<BindingKey, "ok" | "missing" | "fixture">;

export type VisibilityContext = {
  mode: ViewModeId;
  selectedNode: boolean;
  usingFixtureFallback: boolean;
  viewportWidth: number;
  bindingStatus: BindingStatusMap;
  /** instance_id → merged props for prop_truthy resolution */
  instanceProps: Record<string, Record<string, unknown>>;
};

function bindingResolved(status: BindingStatusMap[BindingKey] | undefined): boolean {
  return status === "ok" || status === "fixture";
}

function evaluateRule(rule: VisibleWhen, ctx: VisibilityContext): boolean {
  if (rule.mode && !rule.mode.includes(ctx.mode)) return false;
  if (rule.mode_not && rule.mode_not.includes(ctx.mode)) return false;
  if (rule.selected_node === true && !ctx.selectedNode) return false;
  if (rule.selected_node === false && ctx.selectedNode) return false;
  if (rule.fixture_fallback === true && !ctx.usingFixtureFallback) return false;
  if (rule.fixture_fallback === false && ctx.usingFixtureFallback) return false;
  if (rule.viewport_min_px !== undefined && ctx.viewportWidth < rule.viewport_min_px) return false;
  if (rule.viewport_max_px !== undefined && ctx.viewportWidth > rule.viewport_max_px) return false;
  if (rule.binding_present && !bindingResolved(ctx.bindingStatus[rule.binding_present])) return false;
  if (rule.binding_missing_ok) {
    const status = ctx.bindingStatus[rule.binding_missing_ok];
    if (status === "missing") return true;
    if (!bindingResolved(status)) return false;
  }
  if (rule.prop_truthy) {
    const propValue = findPropTruthyValue(rule.prop_truthy, ctx.instanceProps);
    if (!propValue) return false;
  }
  return true;
}

function findPropTruthyValue(
  propKey: string,
  instanceProps: Record<string, Record<string, unknown>>,
): unknown {
  for (const props of Object.values(instanceProps)) {
    if (propKey in props && props[propKey]) {
      return props[propKey];
    }
  }
  return undefined;
}

export function isComponentVisible(instance: ComponentInstance, ctx: VisibilityContext): boolean {
  if (!instance.visible_when) return true;
  return evaluateRule(instance.visible_when, ctx);
}

export function visibleComponents(
  components: ComponentInstance[],
  ctx: VisibilityContext,
): ComponentInstance[] {
  return components.filter((instance) => isComponentVisible(instance, ctx));
}

export function componentsByRegion(
  components: ComponentInstance[],
  ctx: VisibilityContext,
): Record<string, ComponentInstance[]> {
  const visible = visibleComponents(components, ctx);
  const grouped: Record<string, ComponentInstance[]> = {};
  for (const instance of visible) {
    if (!grouped[instance.region]) grouped[instance.region] = [];
    grouped[instance.region].push(instance);
  }
  return grouped;
}

export function buildInstancePropsMap(components: ComponentInstance[]): Record<string, Record<string, unknown>> {
  const map: Record<string, Record<string, unknown>> = {};
  for (const instance of components) {
    map[instance.instance_id] = { ...(instance.props ?? {}) };
  }
  return map;
}
