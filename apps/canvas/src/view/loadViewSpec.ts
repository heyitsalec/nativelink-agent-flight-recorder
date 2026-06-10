import { withBase } from "../lib/basePath";
import { DEFAULT_VIEW_SPEC, getBundledViewSpec } from "./defaultViewSpec";
import { readStoredViewSpec } from "./persistViewSpec";
import type { ViewSpec } from "./types";

function viewIdFromQuery(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("view");
}

async function fetchRemoteViewSpec(viewId: string): Promise<ViewSpec | null> {
  try {
    const response = await fetch(withBase(`/views/${viewId}.json`));
    if (!response.ok) return null;
    const spec = (await response.json()) as ViewSpec;
    if (spec.schema_version !== "nlfr.view-spec.v1") return null;
    return spec;
  } catch {
    return null;
  }
}

/**
 * View spec load precedence:
 * 1. Query `?view=<view_id>` — bundled template or `/views/<view_id>.json`
 * 2. `localStorage` key `nlfr.view-spec`
 * 3. Bundled `nlfr-default-v0`
 */
export async function loadViewSpec(): Promise<ViewSpec> {
  const queryViewId = viewIdFromQuery();
  if (queryViewId) {
    const bundled = getBundledViewSpec(queryViewId);
    if (bundled) return bundled;
    const remote = await fetchRemoteViewSpec(queryViewId);
    if (remote) return remote;
  }

  const stored = readStoredViewSpec();
  if (stored) return stored;

  return DEFAULT_VIEW_SPEC;
}

export function isViewSpec(value: unknown): value is ViewSpec {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return record.schema_version === "nlfr.view-spec.v1" && typeof record.view_id === "string";
}
