import { chromium } from "playwright";
import { preview } from "vite";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");

// CANVAS_URL targets an already-running server; otherwise serve the built
// dist/ ourselves so the guard is one command locally and in CI.
let previewServer = null;
let url = process.env.CANVAS_URL;
if (!url) {
  previewServer = await preview({
    root: canvasRoot,
    preview: { host: "127.0.0.1", port: 5174, strictPort: false },
  });
  url = previewServer.resolvedUrls.local[0];
}
const projectionPath = path.join(canvasRoot, "public", "projections", "action-graph.json");
const comparePath = path.join(canvasRoot, "public", "projections", "compare-projection.json");

const TRUTH_KEYS = ["source_kind", "confidence", "evidence_refs", "redaction_state"];
const SOURCE_KINDS = new Set(["collectable_v1", "derived_v1", "simulated_v1", "future", "unknown"]);

function validateTruthLabels(value, labelPath, errors) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    errors.push(`${labelPath}: expected object with truth labels`);
    return;
  }
  for (const key of TRUTH_KEYS) {
    if (!(key in value)) {
      errors.push(`${labelPath}: missing ${key}`);
    }
  }
  if (value.source_kind && !SOURCE_KINDS.has(value.source_kind)) {
    errors.push(`${labelPath}: invalid source_kind ${value.source_kind}`);
  }
  if (value.evidence_refs && !Array.isArray(value.evidence_refs)) {
    errors.push(`${labelPath}: evidence_refs must be an array`);
  }
}

function validateCompareProjection(payload, errors) {
  if (payload.projection_kind !== "compare") {
    errors.push("compare projection_kind must be compare");
  }
  validateTruthLabels(payload, "compare.root", errors);
  if (!Array.isArray(payload.dimensions)) {
    errors.push("compare.dimensions must be an array");
    return;
  }
  for (const [index, dimension] of payload.dimensions.entries()) {
    validateTruthLabels(dimension, `compare.dimensions[${index}]`, errors);
    if (!dimension.id || !dimension.title || !dimension.summary) {
      errors.push(`compare.dimensions[${index}]: missing id/title/summary`);
    }
    if (!Array.isArray(dimension.claims)) {
      errors.push(`compare.dimensions[${index}]: claims must be an array`);
    }
  }
}

const projection = JSON.parse(await fs.readFile(projectionPath, "utf8"));
const expectedIds = new Set(projection.nodes.map((node) => node.id));

const compareErrors = [];
let comparePresent = false;
try {
  const compareProjection = JSON.parse(await fs.readFile(comparePath, "utf8"));
  comparePresent = true;
  validateCompareProjection(compareProjection, compareErrors);
} catch (error) {
  if (error && typeof error === "object" && "code" in error && error.code !== "ENOENT") {
    compareErrors.push(`compare projection read failed: ${error.message ?? error}`);
  }
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(url, { waitUntil: "networkidle" });
await page.locator('[data-testid="action-graph-svg"]').waitFor();

/**
 * Density-model honesty snapshot (redesign P4). The graph no longer caps
 * visibility at 8 nodes; instead nodes group into cluster capsules, and the
 * invariant becomes: EVERY projection node is either a rendered card
 * ([data-graph-node-id]) or counted by a visible cluster capsule
 * ([data-graph-cluster-id][data-cluster-count]) — cards + clustered ===
 * total — and the always-visible readout states the same numbers. Nothing is
 * ever silently hidden; collapsed is countable, not gone.
 *
 * Scope of this DOM guard vs the source unit test — kept precise so neither
 * overclaims:
 *   - DOM (here): what the browser actually rendered — rendered card ids are
 *     unique + real, printed capsule label digits sum to that capsule's own
 *     data-cluster-count attribute, rendered cards + Σ(data-cluster-count) ===
 *     total, and the readout's data-* attributes/text match the DOM. It cannot
 *     see whether data-cluster-count itself honestly reflects a disjoint,
 *     phantom-free partition of the projection (a capsule could, in principle,
 *     assert a count while listing an invented or double-counted member).
 *   - Source (scripts/graph-partition.test.mjs): proves buildGraphScene's
 *     output is a disjoint, exhaustive, phantom-free partition of the real
 *     node ids — so the count the DOM trusts provably corresponds to real,
 *     distinct members. Together they close the phantom-member blind spot.
 */
async function graphHonestySnapshot() {
  const renderedIds = await page.locator("[data-graph-node-id]").evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("data-graph-node-id")).filter(Boolean),
  );
  const capsules = await page.locator("[data-graph-cluster-id]").evaluateAll((elements) =>
    elements.map((element) => ({
      id: element.getAttribute("data-graph-cluster-id"),
      count: Number(element.getAttribute("data-cluster-count")),
      // The human-readable count label ("2 invocations · 6 artifacts" /
      // "7 changes") — NOT the suffix/meta text, which may carry digits of
      // its own.
      text:
        element.querySelector(".gcapsule-label, .gcard-label-text")?.textContent ??
        element.textContent ??
        "",
    })),
  );
  const readoutLocator = page.locator('[data-testid="graph-count-readout"]');
  const readoutVisible = await readoutLocator.isVisible().catch(() => false);
  const readout = readoutVisible
    ? await readoutLocator.evaluate((element) => ({
        total: Number(element.getAttribute("data-total")),
        cards: Number(element.getAttribute("data-cards")),
        clustered: Number(element.getAttribute("data-clustered")),
        clusters: Number(element.getAttribute("data-clusters")),
        text: element.textContent ?? "",
      }))
    : null;
  return { renderedIds, capsules, readoutVisible, readout };
}

function checkHonesty(snapshot, label, errors) {
  const renderedSet = new Set(snapshot.renderedIds);
  if (renderedSet.size !== snapshot.renderedIds.length) {
    errors.push(`${label}: duplicate data-graph-node-id entries rendered`);
  }
  const extra = [...renderedSet].filter((id) => !expectedIds.has(id));
  if (extra.length > 0) {
    errors.push(`${label}: fabricated node ids rendered: ${extra.join(", ")}`);
  }
  const clustered = snapshot.capsules.reduce((sum, capsule) => sum + capsule.count, 0);
  // The load-bearing identity: no projection node is unaccounted for.
  if (renderedSet.size + clustered !== expectedIds.size) {
    errors.push(
      `${label}: cards (${renderedSet.size}) + clustered (${clustered}) !== total (${expectedIds.size}) — evidence silently hidden`,
    );
  }
  // Capsule labels must state their real membership: the numbers printed on
  // a capsule sum to its data-cluster-count (no invented counts).
  for (const capsule of snapshot.capsules) {
    if (!Number.isFinite(capsule.count) || capsule.count <= 0) {
      errors.push(`${label}: capsule ${capsule.id} has invalid data-cluster-count`);
      continue;
    }
    const labelSum = (capsule.text.match(/\d+/g) ?? [])
      .map(Number)
      .reduce((sum, value) => sum + value, 0);
    if (labelSum !== capsule.count) {
      errors.push(
        `${label}: capsule ${capsule.id} label "${capsule.text.trim()}" sums to ${labelSum}, not its real member count ${capsule.count}`,
      );
    }
  }
  // The readout must exist, agree with the DOM, and print the true total.
  if (!snapshot.readoutVisible || !snapshot.readout) {
    errors.push(`${label}: graph-count-readout not visible — the total is not discoverable`);
    return;
  }
  const readout = snapshot.readout;
  if (readout.total !== expectedIds.size) {
    errors.push(`${label}: readout total ${readout.total} !== projection total ${expectedIds.size}`);
  }
  if (readout.cards !== renderedSet.size) {
    errors.push(`${label}: readout cards ${readout.cards} !== rendered cards ${renderedSet.size}`);
  }
  if (readout.clustered !== clustered) {
    errors.push(`${label}: readout clustered ${readout.clustered} !== capsule sum ${clustered}`);
  }
  if (readout.clusters !== snapshot.capsules.length) {
    errors.push(
      `${label}: readout clusters ${readout.clusters} !== capsule count ${snapshot.capsules.length}`,
    );
  }
  if (!readout.text.includes(String(expectedIds.size))) {
    errors.push(`${label}: readout text "${readout.text}" does not state the total node count`);
  }
}

const graphErrors = [];
const initial = await graphHonestySnapshot();
checkHonesty(initial, "initial", graphErrors);

// Expanding a cluster must reveal cards without breaking the identity —
// collapsed nodes were countable, expanded nodes are rendered.
let expandedProbe = null;
if (initial.capsules.length > 0) {
  await page.locator("[data-graph-cluster-id]").first().click();
  await page.waitForTimeout(350);
  expandedProbe = await graphHonestySnapshot();
  checkHonesty(expandedProbe, "after-expand", graphErrors);
  if (expandedProbe.renderedIds.length <= initial.renderedIds.length) {
    graphErrors.push(
      `after-expand: expanding a cluster did not reveal any cards (${initial.renderedIds.length} → ${expandedProbe.renderedIds.length})`,
    );
  }
}

let compareLensOk = true;
if (comparePresent) {
  await page.locator('[aria-label="Compare Runs"]').click();
  compareLensOk = await page.locator('[data-testid="compare-lens"]').isVisible();
}

await browser.close();
if (previewServer) {
  await previewServer.close();
}

const report = {
  ok: graphErrors.length === 0 && compareErrors.length === 0 && compareLensOk,
  expectedCount: expectedIds.size,
  initial: {
    renderedCount: initial.renderedIds.length,
    clusteredCount: initial.capsules.reduce((sum, capsule) => sum + capsule.count, 0),
    clusterCount: initial.capsules.length,
    readout: initial.readout?.text?.trim() ?? null,
  },
  afterExpand: expandedProbe
    ? {
        renderedCount: expandedProbe.renderedIds.length,
        clusteredCount: expandedProbe.capsules.reduce((sum, capsule) => sum + capsule.count, 0),
        clusterCount: expandedProbe.capsules.length,
        readout: expandedProbe.readout?.text?.trim() ?? null,
      }
    : null,
  graphErrors,
  compare: {
    present: comparePresent,
    schema_ok: compareErrors.length === 0,
    lens_visible: comparePresent ? compareLensOk : null,
    errors: compareErrors,
  },
};

console.log(JSON.stringify(report, null, 2));
if (!report.ok) {
  process.exitCode = 1;
}
