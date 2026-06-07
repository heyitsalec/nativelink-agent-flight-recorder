import type {
  BindingKey,
  ComponentInstance,
  ProjectionBindingDirect,
  ViewSpec,
} from "../view/types";
import type { ApplyPatchRequest, ApplyPatchResponse, PatchOp, ValidationIssue } from "./types";
import { validateSpec } from "./validate";

function issue(code: string, path: string, message: string): ValidationIssue {
  return { code, path, message };
}

function cloneSpec(spec: Partial<ViewSpec>): Partial<ViewSpec> {
  return structuredClone(spec);
}

function ensureBindings(spec: Partial<ViewSpec>): Record<BindingKey, ProjectionBindingDirect> {
  if (!spec.bindings) spec.bindings = {} as Record<BindingKey, ProjectionBindingDirect>;
  return spec.bindings;
}

function ensureComponents(spec: Partial<ViewSpec>): ComponentInstance[] {
  if (!spec.components) spec.components = [];
  return spec.components;
}

function ensureModes(spec: Partial<ViewSpec>): ViewSpec["modes"] {
  if (!spec.modes) spec.modes = [];
  return spec.modes;
}

function bindingReferenced(spec: Partial<ViewSpec>, key: BindingKey): boolean {
  for (const component of spec.components ?? []) {
    const binding = component.projection_binding;
    if (binding === key) return true;
    if (binding && typeof binding === "object" && binding.kind === "join_v1") {
      if (binding.sources.includes(key)) return true;
    }
  }
  return false;
}

function clearModeComponentRefs(spec: Partial<ViewSpec>, instanceId: string): void {
  for (const mode of spec.modes ?? []) {
    if (mode.primary_component === instanceId) {
      mode.primary_component = "";
    }
    if (mode.rail_component === instanceId) {
      delete mode.rail_component;
    }
  }
}

function applySingleOp(spec: Partial<ViewSpec>, op: PatchOp): ValidationIssue[] {
  switch (op.op) {
    case "add_component": {
      const components = ensureComponents(spec);
      if (components.some((c) => c.instance_id === op.value.instance_id)) {
        return [
          issue(
            "DUPLICATE_INSTANCE_ID",
            `/components/${op.value.instance_id}`,
            `instance_id already exists: ${op.value.instance_id}`,
          ),
        ];
      }
      components.push(structuredClone(op.value));
      return [];
    }
    case "remove_component": {
      const components = ensureComponents(spec);
      const index = components.findIndex((c) => c.instance_id === op.instance_id);
      if (index < 0) {
        return [issue("SCHEMA_VIOLATION", `/components/${op.instance_id}`, "Component not found")];
      }
      components.splice(index, 1);
      clearModeComponentRefs(spec, op.instance_id);
      return [];
    }
    case "update_component": {
      const components = ensureComponents(spec);
      const index = components.findIndex((c) => c.instance_id === op.instance_id);
      if (index < 0) {
        return [issue("SCHEMA_VIOLATION", `/components/${op.instance_id}`, "Component not found")];
      }
      components[index] = { ...components[index]!, ...structuredClone(op.value), instance_id: op.instance_id };
      return [];
    }
    case "move_component": {
      const components = ensureComponents(spec);
      const component = components.find((c) => c.instance_id === op.instance_id);
      if (!component) {
        return [issue("SCHEMA_VIOLATION", `/components/${op.instance_id}`, "Component not found")];
      }
      component.region = op.region;
      return [];
    }
    case "set_binding": {
      const bindings = ensureBindings(spec);
      bindings[op.key] = structuredClone(op.value);
      return [];
    }
    case "remove_binding": {
      if (bindingReferenced(spec, op.key)) {
        return [
          issue("BINDING_IN_USE", `/bindings/${op.key}`, `Cannot remove binding still referenced by components`),
        ];
      }
      const bindings = spec.bindings;
      if (!bindings || !(op.key in bindings)) {
        return [issue("SCHEMA_VIOLATION", `/bindings/${op.key}`, "Binding not found")];
      }
      delete bindings[op.key];
      return [];
    }
    case "add_mode": {
      const modes = ensureModes(spec);
      if (modes.some((m) => m.mode_id === op.value.mode_id)) {
        return [issue("SCHEMA_VIOLATION", `/modes/${op.value.mode_id}`, "mode_id already exists")];
      }
      modes.push(structuredClone(op.value));
      return [];
    }
    case "update_mode": {
      const modes = ensureModes(spec);
      const index = modes.findIndex((m) => m.mode_id === op.mode_id);
      if (index < 0) {
        return [issue("SCHEMA_VIOLATION", `/modes/${op.mode_id}`, "Mode not found")];
      }
      modes[index] = { ...modes[index]!, ...structuredClone(op.value), mode_id: op.mode_id };
      return [];
    }
    case "remove_mode": {
      const modes = ensureModes(spec);
      const index = modes.findIndex((m) => m.mode_id === op.mode_id);
      if (index < 0) {
        return [issue("SCHEMA_VIOLATION", `/modes/${op.mode_id}`, "Mode not found")];
      }
      const modeRail = (spec.components ?? []).find((c) => c.component_kind === "mode_rail");
      const listed =
        typeof modeRail?.props?.modes === "string"
          ? modeRail.props.modes.split(",").map((s) => s.trim())
          : [];
      if (listed.includes(op.mode_id)) {
        return [
          issue(
            "MODE_REF_ORPHAN",
            `/modes/${op.mode_id}`,
            "Cannot remove mode still listed in mode_rail.props.modes",
          ),
        ];
      }
      modes.splice(index, 1);
      return [];
    }
    case "set_layout": {
      spec.layout = {
        ...(spec.layout ?? {
          kind: "grid_shell_v1",
          columns: "minmax(0,1fr) 440px",
          rows: "auto auto minmax(0,1fr) auto",
          regions: {
            notice: { grid_area: "notice", slot: "banner" },
            header: { grid_area: "header", slot: "topbar" },
            primary: { grid_area: "primary", slot: "canvas" },
            rail: { grid_area: "rail", slot: "inspector", width_px: 440 },
            operator: { grid_area: "operator", slot: "command" },
          },
          responsive: { breakpoint_px: 720, collapse_rail: "bottom_sheet" },
        }),
        ...structuredClone(op.value),
        kind: "grid_shell_v1",
      };
      return [];
    }
    case "set_envelope": {
      Object.assign(spec, structuredClone(op.value));
      return [];
    }
    case "replace_components": {
      spec.components = structuredClone(op.value);
      return [];
    }
    case "replace_bindings": {
      spec.bindings = structuredClone(op.value);
      return [];
    }
    default:
      return [issue("SCHEMA_VIOLATION", "/ops", `Unknown patch op`)];
  }
}

export function applyPatch(request: ApplyPatchRequest): ApplyPatchResponse {
  const draft = cloneSpec(request.spec);
  const batchErrors: ValidationIssue[] = [];

  for (let i = 0; i < request.ops.length; i++) {
    const opErrors = applySingleOp(draft, request.ops[i]!);
    if (opErrors.length > 0) {
      batchErrors.push(
        ...opErrors.map((err) => ({
          ...err,
          path: `/ops[${i}]${err.path === "/" ? "" : err.path}`,
        })),
      );
      return { spec: request.spec, applied: 0, errors: batchErrors };
    }
  }

  if (!request.allow_partial) {
    const validation = validateSpec({ spec: draft, strict: false });
    if (validation.errors.length > 0) {
      return { spec: request.spec, applied: 0, errors: validation.errors };
    }
  }

  return { spec: draft, applied: request.ops.length, errors: [] };
}
