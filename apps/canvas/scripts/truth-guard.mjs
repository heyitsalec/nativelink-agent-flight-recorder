import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");

const url = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
const projectionPath = path.join(canvasRoot, "public", "projections", "action-graph.json");

const projection = JSON.parse(await fs.readFile(projectionPath, "utf8"));
const expectedIds = new Set(projection.nodes.map((node) => node.id));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(url, { waitUntil: "networkidle" });
await page.locator('[data-testid="action-graph-svg"]').waitFor();

const renderedIds = await page.locator("[data-graph-node-id]").evaluateAll((elements) =>
  elements.map((element) => element.getAttribute("data-graph-node-id")).filter(Boolean),
);
await browser.close();

const renderedSet = new Set(renderedIds);
const missing = [...expectedIds].filter((id) => !renderedSet.has(id));
const extra = [...renderedSet].filter((id) => !expectedIds.has(id));

const report = {
  ok: missing.length === 0 && extra.length === 0,
  expectedCount: expectedIds.size,
  renderedCount: renderedSet.size,
  missing,
  extra,
};

console.log(JSON.stringify(report, null, 2));
if (!report.ok) {
  process.exitCode = 1;
}
