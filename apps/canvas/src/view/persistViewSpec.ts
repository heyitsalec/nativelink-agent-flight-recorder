import type { ViewSpec } from "./types";

export const VIEW_SPEC_STORAGE_KEY = "nlfr.view-spec";

export function readStoredViewSpec(): ViewSpec | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(VIEW_SPEC_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ViewSpec;
    if (parsed.schema_version !== "nlfr.view-spec.v1") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function persistViewSpec(spec: ViewSpec): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(VIEW_SPEC_STORAGE_KEY, JSON.stringify(spec));
}

export function clearStoredViewSpec(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(VIEW_SPEC_STORAGE_KEY);
}

export function downloadViewSpec(spec: ViewSpec, filename = "view-spec.json"): void {
  const blob = new Blob([JSON.stringify(spec, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
