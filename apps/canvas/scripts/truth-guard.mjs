import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");

const url = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
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

const renderedIds = await page.locator("[data-graph-node-id]").evaluateAll((elements) =>
  elements.map((element) => element.getAttribute("data-graph-node-id")).filter(Boolean),
);

let compareLensOk = true;
if (comparePresent) {
  await page.locator('[aria-label="Compare Runs"]').click();
  compareLensOk = await page.locator('[data-testid="compare-lens"]').isVisible();
}

const overflowChipVisible = await page
  .locator('[data-testid="graph-overflow-chip"]')
  .isVisible()
  .catch(() => false);

await browser.close();

const maxVisibleNodes =
  typeof projection.summary?.max_visible_nodes === "number"
    ? projection.summary.max_visible_nodes
    : 8;

const renderedSet = new Set(renderedIds);
const extra = [...renderedSet].filter((id) => !expectedIds.has(id));
const hiddenCount = Math.max(0, expectedIds.size - renderedSet.size);

const capOk =
  renderedSet.size <= maxVisibleNodes &&
  extra.length === 0 &&
  (hiddenCount === 0 || overflowChipVisible) &&
  (hiddenCount === 0 || renderedSet.size === maxVisibleNodes);

const report = {
  ok: capOk && compareErrors.length === 0 && compareLensOk,
  expectedCount: expectedIds.size,
  renderedCount: renderedSet.size,
  maxVisibleNodes,
  hiddenCount,
  overflowChipVisible,
  extra,
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
