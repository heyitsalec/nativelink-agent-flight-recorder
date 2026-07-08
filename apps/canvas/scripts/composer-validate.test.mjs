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
  effectiveComponents,
  newPanelInstance,
  togglePanelSet,
} from "../src/composer/effectiveSpec.ts";

function fakeComponents() {
  return [
    { instance_id: "graph-main", component_kind: "action_graph_canvas", region: "primary" },
    { instance_id: "legend", component_kind: "truth_legend", region: "primary" },
    { instance_id: "op", component_kind: "operator_command_bar", region: "operator" },
  ];
}

test("catalog: every entry is a known kind in a valid region slot", () => {
  assert.equal(COMPONENT_CATALOG.length, 15);
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
  // Present kinds (3 distinct) are removed from the 15-kind catalog.
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
