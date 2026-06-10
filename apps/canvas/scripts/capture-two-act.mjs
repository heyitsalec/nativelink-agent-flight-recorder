// Capture proof screenshots for the two-act spark lens (R3 demo surface):
// receipt badge on the agent graph node, the receipt detail pane, and the
// compare lens with agent receipts side by side.
//
// Usage: npm run preview (port 5174), then `node scripts/capture-two-act.mjs`.
// Output: <repo>/output/playwright/two-act-*.png (override NLFR_PLAYWRIGHT_OUTPUT).
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(canvasRoot, "../..");

const baseUrl = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
const outputRoot =
  process.env.NLFR_PLAYWRIGHT_OUTPUT ?? path.join(repoRoot, "output", "playwright");

await fs.mkdir(outputRoot, { recursive: true });

const url = new URL(baseUrl);
url.searchParams.set("view", "two-act-spark");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(url.toString(), { waitUntil: "networkidle" });
await page.locator('[data-testid="action-graph-svg"]').waitFor();

const report = { captured: [], checks: {} };

// 1. Graph view with the agent node selected: provenance badge + receipt pane.
const agentNode = page.locator('[data-graph-node-id^="agent:"]').first();
await agentNode.waitFor();
report.checks.agent_badge_visible = await page
  .locator('[data-testid="agent-provenance-badge"]')
  .first()
  .isVisible();
report.checks.badge_provenance_class = await page
  .locator('[data-testid="agent-provenance-badge"]')
  .first()
  .getAttribute("data-provenance-class");
await agentNode.click();
await page.locator('[data-testid="receipt-detail-pane"]').waitFor();
report.checks.receipt_pane_visible = true;
await page.screenshot({
  path: path.join(outputRoot, "two-act-graph-receipt-badge.png"),
  fullPage: false,
});
report.captured.push("two-act-graph-receipt-badge.png");

// 2. Receipt detail pane close-up.
await page
  .locator('[data-testid="evidence-inspector"], .inspector')
  .first()
  .screenshot({ path: path.join(outputRoot, "two-act-receipt-pane.png") });
report.captured.push("two-act-receipt-pane.png");

// 3. Compare lens: act1 vs act2 receipts side by side.
await page.locator('[aria-label="Compare Acts"]').click();
await page.locator('[data-testid="compare-lens"]').waitFor();
const provenance = page.locator('[data-testid="compare-agent-provenance"]');
await provenance.waitFor();
report.checks.compare_provenance_chips = await provenance
  .locator(".provenance-chip")
  .count();
await provenance.scrollIntoViewIfNeeded();
await page.screenshot({
  path: path.join(outputRoot, "two-act-compare-receipts.png"),
  fullPage: false,
});
report.captured.push("two-act-compare-receipts.png");
await provenance
  .locator("xpath=ancestor::section[1]")
  .screenshot({ path: path.join(outputRoot, "two-act-compare-provenance-card.png") })
  .catch(() => provenance.screenshot({
    path: path.join(outputRoot, "two-act-compare-provenance-card.png"),
  }));
report.captured.push("two-act-compare-provenance-card.png");

// 4. Banner honesty check: stub act1 graph is mixed collectable+simulated.
report.checks.projection_notice = await page
  .locator('[data-testid="projection-notice"], .projection-notice')
  .first()
  .textContent();

await browser.close();

console.log(JSON.stringify(report, null, 2));
const ok =
  report.checks.agent_badge_visible &&
  report.checks.receipt_pane_visible &&
  report.checks.compare_provenance_chips > 0;
if (!ok) process.exitCode = 1;
