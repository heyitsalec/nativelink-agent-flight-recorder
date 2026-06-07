import { createContext, useContext, useMemo, useRef, type MutableRefObject, type ReactNode } from "react";
import { zoomIdentity, type ZoomTransform } from "d3";

export type ZoomController = {
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
  getTransform: () => ZoomTransform;
};

const ZoomContext = createContext<MutableRefObject<ZoomController | null> | null>(null);

export type ZoomProviderProps = {
  children: ReactNode;
  controllerRef: MutableRefObject<ZoomController | null>;
};

export function ZoomProvider({ children, controllerRef }: ZoomProviderProps) {
  const value = useMemo(() => controllerRef, [controllerRef]);
  return <ZoomContext.Provider value={value}>{children}</ZoomContext.Provider>;
}

export function useZoomControllerRef(): MutableRefObject<ZoomController | null> {
  const ctx = useContext(ZoomContext);
  if (!ctx) {
    throw new Error("useZoomControllerRef must be used within ZoomProvider");
  }
  return ctx;
}

export function useOptionalZoomControllerRef(): MutableRefObject<ZoomController | null> | null {
  return useContext(ZoomContext);
}

export const defaultZoomTransform = zoomIdentity;
