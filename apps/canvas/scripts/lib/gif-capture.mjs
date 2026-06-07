import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * Shared Harmony-style GIF capture helpers for NLFR canvas media scripts.
 */
export function createGifCapture({
  fps = 8,
  targetDurationSeconds = 8,
  storyDurationSeconds = 8,
  framesDir,
  outputGif,
  outputWidth = 960,
  maxColors = 128,
  bayerScale = 5,
} = {}) {
  const targetFrameCount = Math.round(targetDurationSeconds * fps);
  let frame = 0;
  let storyElapsedSeconds = 0;

  mkdirSync(framesDir, { recursive: true });
  mkdirSync(join(outputGif, ".."), { recursive: true });

  async function hold(page, seconds) {
    storyElapsedSeconds += seconds;
    const cumulativeTargetFrames = Math.min(
      targetFrameCount,
      Math.round((storyElapsedSeconds / storyDurationSeconds) * targetFrameCount),
    );
    const frames = Math.max(1, cumulativeTargetFrames - frame);
    for (let index = 0; index < frames; index += 1) {
      await page.screenshot({
        path: join(framesDir, `frame_${String(frame).padStart(4, "0")}.png`),
        fullPage: false,
      });
      frame += 1;
      await page.waitForTimeout(1000 / fps);
    }
  }

  async function holdFrames(page, count) {
    for (let index = 0; index < count; index += 1) {
      await page.screenshot({
        path: join(framesDir, `frame_${String(frame).padStart(4, "0")}.png`),
        fullPage: false,
      });
      frame += 1;
      await page.waitForTimeout(1000 / fps);
    }
  }

  async function installTourChrome(page, { classPrefix = "nlfr-demo-tour" } = {}) {
    await page.addStyleTag({
      content: `
      .${classPrefix}-caption {
        position: fixed;
        left: 24px;
        bottom: 24px;
        z-index: 2147483647;
        width: min(520px, calc(100vw - 48px));
        padding: 13px 15px 14px;
        border: 1px solid rgba(17, 24, 39, 0.14);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.94);
        box-shadow: 0 18px 50px rgba(17, 24, 39, 0.14);
        color: #18212f;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        pointer-events: none;
      }

      .${classPrefix}-caption strong {
        display: block;
        margin-bottom: 5px;
        font-size: 13px;
        line-height: 1.1;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: #2b8c9f;
      }

      .${classPrefix}-caption span {
        display: block;
        font-size: 15px;
        line-height: 1.32;
      }

      .${classPrefix}-focus {
        position: fixed;
        z-index: 2147483646;
        border: 2px solid rgba(43, 140, 159, 0.82);
        border-radius: 10px;
        box-shadow:
          0 0 0 9999px rgba(247, 248, 251, 0.08),
          0 0 0 6px rgba(43, 140, 159, 0.12),
          0 18px 50px rgba(17, 24, 39, 0.18);
        pointer-events: none;
        transition: left 160ms ease, top 160ms ease, width 160ms ease, height 160ms ease;
      }
    `,
    });
    await page.evaluate((prefix) => {
      const caption = document.createElement("div");
      caption.className = `${prefix}-caption`;
      caption.innerHTML = "<strong></strong><span></span>";
      document.body.append(caption);

      const focusRing = document.createElement("div");
      focusRing.className = `${prefix}-focus`;
      document.body.append(focusRing);
    }, classPrefix);
  }

  async function setCaption(page, title, body, { classPrefix = "nlfr-demo-tour" } = {}) {
    await page.evaluate(
      ({ title: nextTitle, body: nextBody, prefix }) => {
        const caption = document.querySelector(`.${prefix}-caption`);
        caption?.querySelector("strong")?.replaceChildren(document.createTextNode(nextTitle));
        caption?.querySelector("span")?.replaceChildren(document.createTextNode(nextBody));
      },
      { title, body, prefix: classPrefix },
    );
  }

  async function focus(page, selector, { classPrefix = "nlfr-demo-tour", inset = 8 } = {}) {
    const box = await page.locator(selector).first().boundingBox();
    if (!box) return;
    await page.evaluate(
      ({ rect, prefix, inset: ringInset }) => {
        const focusRing = document.querySelector(`.${prefix}-focus`);
        if (!(focusRing instanceof HTMLElement)) return;
        focusRing.style.left = `${Math.max(8, rect.x - ringInset)}px`;
        focusRing.style.top = `${Math.max(8, rect.y - ringInset)}px`;
        focusRing.style.width = `${Math.max(1, rect.width + ringInset * 2)}px`;
        focusRing.style.height = `${Math.max(1, rect.height + ringInset * 2)}px`;
      },
      { rect: box, prefix: classPrefix, inset },
    );
  }

  async function waitForNonblankRoot(page, rootTestId) {
    const selector = `[data-testid="${rootTestId}"]`;
    await page.waitForSelector(selector, { timeout: 10_000, state: "visible" });
    await page.waitForFunction(
      (testId) => {
        const rootElement = document.querySelector(`[data-testid="${testId}"]`);
        const rect = rootElement?.getBoundingClientRect();
        return Boolean(rootElement && rect && rect.width > 100 && rect.height > 100 && rootElement.textContent?.trim());
      },
      rootTestId,
    );
  }

  function makeGif() {
    execFileSync(
      "ffmpeg",
      [
        "-y",
        "-loglevel",
        "error",
        "-framerate",
        String(fps),
        "-i",
        join(framesDir, "frame_%04d.png"),
        "-vf",
        `scale=${outputWidth}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=${maxColors}[p];[s1][p]paletteuse=dither=bayer:bayer_scale=${bayerScale}`,
        "-loop",
        "0",
        outputGif,
      ],
      { stdio: "inherit" },
    );
  }

  return {
    hold,
    holdFrames,
    installTourChrome,
    setCaption,
    focus,
    waitForNonblankRoot,
    makeGif,
    get frameCount() {
      return frame;
    },
    get targetFrameCount() {
      return targetFrameCount;
    },
    fps,
    targetDurationSeconds,
  };
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kib = bytes / 1024;
  if (kib < 1024) return `${kib.toFixed(1)} KiB`;
  return `${(kib / 1024).toFixed(2)} MiB`;
}

export function ffmpegAvailable() {
  try {
    execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

export function createWorkDir(prefix, envVarName) {
  if (process.env[envVarName]) {
    return process.env[envVarName];
  }
  return mkdtempSync(join(tmpdir(), prefix));
}

export function cleanupWorkDir(workDir, envVarName) {
  if (!process.env[envVarName]) {
    rmSync(workDir, { recursive: true, force: true });
  }
}

export async function waitForHttp(url, { timeoutMs = 30_000, intervalMs = 250 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { method: "GET" });
      if (response.ok) return;
    } catch {
      // server not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

/**
 * Spawn `npm run preview` in canvasRoot unless NLFR_SKIP_PREVIEW_SPAWN=1 or server already up.
 * Returns { child, spawned } — caller should kill child when spawned=true.
 */
export async function ensurePreviewServer({
  canvasRoot,
  url = "http://127.0.0.1:5174/",
  skipEnv = "NLFR_SKIP_PREVIEW_SPAWN",
} = {}) {
  try {
    const response = await fetch(url, { method: "GET" });
    if (response.ok) {
      return { child: null, spawned: false };
    }
  } catch {
    // not running
  }

  if (process.env[skipEnv] === "1") {
    throw new Error(
      `Canvas preview not reachable at ${url}. Start it with: npm --prefix apps/canvas run preview`,
    );
  }

  const child = spawn("npm", ["run", "preview"], {
    cwd: canvasRoot,
    stdio: ["ignore", "pipe", "pipe"],
    env: process.env,
  });

  child.stdout?.on("data", () => {});
  child.stderr?.on("data", () => {});

  await waitForHttp(url);
  return { child, spawned: true };
}

export function statGif(outputGif) {
  if (!existsSync(outputGif)) {
    return null;
  }
  return statSync(outputGif).size;
}
