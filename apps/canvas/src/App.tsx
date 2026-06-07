import { useCallback, useRef } from "react";
import { GridShell } from "./layout/GridShell";
import { renderPanel } from "./panels";
import { ZoomProvider, type ZoomController } from "./panels/shared/ZoomContext";
import { ViewProvider, useViewContext } from "./view/ViewContext";

function CanvasGrid() {
  const ctx = useViewContext();
  return (
    <GridShell
      spec={ctx.spec}
      visibility={ctx.visibility}
      renderComponent={(instance) => renderPanel(instance)}
    />
  );
}

export function App() {
  const zoomRef = useRef<ZoomController | null>(null);
  const onZoomReset = useCallback(() => {
    zoomRef.current?.reset();
  }, []);

  return (
    <ViewProvider onZoomReset={onZoomReset}>
      <ZoomProvider controllerRef={zoomRef}>
        <CanvasGrid />
      </ZoomProvider>
    </ViewProvider>
  );
}
