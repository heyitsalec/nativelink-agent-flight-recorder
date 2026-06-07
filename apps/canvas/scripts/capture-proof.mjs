import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(canvasRoot, "../..");

const url = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
const outputRoot =
  process.env.NLFR_PLAYWRIGHT_OUTPUT ?? path.join(repoRoot, "output", "playwright");
const baselineRoot =
  process.env.NLFR_SCREENSHOT_BASELINES ??
  path.join(canvasRoot, "baselines", "screenshots");
const updateBaselines = process.env.UPDATE_BASELINES === "1";

const shots = [
  "canvas-desktop.png",
  "canvas-proof.png",
  "canvas-remote-boundary.png",
  "canvas-failure-focus.png",
  "canvas-agent-loop.png",
  "canvas-mobile.png",
];

await fs.mkdir(outputRoot, { recursive: true });
await fs.mkdir(baselineRoot, { recursive: true });

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

if (updateBaselines) {
  for (const name of shots) {
    await fs.copyFile(path.join(outputRoot, name), path.join(baselineRoot, name));
  }
}

console.log(
  JSON.stringify(
    {
      outputRoot,
      baselineRoot,
      updateBaselines,
      shots: Object.fromEntries(shots.map((name) => [name, path.join(outputRoot, name)])),
      video: path.join(outputRoot, "canvas-operator-flow.webm"),
    },
    null,
    2,
  ),
);
