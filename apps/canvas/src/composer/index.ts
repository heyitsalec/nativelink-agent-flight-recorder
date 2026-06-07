import { COMPONENT_CATALOG } from "./catalog";
import { applyPatch } from "./patch";
import { previewSpec } from "./preview";
import { getTemplateSpec, TEMPLATE_REFS } from "./templates";
import type {
  ApplyPatchRequest,
  ApplyPatchResponse,
  PreviewSpecRequest,
  PreviewSpecResponse,
  ValidateSpecRequest,
  ValidateSpecResponse,
} from "./types";
import { validateSpec } from "./validate";

export type {
  ApplyPatchRequest,
  ApplyPatchResponse,
  PatchOp,
  PreviewSpecRequest,
  PreviewSpecResponse,
  RenderPlan,
  ValidateSpecRequest,
  ValidateSpecResponse,
  ValidationIssue,
} from "./types";

export { COMPONENT_CATALOG, getTemplateSpec, TEMPLATE_REFS };

export function list_catalog(): {
  component_kinds: typeof COMPONENT_CATALOG;
  schema_version: "nlfr.view-spec.v1";
  count: number;
} {
  return {
    component_kinds: COMPONENT_CATALOG,
    schema_version: "nlfr.view-spec.v1",
    count: COMPONENT_CATALOG.length,
  };
}

export function list_templates(): {
  templates: typeof TEMPLATE_REFS;
} {
  return { templates: TEMPLATE_REFS };
}

export function validate_spec(request: ValidateSpecRequest): ValidateSpecResponse {
  return validateSpec(request);
}

export function preview_spec(request: PreviewSpecRequest): PreviewSpecResponse {
  return previewSpec(request);
}

export function apply_patch(request: ApplyPatchRequest): ApplyPatchResponse {
  return applyPatch(request);
}

/** Export helper: validate strict then trigger browser download when available. */
export function exportViewSpec(
  spec: ApplyPatchResponse["spec"],
  filename = "view-spec.json",
): ValidateSpecResponse {
  const validation = validate_spec({ spec, strict: true });
  if (!validation.ok) return validation;
  if (typeof window !== "undefined") {
    const blob = new Blob([JSON.stringify(spec, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  return validation;
}
