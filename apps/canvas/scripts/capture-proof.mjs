import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const url = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
const outputRoot =
  process.env.NLFR_PLAYWRIGHT_OUTPUT ??
  "/Users/alecbot/Documents/nativelink-agent-flight-recorder/output/playwright";

await fs.mkdir(outputRoot, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: outputRoot, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
await page.goto(url, { waitUntil: "networkidle" });
await page.locator('[data-testid="action-graph-svg"]').waitFor();
await page.screenshot({ path: path.join(outputRoot, "canvas-desktop.png"), fullPage: true });
await page.getByLabel("Proof Packet").click();
await page.waitForTimeout(450);
await page.screenshot({ path: path.join(outputRoot, "canvas-proof.png"), fullPage: true });
await page.getByLabel("Remote Boundary").click();
await page.waitForTimeout(450);
await page.screenshot({ path: path.join(outputRoot, "canvas-remote-boundary.png"), fullPage: true });
await page.locator('input[aria-label="operator command"]').fill("focus failures");
await page.locator('input[aria-label="operator command"]').press("Enter");
await page.waitForTimeout(650);
await page.screenshot({ path: path.join(outputRoot, "canvas-failure-focus.png"), fullPage: true });
await page.locator('input[aria-label="operator command"]').fill("agent loop");
await page.locator('input[aria-label="operator command"]').press("Enter");
await page.waitForTimeout(650);
await page.screenshot({ path: path.join(outputRoot, "canvas-agent-loop.png"), fullPage: true });

const video = page.video();
await context.close();
if (video) {
  await fs.copyFile(await video.path(), path.join(outputRoot, "canvas-operator-flow.webm"));
}

const mobile = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
});
const mobilePage = await mobile.newPage();
await mobilePage.goto(url, { waitUntil: "networkidle" });
await mobilePage.locator('[data-testid="action-graph-svg"]').waitFor();
await mobilePage.screenshot({ path: path.join(outputRoot, "canvas-mobile.png"), fullPage: true });
await mobile.close();
await browser.close();

console.log(
  JSON.stringify(
    {
      desktop: path.join(outputRoot, "canvas-desktop.png"),
      proof: path.join(outputRoot, "canvas-proof.png"),
      remote: path.join(outputRoot, "canvas-remote-boundary.png"),
      failure: path.join(outputRoot, "canvas-failure-focus.png"),
      agentLoop: path.join(outputRoot, "canvas-agent-loop.png"),
      mobile: path.join(outputRoot, "canvas-mobile.png"),
      video: path.join(outputRoot, "canvas-operator-flow.webm"),
    },
    null,
    2,
  ),
);
