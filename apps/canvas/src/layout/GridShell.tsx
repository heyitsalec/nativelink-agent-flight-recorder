import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import type { ComponentInstance, RegionSlot, ViewSpec } from "../view/types";
import { componentsByRegion, type VisibilityContext } from "../routing/visibleWhen";

export type GridShellProps = {
  spec: ViewSpec;
  visibility: VisibilityContext;
  renderComponent: (instance: ComponentInstance) => ReactNode;
};

const REGION_ORDER: RegionSlot[] = ["notice", "header", "primary", "rail", "operator"];

function shellGridStyle(spec: ViewSpec, collapsed: boolean): CSSProperties {
  const { layout } = spec;
  return {
    display: "grid",
    gridTemplateColumns: collapsed ? "1fr" : layout.columns,
    gridTemplateRows: layout.rows,
    gridTemplateAreas: collapsed
      ? '"notice" "header" "primary" "operator"'
      : '"notice notice" "header header" "primary rail" "operator operator"',
    minHeight: "100vh",
    width: "100vw",
    position: "relative",
    overflow: "hidden",
  };
}

function regionStyle(region: RegionSlot, spec: ViewSpec, collapsed: boolean): CSSProperties {
  const gridArea = spec.layout.regions[region].grid_area;
  const base: CSSProperties = {
    gridArea,
    position: "relative",
    minWidth: 0,
  };
  if (region === "rail" && !collapsed && spec.layout.regions.rail.width_px) {
    base.width = spec.layout.regions.rail.width_px;
  }
  // The header region is a full-bleed block; the .topbar bar owns its own
  // flex layout (P3 shell). The tool rail floats out of the header via
  // position:fixed, and the zoom-controls slot is hidden by CSS.
  return base;
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

  return (
    <main
      className="app-shell grid-shell"
      data-testid="nlfr-canvas-app"
      data-view-id={spec.view_id}
      style={shellGridStyle(spec, collapsed)}
    >
      {REGION_ORDER.filter((region) => region !== "rail" || !collapsed).map((region) => (
        <section
          key={region}
          className={`grid-region grid-region-${region}`}
          data-region={region}
          aria-label={region}
          style={regionStyle(region, spec, collapsed)}
        >
          {(byRegion[region] ?? []).map((instance) => (
            <div
              key={instance.instance_id}
              className={`grid-slot grid-slot-${instance.component_kind}`}
              data-instance-id={instance.instance_id}
              data-testid={instance.data_testid}
            >
              {renderComponent(instance)}
            </div>
          ))}
        </section>
      ))}
      {collapsed && railComponents.length > 0 && (
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
          {railComponents.map((instance) => (
            <div
              key={instance.instance_id}
              className={`grid-slot grid-slot-${instance.component_kind}`}
              data-instance-id={instance.instance_id}
              data-testid={instance.data_testid}
            >
              {renderComponent(instance)}
            </div>
          ))}
        </aside>
      )}
    </main>
  );
}
