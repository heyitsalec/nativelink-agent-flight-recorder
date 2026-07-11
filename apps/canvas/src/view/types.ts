import type { Confidence, FocusFilter, RedactionState, SourceKind } from "../types";

export type ViewModeId = "graph" | "runway" | "proof" | "remote" | "compare" | "replay";

export type RegionSlot = "notice" | "header" | "primary" | "rail" | "operator";

export type ComponentKind =
  | "projection_notice"
  | "topbar_summary"
  | "mode_rail"
  | "action_graph_canvas"
  | "evidence_inspector"
  | "validation_runway"
  | "proof_constellation"
  | "proof_drawer"
  | "proof_block_card"
  | "remote_boundary_lens"
  | "compare_lens"
  | "compare_dimension_card"
  | "replay_timeline"
  | "truth_legend"
  | "operator_command_bar"
  | "zoom_controls";

export type ProjectionKind =
  | "action_graph"
  | "proof_packet"
  | "compare"
  | "timeline"
  | "runway"
  | "run_group_index";

export type FallbackPolicy = `fixture:${string}` | "none";

export type RefreshPolicy = "manual" | "on_run_group_change";

export type BindingKey = `binding.${string}`;

export type ProjectionBindingDirect = {
  projection_kind: ProjectionKind;
  path: string;
  required?: boolean;
  selector?: string;
  fallback?: FallbackPolicy;
  refresh?: RefreshPolicy;
  notes?: string;
};

export type ProjectionBindingJoin = {
  kind: "join_v1";
  sources: BindingKey[];
  join_fn: string;
  source_kind: SourceKind;
  confidence: Confidence;
  evidence_refs: string[];
  redaction_state: RedactionState;
};

export type ProjectionBinding = ProjectionBindingDirect | ProjectionBindingJoin;

export type ComponentBinding = BindingKey | ProjectionBindingJoin;

export type VisibleWhen = {
  mode?: ViewModeId[];
  mode_not?: ViewModeId[];
  selected_node?: boolean;
  binding_present?: BindingKey;
  binding_missing_ok?: BindingKey;
  fixture_fallback?: boolean;
  viewport_min_px?: number;
  viewport_max_px?: number;
  prop_truthy?: string;
};

export type ComponentProps = Record<string, boolean | string | number | null>;

export type ComponentInstance = {
  instance_id: string;
  component_kind: ComponentKind;
  region: RegionSlot;
  props?: ComponentProps;
  projection_binding?: ComponentBinding;
  visible_when?: VisibleWhen;
  data_testid?: string;
};

export type ModeLens = {
  mode_id: ViewModeId;
  label: string;
  icon: string;
  primary_component: string;
  rail_component?: string;
  default_focus: FocusFilter;
  requires_binding?: BindingKey;
  data_testid?: string;
};

export type GridRegion = {
  grid_area: string;
  slot: string;
  width_px?: number;
};

export type GridShellLayout = {
  kind: "grid_shell_v1";
  columns: string;
  rows: string;
  regions: Record<RegionSlot, GridRegion>;
  responsive: {
    breakpoint_px: number;
    collapse_rail: "bottom_sheet";
  };
};

export type ViewSpec = {
  schema_version: "nlfr.view-spec.v1";
  view_id: string;
  title: string;
  description: string;
  generated_at: string;
  run_group: string;
  layout: GridShellLayout;
  components: ComponentInstance[];
  bindings: Record<BindingKey, ProjectionBindingDirect>;
  modes: ModeLens[];
  source_kind: SourceKind;
  confidence: Confidence;
  evidence_refs: string[];
  redaction_state: RedactionState;
};

export type BindingResolveStatus = "ok" | "missing" | "fixture";

export type ResolvedBindingEntry = {
  key: BindingKey;
  status: BindingResolveStatus;
  value: unknown;
  required: boolean;
};

export type ProjectionNoticeTone = "fallback" | "collectable" | "simulated" | "mixed";

export type ProjectionNotice = {
  tone: ProjectionNoticeTone;
  message: string;
} | null;
