import { joinFnRegistry } from "../pageModel";
import type {
  BindingKey,
  ComponentBinding,
  ComponentInstance,
  ProjectionBindingJoin,
  ViewSpec,
} from "../view/types";
import { COMPONENT_KINDS, REGION_SLOTS } from "./catalog";
import { assertComposerSourceKind } from "./templates";
import type { ValidateSpecRequest, ValidateSpecResponse, ValidationIssue } from "./types";

const REQUIRED_TOP_LEVEL = [
  "schema_version",
  "view_id",
  "title",
  "description",
  "generated_at",
  "run_group",
  "layout",
  "components",
  "bindings",
  "modes",
  "source_kind",
  "confidence",
  "evidence_refs",
  "redaction_state",
] as const;

const SECRET_PATTERNS = [
  /\bAPI[_-]?KEY\b/i,
  /\bSECRET\b/i,
  /\bPASSWORD\b/i,
  /\bTOKEN\b/i,
  /\bBearer\s+[A-Za-z0-9._-]+/,
  /\bprocess\.env\b/,
  /\$\{[A-Z_]+\}/,
  /\bsk-[A-Za-z0-9]{20,}\b/,
];

const RAW_PROMPT_MIN_LEN = 120;

function issue(code: string, path: string, message: string): ValidationIssue {
  return { code, path, message };
}

function bindingKeyFromComponent(binding: ComponentBinding | undefined): BindingKey[] {
  if (!binding) return [];
  if (typeof binding === "string") return [binding];
  return binding.sources;
}

function collectPropsStrings(value: unknown, path: string, out: { path: string; text: string }[]): void {
  if (typeof value === "string") {
    out.push({ path, text: value });
    return;
  }
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectPropsStrings(item, `${path}[${index}]`, out));
    return;
  }
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    collectPropsStrings(child, `${path}/${key}`, out);
  }
}

function validateSchemaStructure(spec: Partial<ViewSpec>, allowPartial: boolean): ValidationIssue[] {
  const errors: ValidationIssue[] = [];
  if (!allowPartial) {
    for (const field of REQUIRED_TOP_LEVEL) {
      if (spec[field as keyof ViewSpec] === undefined) {
        errors.push(issue("SCHEMA_VIOLATION", `/${field}`, `Missing required field: ${field}`));
      }
    }
  }
  if (spec.schema_version !== undefined && spec.schema_version !== "nlfr.view-spec.v1") {
    errors.push(
      issue("SCHEMA_VIOLATION", "/schema_version", `Expected nlfr.view-spec.v1, got ${spec.schema_version}`),
    );
  }
  if (spec.view_id !== undefined && !/^[a-z][a-z0-9_-]*$/.test(spec.view_id)) {
    errors.push(issue("SCHEMA_VIOLATION", "/view_id", "view_id must match ^[a-z][a-z0-9_-]*$"));
  }
  if (spec.layout?.kind !== undefined && spec.layout.kind !== "grid_shell_v1") {
    errors.push(issue("SCHEMA_VIOLATION", "/layout/kind", "layout.kind must be grid_shell_v1"));
  }
  return errors;
}

function validateCatalogMembership(components: ComponentInstance[] | undefined): ValidationIssue[] {
  if (!components) return [];
  const errors: ValidationIssue[] = [];
  for (let i = 0; i < components.length; i++) {
    const kind = components[i]?.component_kind;
    if (!kind || !COMPONENT_KINDS.has(kind)) {
      errors.push(
        issue(
          "UNKNOWN_COMPONENT_KIND",
          `/components/${i}/component_kind`,
          `Unknown component_kind: ${String(kind)}`,
        ),
      );
    }
  }
  return errors;
}

function validateDuplicateInstanceIds(components: ComponentInstance[] | undefined): ValidationIssue[] {
  if (!components) return [];
  const seen = new Map<string, number>();
  const errors: ValidationIssue[] = [];
  for (let i = 0; i < components.length; i++) {
    const id = components[i]?.instance_id;
    if (!id) continue;
    if (seen.has(id)) {
      errors.push(
        issue("DUPLICATE_INSTANCE_ID", `/components/${i}/instance_id`, `Duplicate instance_id: ${id}`),
      );
    } else {
      seen.set(id, i);
    }
  }
  return errors;
}

function validateBindingResolution(
  components: ComponentInstance[] | undefined,
  bindings: ViewSpec["bindings"] | undefined,
): ValidationIssue[] {
  if (!components) return [];
  const errors: ValidationIssue[] = [];
  const bindingKeys = new Set(Object.keys(bindings ?? {}));
  for (let i = 0; i < components.length; i++) {
    const binding = components[i]?.projection_binding;
    if (typeof binding === "string" && !bindingKeys.has(binding)) {
      errors.push(
        issue(
          "UNRESOLVED_BINDING",
          `/components/${i}/projection_binding`,
          `Binding key not in bindings: ${binding}`,
        ),
      );
    }
    if (binding && typeof binding === "object" && binding.kind === "join_v1") {
      for (const source of binding.sources) {
        if (!bindingKeys.has(source)) {
          errors.push(
            issue(
              "UNRESOLVED_BINDING",
              `/components/${i}/projection_binding/sources`,
              `Join source not in bindings: ${source}`,
            ),
          );
        }
      }
    }
  }
  return errors;
}

function validateJoinRegistry(components: ComponentInstance[] | undefined): ValidationIssue[] {
  if (!components) return [];
  const errors: ValidationIssue[] = [];
  for (let i = 0; i < components.length; i++) {
    const binding = components[i]?.projection_binding;
    if (binding && typeof binding === "object" && binding.kind === "join_v1") {
      const joinBinding = binding as ProjectionBindingJoin;
      if (!joinFnRegistry[joinBinding.join_fn]) {
        errors.push(
          issue(
            "UNKNOWN_JOIN_FN",
            `/components/${i}/projection_binding/join_fn`,
            `Unknown join_fn: ${joinBinding.join_fn}`,
          ),
        );
      }
    }
  }
  return errors;
}

function validateModeConsistency(
  components: ComponentInstance[] | undefined,
  modes: ViewSpec["modes"] | undefined,
): ValidationIssue[] {
  const errors: ValidationIssue[] = [];
  const modeIds = new Set((modes ?? []).map((mode) => mode.mode_id));
  const instanceIds = new Set((components ?? []).map((c) => c.instance_id));

  const modeRail = (components ?? []).find((c) => c.component_kind === "mode_rail");
  if (modeRail?.props?.modes && typeof modeRail.props.modes === "string") {
    const listed = modeRail.props.modes.split(",").map((s) => s.trim());
    for (const modeId of listed) {
      if (modeId && !modeIds.has(modeId as ViewSpec["modes"][number]["mode_id"])) {
        errors.push(
          issue(
            "MODE_REF_ORPHAN",
            `/components/${modeRail.instance_id}/props/modes`,
            `mode_rail lists unknown mode_id: ${modeId}`,
          ),
        );
      }
    }
  }

  for (let i = 0; i < (modes ?? []).length; i++) {
    const mode = modes![i]!;
    if (!instanceIds.has(mode.primary_component)) {
      errors.push(
        issue(
          "MODE_REF_ORPHAN",
          `/modes/${i}/primary_component`,
          `Mode ${mode.mode_id} references missing instance: ${mode.primary_component}`,
        ),
      );
    }
    if (mode.rail_component && !instanceIds.has(mode.rail_component)) {
      errors.push(
        issue(
          "MODE_REF_ORPHAN",
          `/modes/${i}/rail_component`,
          `Mode ${mode.mode_id} references missing instance: ${mode.rail_component}`,
        ),
      );
    }
  }
  return errors;
}

function validateRegionSlots(components: ComponentInstance[] | undefined): ValidationIssue[] {
  if (!components) return [];
  const errors: ValidationIssue[] = [];
  for (let i = 0; i < components.length; i++) {
    const region = components[i]?.region;
    if (region && !REGION_SLOTS.has(region)) {
      errors.push(issue("SCHEMA_VIOLATION", `/components/${i}/region`, `Invalid region slot: ${region}`));
    }
  }
  return errors;
}

function validatePrivacy(components: ComponentInstance[] | undefined): ValidationIssue[] {
  if (!components) return [];
  const errors: ValidationIssue[] = [];
  for (let i = 0; i < components.length; i++) {
    const props = components[i]?.props;
    if (!props) continue;
    const strings: { path: string; text: string }[] = [];
    collectPropsStrings(props, `/components/${i}/props`, strings);
    for (const { path, text } of strings) {
      for (const pattern of SECRET_PATTERNS) {
        if (pattern.test(text)) {
          errors.push(issue("SECRET_IN_PROPS", path, "Props contain suspected secret or env-var pattern"));
          break;
        }
      }
      if (text.length >= RAW_PROMPT_MIN_LEN && /\b(prompt|instruction|system message)\b/i.test(text)) {
        errors.push(issue("RAW_PROMPT_IN_PROPS", path, "Props may contain raw prompt text"));
      }
      if (path.endsWith("/model") || path.includes("/model")) {
        continue;
      }
      if (path.includes("prompt") && !path.includes("prompt_sha256") && text.length > 64) {
        errors.push(issue("RAW_PROMPT_IN_PROPS", path, "Agent props must use prompt_sha256 prefix only"));
      }
    }
  }
  return errors;
}

function validateComposerSourceKind(spec: Partial<ViewSpec>): ValidationIssue[] {
  if (!spec.source_kind) return [];
  if (!assertComposerSourceKind(spec.source_kind)) {
    return [
      issue(
        "SCHEMA_VIOLATION",
        "/source_kind",
        "Composer output must use derived_v1 or simulated_v1 — never collectable_v1",
      ),
    ];
  }
  return [];
}

function validateRunGroupMismatch(
  spec: Partial<ViewSpec>,
  loadedRunGroup: string | undefined,
): ValidationIssue[] {
  if (!loadedRunGroup || !spec.run_group || spec.run_group === loadedRunGroup) return [];
  return [
    issue(
      "RUN_GROUP_MISMATCH",
      "/run_group",
      `spec run_group ${spec.run_group} != action_graph ${loadedRunGroup}`,
    ),
  ];
}

function validateOrphanBindings(
  components: ComponentInstance[] | undefined,
  bindings: ViewSpec["bindings"] | undefined,
): ValidationIssue[] {
  if (!bindings) return [];
  const referenced = new Set<BindingKey>();
  for (const component of components ?? []) {
    for (const key of bindingKeyFromComponent(component.projection_binding)) {
      referenced.add(key);
    }
  }
  const warnings: ValidationIssue[] = [];
  for (const key of Object.keys(bindings)) {
    if (!referenced.has(key as BindingKey)) {
      warnings.push(
        issue("ORPHAN_BINDING", `/bindings/${key}`, `Binding defined but no component references it`),
      );
    }
  }
  return warnings;
}

function validateMissingOptionalProjection(
  bindings: ViewSpec["bindings"] | undefined,
  projectionsRoot: string | undefined,
  fixtureKeys: Set<string> | undefined,
): ValidationIssue[] {
  if (!bindings || !projectionsRoot) return [];
  const warnings: ValidationIssue[] = [];
  for (const [key, binding] of Object.entries(bindings)) {
    if (binding.required !== false) continue;
    if (fixtureKeys?.has(key)) continue;
    warnings.push(
      issue(
        "MISSING_OPTIONAL_PROJECTION",
        `/bindings/${key}/path`,
        `Optional binding path not resolved at ${projectionsRoot}${binding.path}`,
      ),
    );
  }
  return warnings;
}

export function validateSpec(request: ValidateSpecRequest): ValidateSpecResponse {
  const spec = request.spec;
  const allowPartial = !request.strict;
  const errors: ValidationIssue[] = [];
  const warnings: ValidationIssue[] = [];

  errors.push(...validateSchemaStructure(spec, allowPartial));
  errors.push(...validateCatalogMembership(spec.components));
  errors.push(...validateDuplicateInstanceIds(spec.components));
  errors.push(...validateBindingResolution(spec.components, spec.bindings));
  errors.push(...validateJoinRegistry(spec.components));
  errors.push(...validateModeConsistency(spec.components, spec.modes));
  errors.push(...validateRegionSlots(spec.components));
  errors.push(...validatePrivacy(spec.components));
  errors.push(...validateComposerSourceKind(spec));

  warnings.push(...validateRunGroupMismatch(spec, request.loaded_run_group));
  warnings.push(...validateOrphanBindings(spec.components, spec.bindings));
  warnings.push(
    ...validateMissingOptionalProjection(spec.bindings, request.projections_root, undefined),
  );

  if (request.strict) {
    errors.push(...warnings);
    return { ok: errors.length === 0, errors, warnings: [] };
  }

  return { ok: errors.length === 0, errors, warnings };
}

export function isFullViewSpec(spec: Partial<ViewSpec>): spec is ViewSpec {
  const result = validateSpec({ spec, strict: true });
  return result.ok;
}
