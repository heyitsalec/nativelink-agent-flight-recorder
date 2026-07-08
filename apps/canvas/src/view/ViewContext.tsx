import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle } from "lucide-react";
import { resolveBindings, type ResolvedBindings } from "../bindings/resolver";
import { layoutProjection } from "../layout";
import { deriveProjectionNotice, resolveJoinFn } from "../pageModel";
import { buildInstancePropsMap, type VisibilityContext } from "../routing/visibleWhen";
import { useViewRoute, type ViewRouteActions, type ViewRouteState } from "../routing/useViewRoute";
import { DEFAULT_VIEW_SPEC } from "./defaultViewSpec";
import { loadViewSpec } from "./loadViewSpec";
import type { ComponentInstance, ProjectionBindingJoin, ViewSpec } from "./types";

/**
 * Ephemeral UI-overlay state (redesign P7). The composer drawer and the ⌘K
 * command palette are opened from several places — the header "Composer"
 * button, the operator bar's ⌘K, and the compare lens' honest empty state —
 * so their open/closed flags live in the shared view context, NOT in any one
 * panel. This state is UI-only: it is never serialized into a projection or an
 * exported view spec (the palette is non-evidentiary by construction).
 */
export type OverlayState = {
  composerOpen: boolean;
  paletteOpen: boolean;
};

export type OverlayActions = {
  openComposer: () => void;
  closeComposer: () => void;
  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;
};

export type ViewContextValue = {
  spec: ViewSpec;
  bindings: ResolvedBindings;
  route: ViewRouteState;
  routeActions: ViewRouteActions;
  visibility: VisibilityContext;
  projectionNotice: ReturnType<typeof deriveProjectionNotice>;
  graph: ReturnType<typeof layoutProjection>;
  resolveComponentJoin: (join: ProjectionBindingJoin) => unknown;
  loading: boolean;
  error: string | null;
  reloadSpec: () => Promise<void>;
  overlay: OverlayState;
  overlayActions: OverlayActions;
};

const ViewContext = createContext<ViewContextValue | null>(null);

/** The action-graph projection filename, for the honest "Loading …" state. */
function projectionBasename(spec: ViewSpec): string {
  const graphBinding = Object.values(spec.bindings ?? {}).find(
    (binding) => binding.projection_kind === "action_graph",
  );
  const path = graphBinding?.path ?? "action-graph.json";
  return path.split("/").filter(Boolean).pop() ?? "action-graph.json";
}

export type ViewProviderProps = {
  children: ReactNode;
  specOverride?: ViewSpec;
  onZoomReset?: () => void;
};

export function ViewProvider({ children, specOverride, onZoomReset }: ViewProviderProps) {
  const [spec, setSpec] = useState<ViewSpec | null>(specOverride ?? null);
  const [bindings, setBindings] = useState<ResolvedBindings | null>(null);
  const [loading, setLoading] = useState(!specOverride);
  const [error, setError] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<OverlayState>({
    composerOpen: false,
    paletteOpen: false,
  });

  const overlayActions = useMemo<OverlayActions>(
    () => ({
      openComposer: () => setOverlay((o) => ({ ...o, composerOpen: true, paletteOpen: false })),
      closeComposer: () => setOverlay((o) => ({ ...o, composerOpen: false })),
      openPalette: () => setOverlay((o) => ({ ...o, paletteOpen: true })),
      closePalette: () => setOverlay((o) => ({ ...o, paletteOpen: false })),
      togglePalette: () => setOverlay((o) => ({ ...o, paletteOpen: !o.paletteOpen })),
    }),
    [],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextSpec = specOverride ?? (await loadViewSpec());
      const resolved = await resolveBindings(nextSpec);
      setSpec(nextSpec);
      setBindings(resolved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load view spec");
    } finally {
      setLoading(false);
    }
  }, [specOverride]);

  useEffect(() => {
    void load();
  }, [load]);

  const actionGraph = bindings?.actionGraph;
  const nodeIds = useMemo(() => actionGraph?.nodes.map((node) => node.id) ?? [], [actionGraph]);
  const runGroup = actionGraph?.run_group ?? spec?.run_group ?? "latest";

  const [route, routeActions] = useViewRoute(spec ?? DEFAULT_VIEW_SPEC, runGroup, nodeIds, {
    onZoomReset,
  });

  const graph = useMemo(
    () => (actionGraph ? layoutProjection(actionGraph) : null),
    [actionGraph],
  );

  const projectionNotice = useMemo(
    () =>
      actionGraph && bindings
        ? deriveProjectionNotice(actionGraph, bindings.usingFixtureFallback)
        : null,
    [actionGraph, bindings],
  );

  const visibility = useMemo((): VisibilityContext => {
    const instanceProps = buildInstancePropsMap(spec?.components ?? []);
    return {
      mode: route.mode,
      selectedNode: route.selectedId !== null,
      usingFixtureFallback: bindings?.usingFixtureFallback ?? false,
      viewportWidth: typeof window !== "undefined" ? window.innerWidth : 1280,
      bindingStatus: bindings?.status ?? {},
      instanceProps,
    };
  }, [spec, route.mode, route.selectedId, bindings]);

  const resolveComponentJoin = useCallback(
    (join: ProjectionBindingJoin) => {
      if (!spec || !bindings) return null;
      return resolveJoinFn(join.join_fn, bindings.values, {
        spec,
        usingFixtureFallback: bindings.usingFixtureFallback,
      });
    },
    [spec, bindings],
  );

  const value = useMemo((): ViewContextValue | null => {
    if (!spec || !bindings || !graph) return null;
    return {
      spec,
      bindings,
      route,
      routeActions,
      visibility,
      projectionNotice,
      graph,
      resolveComponentJoin,
      loading,
      error,
      reloadSpec: load,
      overlay,
      overlayActions,
    };
  }, [
    spec,
    bindings,
    graph,
    route,
    routeActions,
    visibility,
    projectionNotice,
    resolveComponentJoin,
    loading,
    error,
    load,
    overlay,
    overlayActions,
  ]);

  const loadingProjectionName = projectionBasename(spec ?? DEFAULT_VIEW_SPEC);

  if (!value) {
    return (
      <main className="app-shell app-shell--state" data-testid="nlfr-canvas-app">
        {error ? (
          <div className="system-state system-state--error" role="alert" data-testid="projection-error-state">
            <div className="system-state-head">
              <AlertTriangle size={16} aria-hidden="true" />
              <span className="system-state-title">Projection failed to parse</span>
            </div>
            <p className="system-state-detail">
              <code>{error}</code>
            </p>
            <p className="system-state-note">Nothing partial is rendered.</p>
          </div>
        ) : (
          <div className="system-state system-state--loading" role="status" data-testid="projection-loading-state">
            <div className="system-state-head">
              <span className="system-state-spinner" aria-hidden="true" />
              <span className="system-state-title">Loading {loadingProjectionName}…</span>
            </div>
            <div className="system-state-skeleton" aria-hidden="true">
              <span className="skeleton-bar" />
              <span className="skeleton-bar skeleton-bar--wide" />
              <span className="skeleton-bar" />
            </div>
          </div>
        )}
      </main>
    );
  }

  return <ViewContext.Provider value={value}>{children}</ViewContext.Provider>;
}

export function useViewContext(): ViewContextValue {
  const ctx = useContext(ViewContext);
  if (!ctx) {
    throw new Error("useViewContext must be used within ViewProvider");
  }
  return ctx;
}

export function useViewComponent(instance: ComponentInstance): unknown {
  const ctx = useViewContext();
  const binding = instance.projection_binding;
  if (!binding) return null;
  if (typeof binding === "string") {
    return ctx.bindings.values[binding] ?? null;
  }
  return ctx.resolveComponentJoin(binding);
}
