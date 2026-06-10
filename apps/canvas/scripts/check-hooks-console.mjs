// Regression check for two QA findings on the two-act spark lens:
//
// 1. Rules-of-Hooks violation (PR #15): panels were invoked as bare function
//    calls inside GridShell, so selecting a node (mounting the receipt pane)
//    reordered GridShell's hook list and fired
//    "React has detected a change in the order of Hooks". This script clicks
//    agent node → receipt pane → every other node kind → compare lens while
//    capturing the console, and fails on any console error / page error /
//    hook warning.
// 2. Viewport fit: the agent node (with its provenance badge) must be inside
//    the svg viewport on load at common laptop widths (1200 and 1440), and
//    "Reset view" must reframe the graph after a pan.
//
// Usage: npm run preview (port 5174) or npm run dev (port 5173), then
//   CANVAS_URL=http://127.0.0.1:5173/ node scripts/check-hooks-console.mjs
// Screenshots land in <repo>/output/playwright/ (override NLFR_PLAYWRIGHT_OUTPUT).
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../../..");
const baseUrl = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
const outputRoot =
  process.env.NLFR_PLAYWRIGHT_OUTPUT ?? path.join(repoRoot, "output", "playwright");
await fs.mkdir(outputRoot, { recursive: true });

const url = new URL(baseUrl);
url.searchParams.set("view", "two-act-spark");

const NODE_KINDS = [
  "run",
  "change",
  "invocation",
  "target",
  "action",
  "cache_event",
  "failure",
  "artifact",
];

const report = { url: url.toString(), viewports: {}, consoleMessages: [], ok: true };

const browser = await chromium.launch();

function watchConsole(page) {
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      report.consoleMessages.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => {
    report.consoleMessages.push({ type: "pageerror", text: String(error) });
  });
}

function withinBox(inner, outer, epsilon = 1) {
  return (
    Boolean(inner) &&
    Boolean(outer) &&
    inner.x >= outer.x - epsilon &&
    inner.y >= outer.y - epsilon &&
    inner.x + inner.width <= outer.x + outer.width + epsilon &&
    inner.y + inner.height <= outer.y + outer.height + epsilon
  );
}

async function agentVisibleInSvg(page) {
  const svgBox = await page.locator(".graph-canvas").boundingBox();
  const nodeBox = await page
    .locator('[data-graph-node-id^="agent:"]')
    .first()
    .boundingBox();
  const badgeBox = await page
    .locator('[data-testid="agent-provenance-badge"]')
    .first()
    .boundingBox();
  return {
    ok: withinBox(nodeBox, svgBox) && withinBox(badgeBox, svgBox),
    svgBox,
    nodeBox,
    badgeBox,
  };
}

async function runViewport(width, height, { clickThrough }) {
  const page = await browser.newPage({ viewport: { width, height } });
  watchConsole(page);
  await page.goto(url.toString(), { waitUntil: "networkidle" });
  await page.locator('[data-testid="action-graph-svg"]').waitFor();
  await page.locator('[data-graph-node-id^="agent:"]').first().waitFor();

  const result = { steps: [] };

  // Initial fit: agent node + provenance badge inside the svg viewport.
  result.initialFit = await agentVisibleInSvg(page);
  result.steps.push(`initial fit agent visible: ${result.initialFit.ok}`);

  // Click the agent node → receipt pane must open.
  await page.locator('[data-graph-node-id^="agent:"]').first().click();
  await page.locator('[data-testid="receipt-detail-pane"]').waitFor();
  result.steps.push("agent node click -> receipt pane visible");
  await page.screenshot({
    path: path.join(outputRoot, `two-act-${width}-agent-receipt.png`),
    fullPage: false,
  });

  if (clickThrough) {
    // Click through every other node kind present on the canvas.
    for (const kind of NODE_KINDS) {
      const node = page.locator(`.graph-node.${kind}`).first();
      if ((await node.count()) === 0) continue;
      await node.click();
      await page.locator(".inspector").waitFor();
      result.steps.push(`node click: ${kind}`);
    }

    // Compare lens, then back to the graph + agent receipt again.
    await page.locator('[aria-label="Compare Acts"]').click();
    await page.locator('[data-testid="compare-lens"]').waitFor();
    result.steps.push("compare lens visible");
    await page.locator('[aria-label="Action Graph"]').click();
    await page.locator('[data-graph-node-id^="agent:"]').first().click();
    await page.locator('[data-testid="receipt-detail-pane"]').waitFor();
    result.steps.push("back to graph -> receipt pane visible again");
  }

  // Pan the canvas away, then Reset view must reframe to fit.
  const svgBox = await page.locator(".graph-canvas").boundingBox();
  await page.mouse.move(svgBox.x + svgBox.width / 2, svgBox.y + svgBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    svgBox.x + svgBox.width / 2 + svgBox.width * 0.6,
    svgBox.y + svgBox.height / 2 + svgBox.height * 0.45,
    { steps: 8 },
  );
  await page.mouse.up();
  result.afterPan = await agentVisibleInSvg(page);
  result.steps.push(`after pan agent visible: ${result.afterPan.ok}`);
  await page.locator('[aria-label="Reset view"]').click();
  await page.waitForTimeout(700); // reset transition is 420ms
  result.afterReset = await agentVisibleInSvg(page);
  result.steps.push(`after reset agent visible: ${result.afterReset.ok}`);

  await page.close();
  return result;
}

for (const [width, height, opts] of [
  [1440, 900, { clickThrough: true }],
  [1200, 800, { clickThrough: false }],
]) {
  report.viewports[`${width}x${height}`] = await runViewport(width, height, opts);
}

await browser.close();

const errors = report.consoleMessages.filter(
  (message) =>
    message.type === "error" ||
    message.type === "pageerror" ||
    /hook/i.test(message.text),
);
const fitOk = Object.values(report.viewports).every(
  (entry) => entry.initialFit.ok && entry.afterReset.ok,
);
report.ok = errors.length === 0 && fitOk;
report.consoleErrorCount = errors.length;

console.log(JSON.stringify(report, null, 2));
if (!report.ok) {
  process.exitCode = 1;
}
