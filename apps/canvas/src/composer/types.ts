import type {
  BindingKey,
  ComponentInstance,
  GridShellLayout,
  ModeLens,
  ProjectionBindingDirect,
  ViewModeId,
  ViewSpec,
} from "../view/types";

export type ValidationIssue = {
  code: string;
  path: string;
  message: string;
};

export type ValidateSpecRequest = {
  spec: Partial<ViewSpec> | ViewSpec;
  projections_root?: string;
  strict?: boolean;
  /** Loaded action_graph.run_group for mismatch warning */
  loaded_run_group?: string;
};

export type ValidateSpecResponse = {
  ok: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
};

export type PreviewSpecRequest = {
  spec: Partial<ViewSpec> | ViewSpec;
  projections_root?: string;
  mode?: ViewModeId;
  fixtures?: Record<BindingKey, string>;
  selected_node?: boolean;
  viewport_width?: number;
};

export type BindingResolvedEntry = {
  key: BindingKey;
  status: "ok" | "missing" | "fixture";
  projection_kind?: string;
  required: boolean;
};

export type RenderPlan = {
  regions: Record<string, string[]>;
  bindings_resolved: BindingResolvedEntry[];
  visible_components: string[];
  testids: string[];
};

export type PreviewSpecResponse = {
  render_plan: RenderPlan;
};

export type PatchOp =
  | { op: "add_component"; value: ComponentInstance }
  | { op: "remove_component"; instance_id: string }
  | { op: "update_component"; instance_id: string; value: Partial<ComponentInstance> }
  | { op: "move_component"; instance_id: string; region: ComponentInstance["region"] }
  | { op: "set_binding"; key: BindingKey; value: ProjectionBindingDirect }
  | { op: "remove_binding"; key: BindingKey }
  | { op: "add_mode"; value: ModeLens }
  | { op: "update_mode"; mode_id: ViewModeId; value: Partial<ModeLens> }
  | { op: "remove_mode"; mode_id: ViewModeId }
  | { op: "set_layout"; value: Partial<GridShellLayout> }
  | {
      op: "set_envelope";
      value: Partial<
        Pick<
          ViewSpec,
          | "title"
          | "description"
          | "run_group"
          | "source_kind"
          | "confidence"
          | "evidence_refs"
          | "redaction_state"
          | "view_id"
          | "generated_at"
        >
      >;
    }
  | { op: "replace_components"; value: ComponentInstance[] }
  | { op: "replace_bindings"; value: Record<BindingKey, ProjectionBindingDirect> };

export type ApplyPatchRequest = {
  spec: Partial<ViewSpec> | ViewSpec;
  ops: PatchOp[];
  allow_partial?: boolean;
};

export type ApplyPatchResponse = {
  spec: Partial<ViewSpec> | ViewSpec;
  applied: number;
  errors: ValidationIssue[];
};
