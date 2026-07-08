import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import type { ComponentInstance, RegionSlot, ViewSpec } from "../view/types";
import { componentsByRegion, type VisibilityContext } from "../routing/visibleWhen";

export type GridShellProps = {
  spec: ViewSpec;
  visibility: VisibilityContext;
  renderComponent: (instance: ComponentInstance) => ReactNode;
};

// The rail is NOT a flow region in the redesign (P6): the graph is full-width
// and the rail's panels float as fixed overlays. So the grid lays out only
// notice/header/primary/operator in a single column.
const FLOW_REGIONS: RegionSlot[] = ["notice", "header", "primary", "operator"];

function shellGridStyle(spec: ViewSpec): CSSProperties {
  const { layout } = spec;
  return {
    display: "grid",
    // Single full-width column — the reserved 440px rail column is gone; the
    // primary graph fills the viewport and lenses float over it (P6).
    gridTemplateColumns: "minmax(0, 1fr)",
    gridTemplateRows: layout.rows,
    gridTemplateAreas: '"notice" "header" "primary" "operator"',
    minHeight: "100vh",
    width: "100vw",
    position: "relative",
    overflow: "hidden",
  };
}

function regionStyle(region: RegionSlot, spec: ViewSpec): CSSProperties {
  const gridArea = spec.layout.regions[region].grid_area;
  // The header region is a full-bleed block; the .topbar bar owns its own
  // flex layout (P3 shell). The tool rail floats out of the header via
  // position:fixed, and the zoom-controls slot is hidden by CSS.
  return { gridArea, position: "relative", minWidth: 0 };
}

export function GridShell({ spec, visibility, renderComponent }: GridShellProps) {
  const [viewportWidth, setViewportWidth] = useState(
    () => (typeof window !== "undefined" ? window.innerWidth : 1280),
  );

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const ctx = useMemo(
    () => ({ ...visibility, viewportWidth }),
    [visibility, viewportWidth],
  );

  const collapsed = viewportWidth < spec.layout.responsive.breakpoint_px;
  const byRegion = componentsByRegion(spec.components, ctx);
  const railComponents = byRegion.rail ?? [];

  const renderSlot = (instance: ComponentInstance) => (
    <div
      key={instance.instance_id}
      className={`grid-slot grid-slot-${instance.component_kind}`}
      data-instance-id={instance.instance_id}
      data-testid={instance.data_testid}
    >
      {renderComponent(instance)}
    </div>
  );

  return (
    <main
      className="app-shell grid-shell"
      data-testid="nlfr-canvas-app"
      data-view-id={spec.view_id}
      style={shellGridStyle(spec)}
    >
      {FLOW_REGIONS.map((region) => (
        <section
          key={region}
          className={`grid-region grid-region-${region}`}
          data-region={region}
          aria-label={region}
          style={regionStyle(region, spec)}
        >
          {(byRegion[region] ?? []).map(renderSlot)}
        </section>
      ))}
      {/* Rail lenses float over the full-width graph (P6). On desktop this is a
          fixed, pointer-events-none overlay layer; each lens' grid-slot wrapper
          positions itself (right drawer / centered panel) and re-enables pointer
          events. On mobile the rail collapses into the bottom sheet (P8). */}
      {railComponents.length > 0 &&
        (collapsed ? (
          <aside
            className="grid-rail-bottom-sheet"
            data-region="rail"
            data-collapsed="true"
            aria-label="rail"
            style={{
              position: "fixed",
              left: 0,
              right: 0,
              bottom: 72,
              zIndex: 6,
              maxHeight: "45vh",
              overflow: "auto",
            }}
          >
            {railComponents.map(renderSlot)}
          </aside>
        ) : (
          <div className="grid-region grid-region-rail" data-region="rail" aria-label="rail">
            {railComponents.map(renderSlot)}
          </div>
        ))}
    </main>
  );
}
