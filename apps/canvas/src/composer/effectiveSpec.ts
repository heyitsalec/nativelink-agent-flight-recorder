import type { CatalogEntry } from "./catalog";
import type { ComponentInstance, ComponentProps } from "../view/types";

/**
 * Pure spec-shaping helpers for the composer drawer (redesign P7 §7). These are
 * import-free (type-only imports) so `node --test` can exercise them directly —
 * see scripts/composer-validate.test.mjs. The drawer feeds their output to the
 * REAL validate_spec / preview_spec engines, so the live preview and validation
 * reflect the genuine composed spec.
 */

/** The composed component list = the draft minus toggled-off instance ids. */
export function effectiveComponents(
  components: ComponentInstance[],
  disabled: Set<string>,
): ComponentInstance[] {
  return components.filter((component) => !disabled.has(component.instance_id));
}

/** Immutably flip an instance id in the toggled-off (denylist) set. */
export function togglePanelSet(disabled: Set<string>, instanceId: string): Set<string> {
  const next = new Set(disabled);
  if (next.has(instanceId)) next.delete(instanceId);
  else next.add(instanceId);
  return next;
}

/** Catalog kinds not already present in the draft — the "+ add panel" options. */
export function addableCatalog(
  components: ComponentInstance[],
  catalog: CatalogEntry[],
): CatalogEntry[] {
  const present = new Set(components.map((component) => component.component_kind));
  return catalog.filter((entry) => !present.has(entry.kind));
}

/**
 * Build a fresh component instance for a catalog kind, seeding props from the
 * catalog defaults. `seed` keeps the instance_id unique (the drawer passes a
 * timestamp base36).
 */
export function newPanelInstance(entry: CatalogEntry, seed: string): ComponentInstance {
  const props: ComponentProps = {};
  for (const [name, schema] of Object.entries(entry.props_schema)) {
    if (schema.default !== undefined) props[name] = schema.default;
  }
  return {
    instance_id: `composer-${entry.kind}-${seed}`,
    component_kind: entry.kind,
    region: entry.region,
    data_testid: entry.default_testid,
    props: Object.keys(props).length > 0 ? props : undefined,
  };
}
