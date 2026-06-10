/// <reference types="vite/client" />

/**
 * Resolve a root-relative asset path (e.g. "/projections/action-graph.json")
 * against the Vite base path so fetches work on GitHub project pages, where
 * the app is served from /<repo-name>/ instead of /.
 *
 * View specs keep root-relative `path` values; this helper is the single
 * runtime translation point.
 */
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL ?? "/";
  if (!path.startsWith("/")) return `${base}${path}`;
  return `${base.replace(/\/$/, "")}${path}`;
}
