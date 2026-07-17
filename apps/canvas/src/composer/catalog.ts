import type { ComponentKind, RegionSlot } from "../view/types";

export type CatalogPropSchema = Record<
  string,
  { type: "boolean" | "string" | "number"; default?: boolean | string | number }
>;

export type CatalogEntry = {
  kind: ComponentKind;
  region: RegionSlot;
  default_testid: string;
  binding_required: boolean;
  props_schema: CatalogPropSchema;
};

/** v1 component catalog — 16 kinds from docs/design/component-catalog.md */
export const COMPONENT_CATALOG: CatalogEntry[] = [
  {
    kind: "projection_notice",
    region: "notice",
    default_testid: "projection-notice",
    binding_required: true,
    props_schema: {
      tones: { type: "string", default: "fallback,collectable,simulated,mixed" },
    },
  },
  {
    kind: "topbar_summary",
    region: "header",
    default_testid: "topbar-summary",
    binding_required: true,
    props_schema: {
      show_remote_label: { type: "boolean", default: true },
    },
  },
  {
    kind: "mode_rail",
    region: "header",
    default_testid: "canvas-mode-rail",
    binding_required: false,
    props_schema: {
      modes: { type: "string", default: "graph,runway,proof,remote,compare,replay" },
    },
  },
  {
    kind: "zoom_controls",
    region: "header",
    default_testid: "zoom-controls",
    binding_required: false,
    props_schema: {
      target_instance_id: { type: "string", default: "graph-main" },
      always_visible: { type: "boolean", default: false },
    },
  },
  {
    kind: "action_graph_canvas",
    region: "primary",
    default_testid: "action-graph-svg",
    binding_required: true,
    props_schema: {
      show_truth_legend: { type: "boolean", default: false },
      zoom_controls: { type: "boolean", default: true },
      highlight_focus: { type: "string", default: "{focus}" },
      dimmed: { type: "boolean", default: false },
    },
  },
  {
    kind: "truth_legend",
    region: "primary",
    default_testid: "truth-legend",
    binding_required: false,
    props_schema: {
      items: { type: "string", default: "collectable_v1,derived_v1,simulated_v1,future" },
    },
  },
  {
    kind: "proof_constellation",
    region: "primary",
    default_testid: "proof-constellation",
    binding_required: true,
    props_schema: {
      scope_block_id: { type: "string", default: "scope" },
    },
  },
  {
    kind: "evidence_inspector",
    region: "rail",
    default_testid: "evidence-inspector",
    binding_required: true,
    props_schema: {
      close_on_mode_change: { type: "boolean", default: true },
    },
  },
  {
    kind: "validation_runway",
    region: "primary",
    default_testid: "validation-runway",
    binding_required: true,
    props_schema: {
      lane_order: {
        type: "string",
        default: "run,invocation,target,action,cache_event,failure,artifact",
      },
    },
  },
  {
    kind: "proof_drawer",
    region: "rail",
    default_testid: "proof-drawer",
    binding_required: true,
    props_schema: {
      render_blocks_as: { type: "string", default: "proof_block_card" },
    },
  },
  {
    kind: "proof_block_card",
    region: "rail",
    default_testid: "proof-block-card",
    binding_required: true,
    props_schema: {
      block_id: { type: "string", default: "scope" },
    },
  },
  {
    kind: "remote_boundary_lens",
    region: "rail",
    default_testid: "remote-execution-lens",
    binding_required: true,
    props_schema: {
      remote_block_id: { type: "string", default: "remote_execution" },
      worker_block_title: { type: "string", default: "Worker Readiness Boundary" },
    },
  },
  {
    kind: "compare_lens",
    region: "rail",
    default_testid: "compare-lens",
    binding_required: true,
    props_schema: {
      empty_state_path_hint: { type: "string", default: "/projections/compare-projection.json" },
    },
  },
  {
    kind: "compare_dimension_card",
    region: "rail",
    default_testid: "compare-dimension-card",
    binding_required: true,
    props_schema: {
      dimension_id: { type: "string", default: "agent_provenance" },
    },
  },
  {
    kind: "replay_timeline",
    region: "rail",
    default_testid: "replay-lens",
    binding_required: true,
    props_schema: {
      empty_state_path_hint: { type: "string", default: "/projections/timeline.json" },
    },
  },
  {
    kind: "operator_command_bar",
    region: "operator",
    default_testid: "operator-chat",
    binding_required: false,
    props_schema: {
      placeholder: { type: "string", default: "focus cache misses" },
      commands: { type: "string", default: "cache,fail,proof,remote,agent,compare,replay,runway,reset" },
    },
  },
];

export const COMPONENT_KINDS = new Set(COMPONENT_CATALOG.map((entry) => entry.kind));

export const REGION_SLOTS = new Set(["notice", "header", "primary", "rail", "operator"] as const);

export function catalogEntryFor(kind: ComponentKind): CatalogEntry | undefined {
  return COMPONENT_CATALOG.find((entry) => entry.kind === kind);
}
