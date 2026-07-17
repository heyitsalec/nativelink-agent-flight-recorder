/**
 * Unit tests for the composer's spec-shaping + catalog validation helpers
 * (redesign P7 §7). These are the pure functions the Composer drawer's panel
 * toggles, "+ add panel", and live preview/validation are built from — kept in
 * composer/effectiveSpec.ts + composer/catalog.ts (type-only imports) so
 * `node --test` can import them directly (Node strips the TS types on import).
 *
 * They prove the composer edits a REAL view spec: every catalog kind is a valid
 * component kind in a real region, toggling a panel removes exactly that panel,
 * "+ add panel" only offers kinds not already present, and a re-added panel is
 * a schema-shaped instance (valid kind + region + catalog testid). The full
 * validate_spec / preview_spec engine wiring is proven end-to-end in the
 * playwright capture (the "spec valid · N panels · 0 errors" ok row).
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  COMPONENT_CATALOG,
  COMPONENT_KINDS,
  REGION_SLOTS,
  catalogEntryFor,
} from "../src/composer/catalog.ts";
import {
  addableCatalog,
  bindingKeysOfComponents,
  composeEffectiveSpec,
  effectiveComponents,
  newPanelInstance,
  togglePanelSet,
} from "../src/composer/effectiveSpec.ts";
import { DEFAULT_VIEW_SPEC } from "../src/view/defaultViewSpec.ts";

function fakeComponents() {
  return [
    { instance_id: "graph-main", component_kind: "action_graph_canvas", region: "primary" },
    { instance_id: "legend", component_kind: "truth_legend", region: "primary" },
    { instance_id: "op", component_kind: "operator_command_bar", region: "operator" },
  ];
}

test("catalog: every entry is a known kind in a valid region slot", () => {
  assert.equal(COMPONENT_CATALOG.length, 16);
  for (const entry of COMPONENT_CATALOG) {
    assert.ok(COMPONENT_KINDS.has(entry.kind), `kind ${entry.kind} in COMPONENT_KINDS`);
    assert.ok(REGION_SLOTS.has(entry.region), `region ${entry.region} valid for ${entry.kind}`);
    assert.ok(entry.default_testid.length > 0, `${entry.kind} has a default testid`);
  }
});

test("catalog: catalogEntryFor resolves real kinds and rejects unknown", () => {
  assert.equal(catalogEntryFor("truth_legend")?.default_testid, "truth-legend");
  assert.equal(catalogEntryFor("operator_command_bar")?.region, "operator");
  assert.equal(catalogEntryFor("not_a_kind"), undefined);
});

test("effectiveComponents: drops exactly the toggled-off instance ids, preserves order", () => {
  const components = fakeComponents();
  const disabled = new Set(["legend"]);
  const effective = effectiveComponents(components, disabled);
  assert.deepEqual(
    effective.map((c) => c.instance_id),
    ["graph-main", "op"],
  );
  // No disabled → unchanged; empty set is a pass-through.
  assert.equal(effectiveComponents(components, new Set()).length, 3);
});

test("togglePanelSet: immutably flips membership without mutating the input", () => {
  const base = new Set(["a"]);
  const added = togglePanelSet(base, "b");
  assert.deepEqual([...added].sort(), ["a", "b"]);
  assert.deepEqual([...base], ["a"], "input set not mutated");
  const removed = togglePanelSet(added, "a");
  assert.deepEqual([...removed], ["b"]);
});

test("addableCatalog: excludes kinds already present in the draft", () => {
  const components = fakeComponents();
  const addable = addableCatalog(components, COMPONENT_CATALOG);
  const kinds = addable.map((e) => e.kind);
  assert.ok(!kinds.includes("action_graph_canvas"), "present kind excluded");
  assert.ok(!kinds.includes("truth_legend"), "present kind excluded");
  assert.ok(kinds.includes("proof_drawer"), "absent kind offered");
  // Present kinds (3 distinct) are removed from the 16-kind catalog.
  assert.equal(addable.length, COMPONENT_CATALOG.length - 3);
});

test("newPanelInstance: builds a schema-shaped instance from catalog defaults", () => {
  const entry = catalogEntryFor("truth_legend");
  const instance = newPanelInstance(entry, "seed1");
  assert.equal(instance.component_kind, "truth_legend");
  assert.equal(instance.region, "primary");
  assert.equal(instance.data_testid, "truth-legend");
  assert.ok(instance.instance_id.startsWith("composer-truth_legend-"));
  assert.ok(COMPONENT_KINDS.has(instance.component_kind), "re-added panel is a valid kind");
  // Its default prop (items) is seeded from the catalog schema.
  assert.equal(instance.props?.items, "collectable_v1,derived_v1,simulated_v1,future");
});

test("add → the added kind is no longer addable (round-trip)", () => {
  const components = fakeComponents();
  const entry = catalogEntryFor("proof_drawer");
  const added = [...components, newPanelInstance(entry, "x")];
  const kinds = addableCatalog(added, COMPONENT_CATALOG).map((e) => e.kind);
  assert.ok(!kinds.includes("proof_drawer"), "just-added kind removed from options");
});

test("bindingKeysOfComponents: collects direct string + join source keys", () => {
  const keys = bindingKeysOfComponents([
    { instance_id: "a", component_kind: "topbar_summary", region: "header", projection_binding: "binding.action_graph" },
    {
      instance_id: "b",
      component_kind: "remote_boundary_lens",
      region: "rail",
      projection_binding: {
        kind: "join_v1",
        sources: ["binding.action_graph", "binding.proof_packet"],
        join_fn: "remote_lens_model",
        source_kind: "derived_v1",
        confidence: "medium",
        evidence_refs: [],
        redaction_state: "safe",
      },
    },
    { instance_id: "c", component_kind: "truth_legend", region: "primary" },
  ]);
  assert.deepEqual([...keys].sort(), ["binding.action_graph", "binding.proof_packet"]);
});

/**
 * V1 (board 1k) — toggling off a panel a mode references must degrade
 * gracefully, never leave a dangling mode → panel reference (which validate
 * would flag as a persist-blocking MODE_REF_ORPHAN). composeEffectiveSpec
 * reconciles the modes so the composed spec is always internally consistent.
 * A spec with no dangling refs cannot trip MODE_REF_ORPHAN → stays persistable.
 */
function noDanglingModeRefs(spec) {
  const ids = new Set(spec.components.map((c) => c.instance_id));
  for (const mode of spec.modes) {
    if (!ids.has(mode.primary_component)) return false;
    if (mode.rail_component && !ids.has(mode.rail_component)) return false;
  }
  const modeIds = new Set(spec.modes.map((m) => m.mode_id));
  const rail = spec.components.find((c) => c.component_kind === "mode_rail");
  const listed = typeof rail?.props?.modes === "string" ? rail.props.modes : "";
  if (listed) {
    for (const id of listed.split(",").map((s) => s.trim()).filter(Boolean)) {
      if (!modeIds.has(id)) return false;
    }
  }
  return true;
}

// The 7 panels the default spec's modes reference (primary or rail).
const MODE_REFERENCED = [
  "graph-main", // primary of all 6 modes
  "inspector-selected-node", // graph rail
  "runway-overlay", // runway rail
  "proof-drawer", // proof rail
  "remote-lens", // remote rail
  "compare-lens", // compare rail
  "replay-lens", // replay rail
];

test("composeEffectiveSpec: default (no toggles) is unchanged + fully consistent", () => {
  const { spec, unavailableModes, detachedRails } = composeEffectiveSpec(
    DEFAULT_VIEW_SPEC,
    new Set(),
  );
  assert.equal(spec.components.length, 14);
  assert.equal(spec.modes.length, 6);
  assert.equal(unavailableModes.length, 0);
  assert.equal(detachedRails.length, 0);
  assert.ok(noDanglingModeRefs(spec), "default spec has no dangling mode refs");
});

test("composeEffectiveSpec: toggling EACH of the 14 panels off stays consistent (persistable)", () => {
  const allIds = DEFAULT_VIEW_SPEC.components.map((c) => c.instance_id);
  assert.equal(allIds.length, 14);
  for (const id of allIds) {
    const { spec } = composeEffectiveSpec(DEFAULT_VIEW_SPEC, new Set([id]));
    assert.equal(spec.components.length, 13, `${id}: exactly one panel dropped`);
    assert.ok(noDanglingModeRefs(spec), `${id}: no dangling mode ref → no MODE_REF_ORPHAN`);
  }
});

test("composeEffectiveSpec: only mode-referenced panels emit a degrade notice", () => {
  for (const id of DEFAULT_VIEW_SPEC.components.map((c) => c.instance_id)) {
    const { unavailableModes, detachedRails } = composeEffectiveSpec(
      DEFAULT_VIEW_SPEC,
      new Set([id]),
    );
    const noticed = unavailableModes.length + detachedRails.length > 0;
    if (MODE_REFERENCED.includes(id)) {
      assert.ok(noticed, `${id} is mode-referenced → must warn`);
    } else {
      assert.ok(!noticed, `${id} is not mode-referenced → no mode warning`);
    }
  }
});

test("composeEffectiveSpec: primary panel off drops every dependent mode", () => {
  // graph-main is the primary of all 6 modes.
  const { spec, unavailableModes, detachedRails } = composeEffectiveSpec(
    DEFAULT_VIEW_SPEC,
    new Set(["graph-main"]),
  );
  assert.equal(unavailableModes.length, 6);
  assert.equal(detachedRails.length, 0);
  assert.equal(spec.modes.length, 0);
  const rail = spec.components.find((c) => c.component_kind === "mode_rail");
  assert.equal(rail.props.modes, "", "mode rail lists no dropped modes");
  assert.ok(noDanglingModeRefs(spec));
});

test("composeEffectiveSpec: rail panel off detaches only that rail, keeps the mode", () => {
  const { spec, unavailableModes, detachedRails } = composeEffectiveSpec(
    DEFAULT_VIEW_SPEC,
    new Set(["compare-lens"]),
  );
  assert.equal(unavailableModes.length, 0);
  assert.deepEqual(
    detachedRails.map((r) => r.mode_id),
    ["compare"],
  );
  assert.equal(spec.modes.length, 6, "compare mode is kept");
  const compare = spec.modes.find((m) => m.mode_id === "compare");
  assert.equal(compare.rail_component, undefined, "dangling rail ref detached");
  assert.ok(noDanglingModeRefs(spec));
});
