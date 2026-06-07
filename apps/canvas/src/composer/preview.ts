import {
  buildInstancePropsMap,
  componentsByRegion,
  type BindingStatusMap,
  type VisibilityContext,
} from "../routing/visibleWhen";
import type { BindingKey, ViewModeId, ViewSpec } from "../view/types";
import { catalogEntryFor } from "./catalog";
import type { BindingResolvedEntry, PreviewSpecRequest, PreviewSpecResponse } from "./types";

const SHELL_TESTID = "nlfr-canvas-app";

function defaultBindingStatus(bindings: ViewSpec["bindings"] | undefined): BindingStatusMap {
  const status: BindingStatusMap = {} as BindingStatusMap;
  for (const key of Object.keys(bindings ?? {})) {
    status[key as BindingKey] = "missing";
  }
  return status;
}

function resolveBindings(
  spec: Partial<ViewSpec>,
  fixtures: PreviewSpecRequest["fixtures"],
): BindingResolvedEntry[] {
  const entries: BindingResolvedEntry[] = [];
  for (const [key, binding] of Object.entries(spec.bindings ?? {})) {
    const bindingKey = key as BindingKey;
    let status: BindingResolvedEntry["status"] = "missing";
    if (fixtures?.[bindingKey]) {
      status = fixtures[bindingKey].startsWith("fixture:") ? "fixture" : "ok";
    } else if (binding.required === false) {
      status = "missing";
    } else {
      status = "ok";
    }
    entries.push({
      key: bindingKey,
      status,
      projection_kind: binding.projection_kind,
      required: binding.required !== false,
    });
  }
  return entries;
}

function collectTestIds(spec: Partial<ViewSpec>, visibleIds: Set<string>): string[] {
  const testids = new Set<string>([SHELL_TESTID]);
  for (const component of spec.components ?? []) {
    if (!visibleIds.has(component.instance_id)) continue;
    if (component.data_testid) {
      testids.add(component.data_testid);
    } else {
      const catalog = catalogEntryFor(component.component_kind);
      if (catalog?.default_testid) testids.add(catalog.default_testid);
    }
  }
  return [...testids];
}

export function previewSpec(request: PreviewSpecRequest): PreviewSpecResponse {
  const spec = request.spec;
  const mode: ViewModeId = request.mode ?? spec.modes?.[0]?.mode_id ?? "graph";
  const bindingStatus = defaultBindingStatus(spec.bindings);

  for (const entry of resolveBindings(spec, request.fixtures)) {
    bindingStatus[entry.key] = entry.status === "fixture" ? "fixture" : entry.status;
  }

  const instanceProps = buildInstancePropsMap(spec.components ?? []);
  const ctx: VisibilityContext = {
    mode,
    selectedNode: request.selected_node ?? false,
    usingFixtureFallback: Object.values(bindingStatus).some((s) => s === "fixture"),
    viewportWidth: request.viewport_width ?? 1280,
    bindingStatus,
    instanceProps,
  };

  const byRegion = componentsByRegion(spec.components ?? [], ctx);
  const regions: Record<string, string[]> = {};
  for (const [region, instances] of Object.entries(byRegion)) {
    regions[region] = instances.map((i) => i.instance_id);
  }

  const visible = Object.values(byRegion).flat();
  const visibleIds = new Set(visible.map((i) => i.instance_id));

  return {
    render_plan: {
      regions,
      bindings_resolved: resolveBindings(spec, request.fixtures),
      visible_components: visible.map((i) => i.instance_id),
      testids: collectTestIds(spec, visibleIds),
    },
  };
}
