import { chromium } from "playwright";
import { statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  cleanupWorkDir,
  createGifCapture,
  createWorkDir,
  ensurePreviewServer,
  ffmpegAvailable,
  formatBytes,
  statGif,
} from "./lib/gif-capture.mjs";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const canvasRoot = join(scriptDir, "..");
const repoRoot = join(canvasRoot, "../..");
const mediaDir = process.env.NLFR_DEMO_MEDIA_DIR ?? join(repoRoot, "docs/media");
const outputGif = process.env.NLFR_DEMO_TOUR_GIF ?? join(mediaDir, "nlfr-canvas-tour.gif");
const workDir =
  process.env.NLFR_DEMO_TOUR_WORK_DIR ?? createWorkDir("nlfr-demo-tour-", "NLFR_DEMO_TOUR_WORK_DIR");
const framesDir = join(workDir, "frames");

const fps = Number(process.env.NLFR_DEMO_TOUR_FPS ?? 8);
const targetDurationSeconds = Number(process.env.NLFR_DEMO_TOUR_DURATION_SECONDS ?? 8);
const storyDurationSeconds = Number(process.env.NLFR_DEMO_TOUR_STORY_SECONDS ?? 8);
const viewport = {
  width: Number(process.env.NLFR_DEMO_TOUR_WIDTH ?? 1280),
  height: Number(process.env.NLFR_DEMO_TOUR_HEIGHT ?? 800),
};
const outputWidth = Number(process.env.NLFR_DEMO_TOUR_OUTPUT_WIDTH ?? 960);
const url = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";

const capture = createGifCapture({
  fps,
  targetDurationSeconds,
  storyDurationSeconds,
  framesDir,
  outputGif,
  outputWidth,
});

let previewChild = null;
let previewSpawned = false;

try {
  ({ child: previewChild, spawned: previewSpawned } = await ensurePreviewServer({
    canvasRoot,
    url,
  }));

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.setViewportSize(viewport);
    await page.goto(url, { waitUntil: "networkidle" });
    await page.locator('[data-testid="action-graph-svg"]').waitFor({ timeout: 15_000 });
    await capture.installTourChrome(page);

    await capture.setCaption(
      page,
      "Action Graph",
      "The canvas renders the action graph projection only — nodes, edges, and truth labels from recorded evidence.",
    );
    await capture.focus(page, '[data-testid="action-graph-svg"]');
    await capture.hold(page, 2.0);

    await page.getByLabel("Proof Packet").click();
    await page.locator('[data-testid="proof-drawer"]').waitFor({ state: "visible" });
    await capture.setCaption(
      page,
      "Proof Packet",
      "Proof claims stay explicit: source kind, confidence, evidence refs, and redaction state on every node.",
    );
    await capture.focus(page, '[data-testid="proof-drawer"]');
    await capture.hold(page, 2.0);

    await page.getByLabel("Compare Runs").click();
    await page.locator('[data-testid="compare-lens"]').waitFor({ state: "visible" });
    await capture.setCaption(
      page,
      "Compare Runs",
      "Derived compare dimensions show proof-packet deltas between run groups — no invented backend state.",
    );
    await capture.focus(page, '[data-testid="compare-lens"]');
    await capture.hold(page, 2.0);

    await page.locator('input[aria-label="operator command"]').fill("agent loop");
    await page.locator('input[aria-label="operator command"]').press("Enter");
    await page.waitForTimeout(400);
    await capture.setCaption(
      page,
      "Operator Command",
      'Type "agent loop" to isolate agent and change evidence on the graph without leaving the projection.',
    );
    await capture.focus(page, '[data-testid="operator-chat"]');
    await capture.hold(page, 2.0);

    if (!ffmpegAvailable()) {
      throw new Error("ffmpeg not found on PATH — install ffmpeg to encode GIF output.");
    }

    capture.makeGif();
    const size = statSync(outputGif).size;
    console.log(
      `Captured ${outputGif} (${formatBytes(size)}, ${capture.frameCount} frames at ${fps} fps, ${targetDurationSeconds}s target)`,
    );
  } finally {
    await browser.close();
  }
} finally {
  if (previewSpawned && previewChild) {
    previewChild.kill("SIGTERM");
  }
  cleanupWorkDir(workDir, "NLFR_DEMO_TOUR_WORK_DIR");
}

const result = {
  status: "ok",
  gif: outputGif,
  bytes: statGif(outputGif),
  ffmpeg: ffmpegAvailable(),
  frames: capture.frameCount,
  fps,
  durationSeconds: targetDurationSeconds,
};

console.log(JSON.stringify(result, null, 2));
