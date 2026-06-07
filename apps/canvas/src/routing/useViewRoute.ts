import { useCallback, useEffect, useRef, useState } from "react";
import type { FocusFilter } from "../types";
import type { ViewModeId, ViewSpec } from "../view/types";
import { applyModeChange, applyRunGroupChange, type SelectionState } from "./selectionReset";

export type ViewRouteState = SelectionState & {
  mode: ViewModeId;
};

export type ViewRouteActions = {
  setMode: (mode: ViewModeId) => void;
  setFocus: (focus: FocusFilter) => void;
  setSelectedId: (id: string | null) => void;
  setCommand: (command: string) => void;
  setOperatorNote: (note: string) => void;
};

const DEFAULT_OPERATOR_NOTE =
  "Ask for cache, failures, agents, proof, runway, or reset.";

export function useViewRoute(
  spec: ViewSpec,
  runGroup: string,
  nodeIds: string[],
  options?: { onZoomReset?: () => void },
): [ViewRouteState, ViewRouteActions] {
  const [mode, setModeState] = useState<ViewModeId>("graph");
  const [focus, setFocus] = useState<FocusFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [operatorNote, setOperatorNote] = useState(DEFAULT_OPERATOR_NOTE);
  const prevModeRef = useRef<ViewModeId>(mode);
  const prevRunGroupRef = useRef(runGroup);

  const setMode = useCallback(
    (nextMode: ViewModeId) => {
      const result = applyModeChange(spec, prevModeRef.current, nextMode, {
        selectedId,
        focus,
        command,
        operatorNote,
      }, nodeIds);
      setModeState(nextMode);
      setFocus(result.focus);
      setSelectedId(result.selectedId);
      setCommand(result.command);
      setOperatorNote(result.operatorNote);
      prevModeRef.current = nextMode;
    },
    [spec, selectedId, focus, command, operatorNote, nodeIds],
  );

  useEffect(() => {
    if (runGroup === prevRunGroupRef.current) return;
    const result = applyRunGroupChange(spec, operatorNote);
    setSelectedId(result.selectedId);
    setFocus(result.focus);
    setCommand(result.command);
    setOperatorNote(result.operatorNote);
    if (result.resetZoom) options?.onZoomReset?.();
    prevRunGroupRef.current = runGroup;
  }, [runGroup, spec, operatorNote, options]);

  return [
    { mode, focus, selectedId, command, operatorNote },
    {
      setMode,
      setFocus,
      setSelectedId,
      setCommand,
      setOperatorNote,
    },
  ];
}
