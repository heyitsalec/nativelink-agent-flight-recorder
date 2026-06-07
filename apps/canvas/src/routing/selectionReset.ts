import type { FocusFilter } from "../types";
import type { ViewModeId, ViewSpec } from "../view/types";

export type SelectionState = {
  selectedId: string | null;
  focus: FocusFilter;
  command: string;
  operatorNote: string;
};

export type ModeChangeResult = {
  focus: FocusFilter;
  selectedId: string | null;
  command: string;
  operatorNote: string;
};

export type RunGroupChangeResult = {
  selectedId: null;
  focus: FocusFilter;
  command: string;
  operatorNote: string;
  resetZoom: boolean;
};

const INSPECTOR_MODES: ViewModeId[] = ["graph", "runway"];
const LENS_MODES: ViewModeId[] = ["proof", "remote", "compare"];

function defaultFocusForMode(spec: ViewSpec, mode: ViewModeId): FocusFilter {
  const lens = spec.modes.find((entry) => entry.mode_id === mode);
  return lens?.default_focus ?? "all";
}

function selectionInProjection(selectedId: string | null, nodeIds: string[]): boolean {
  if (!selectedId) return false;
  return nodeIds.includes(selectedId);
}

export function applyModeChange(
  spec: ViewSpec,
  prevMode: ViewModeId,
  nextMode: ViewModeId,
  state: SelectionState,
  nodeIds: string[],
): ModeChangeResult {
  const focus = defaultFocusForMode(spec, nextMode);
  let selectedId = state.selectedId;

  if (LENS_MODES.includes(nextMode)) {
    selectedId = null;
  } else if (
    INSPECTOR_MODES.includes(nextMode) &&
    INSPECTOR_MODES.includes(prevMode) &&
    selectionInProjection(selectedId, nodeIds)
  ) {
    // graph ↔ runway inspector continuity
  } else if (INSPECTOR_MODES.includes(nextMode) && !selectionInProjection(selectedId, nodeIds)) {
    selectedId = null;
  }

  return {
    focus,
    selectedId,
    command: "",
    operatorNote: state.operatorNote,
  };
}

export function applyRunGroupChange(
  _spec: ViewSpec,
  operatorNote: string,
): RunGroupChangeResult {
  return {
    selectedId: null,
    focus: "all",
    command: "",
    operatorNote,
    resetZoom: true,
  };
}

export function shouldClearSelectionOnModeEnter(nextMode: ViewModeId): boolean {
  return LENS_MODES.includes(nextMode);
}

export function preservesInspectorSelection(prevMode: ViewModeId, nextMode: ViewModeId): boolean {
  return INSPECTOR_MODES.includes(prevMode) && INSPECTOR_MODES.includes(nextMode);
}
