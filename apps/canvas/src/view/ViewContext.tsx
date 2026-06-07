import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { resolveBindings, type ResolvedBindings } from "../bindings/resolver";
import { layoutProjection } from "../layout";
import { deriveProjectionNotice, resolveJoinFn } from "../pageModel";
import { buildInstancePropsMap, type VisibilityContext } from "../routing/visibleWhen";
import { useViewRoute, type ViewRouteActions, type ViewRouteState } from "../routing/useViewRoute";
import { DEFAULT_VIEW_SPEC } from "./defaultViewSpec";
import { loadViewSpec } from "./loadViewSpec";
import type { ComponentInstance, ProjectionBindingJoin, ViewSpec } from "./types";

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
};

const ViewContext = createContext<ViewContextValue | null>(null);

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
  ]);

  if (!value) {
    return (
      <main className="app-shell" data-testid="nlfr-canvas-app">
        {error ? <p role="alert">{error}</p> : <p role="status">Loading view spec…</p>}
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
