import type { CatalogEntry } from "./catalog";
import type {
  ComponentInstance,
  ComponentProps,
  ModeLens,
  ViewModeId,
  ViewSpec,
} from "../view/types";

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
  disabled: ReadonlySet<string>,
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

/** All binding keys a set of components reference (direct string or join sources). */
export function bindingKeysOfComponents(components: ComponentInstance[]): Set<string> {
  const keys = new Set<string>();
  for (const component of components) {
    const binding = component.projection_binding;
    if (typeof binding === "string") {
      keys.add(binding);
    } else if (binding && typeof binding === "object" && binding.kind === "join_v1") {
      for (const source of binding.sources) keys.add(source);
    }
  }
  return keys;
}

/** A mode the composer dropped because its PRIMARY panel was toggled off. */
export type UnavailableMode = { mode_id: ViewModeId; label: string; primary: string };
/** A mode kept, but with its (toggled-off) SECONDARY rail panel detached. */
export type DetachedRail = { mode_id: ViewModeId; label: string; rail: string };

export type ComposedSpec = {
  /** The composed spec: components pruned AND modes reconciled to stay consistent. */
  spec: ViewSpec;
  unavailableModes: UnavailableMode[];
  detachedRails: DetachedRail[];
};

/**
 * Compose the effective spec from a draft + the toggled-off (denylist) set,
 * degrading GRACEFULLY when an operator toggles off a panel a mode references
 * (redesign P7 V1, board 1k). Rather than leaving a dangling mode → panel
 * reference (which validate flags as a persist-blocking MODE_REF_ORPHAN error),
 * we reconcile the modes so the composed spec stays internally consistent and
 * therefore persistable:
 *
 *  - PRIMARY panel toggled off  → the mode cannot render its main content, so
 *    the mode is DROPPED (and surfaced as an "unavailable mode" warning).
 *  - SECONDARY rail panel toggled off → the mode's primary still renders, so we
 *    keep the mode but DETACH its now-absent rail reference (warned separately).
 *
 * The mode_rail's listed mode ids are pruned to the survivors so it never lists
 * a dropped mode. A draft with NO toggles is returned unchanged (fully valid).
 * Pure + type-only imports → exercised directly by `node --test`.
 */
export function composeEffectiveSpec(
  draft: ViewSpec,
  disabled: ReadonlySet<string>,
): ComposedSpec {
  const components = effectiveComponents(draft.components, disabled);
  const presentIds = new Set(components.map((component) => component.instance_id));
  const draftIds = new Set(draft.components.map((component) => component.instance_id));
  // "Toggled off" = present in the draft but not in the effective set — an
  // INTENTIONAL operator action, distinct from a spec that never had the panel.
  const toggledOff = (id: string | undefined): id is string =>
    id !== undefined && draftIds.has(id) && !presentIds.has(id);

  const unavailableModes: UnavailableMode[] = [];
  const detachedRails: DetachedRail[] = [];
  const modes: ModeLens[] = [];

  for (const mode of draft.modes) {
    if (toggledOff(mode.primary_component)) {
      unavailableModes.push({
        mode_id: mode.mode_id,
        label: mode.label,
        primary: mode.primary_component,
      });
      continue;
    }
    let railComponent = mode.rail_component;
    if (toggledOff(railComponent)) {
      detachedRails.push({ mode_id: mode.mode_id, label: mode.label, rail: railComponent });
      railComponent = undefined;
    }
    modes.push(railComponent === mode.rail_component ? mode : { ...mode, rail_component: railComponent });
  }

  const survivingIds = new Set<string>(modes.map((mode) => mode.mode_id));
  const reconciledComponents = components.map((component) => {
    if (component.component_kind !== "mode_rail") return component;
    const listed = typeof component.props?.modes === "string" ? component.props.modes : "";
    if (!listed) return component;
    const kept = listed
      .split(",")
      .map((id) => id.trim())
      .filter((id) => id.length > 0 && survivingIds.has(id));
    if (kept.join(",") === listed) return component;
    return { ...component, props: { ...component.props, modes: kept.join(",") } };
  });

  return {
    spec: { ...draft, components: reconciledComponents, modes },
    unavailableModes,
    detachedRails,
  };
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
