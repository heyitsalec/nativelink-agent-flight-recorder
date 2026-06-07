import { chromium } from "playwright";
import { mkdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  cleanupWorkDir,
  createGifCapture,
  createWorkDir,
  ffmpegAvailable,
  formatBytes,
  statGif,
} from "./lib/gif-capture.mjs";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const canvasRoot = join(scriptDir, "..");
const repoRoot = join(canvasRoot, "../..");
const mediaDir = process.env.NLFR_EVIDENCE_MEDIA_DIR ?? join(repoRoot, "docs/media");
const outputGif = process.env.NLFR_EVIDENCE_LOOP_GIF ?? join(mediaDir, "nlfr-evidence-loop.gif");
const workDir =
  process.env.NLFR_EVIDENCE_LOOP_WORK_DIR ??
  createWorkDir("nlfr-evidence-loop-", "NLFR_EVIDENCE_LOOP_WORK_DIR");
const framesDir = join(workDir, "frames");
const htmlPath = join(workDir, "index.html");

const fps = Number(process.env.NLFR_EVIDENCE_LOOP_FPS ?? 8);
const targetDurationSeconds = Number(process.env.NLFR_EVIDENCE_LOOP_DURATION_SECONDS ?? 8);
const viewport = {
  width: Number(process.env.NLFR_EVIDENCE_LOOP_WIDTH ?? 1280),
  height: Number(process.env.NLFR_EVIDENCE_LOOP_HEIGHT ?? 720),
};
const outputWidth = Number(process.env.NLFR_EVIDENCE_LOOP_OUTPUT_WIDTH ?? 960);

mkdirSync(mediaDir, { recursive: true });
writeFileSync(htmlPath, buildHtml(), "utf8");

const capture = createGifCapture({
  fps,
  targetDurationSeconds,
  storyDurationSeconds: targetDurationSeconds,
  framesDir,
  outputGif,
  outputWidth,
  maxColors: 144,
  bayerScale: 4,
});

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.setViewportSize(viewport);
  await page.goto(`file://${htmlPath}`, { waitUntil: "load" });
  await page.waitForSelector('[data-testid="nlfr-evidence-loop"]', { timeout: 10_000 });

  for (let frameIndex = 0; frameIndex < capture.targetFrameCount; frameIndex += 1) {
    const seconds = (frameIndex / Math.max(1, capture.targetFrameCount - 1)) * targetDurationSeconds;
    await page.evaluate((value) => window.renderNlfrEvidenceFrame(value), seconds);
    await page.screenshot({
      path: join(framesDir, `frame_${String(frameIndex).padStart(4, "0")}.png`),
      fullPage: false,
    });
  }

  if (!ffmpegAvailable()) {
    throw new Error("ffmpeg not found on PATH — install ffmpeg to encode GIF output.");
  }

  capture.makeGif();
  const size = statSync(outputGif).size;
  console.log(
    `Captured ${outputGif} (${formatBytes(size)}, ${capture.targetFrameCount} frames at ${fps} fps, ${targetDurationSeconds}s target)`,
  );
} finally {
  await browser.close();
  cleanupWorkDir(workDir, "NLFR_EVIDENCE_LOOP_WORK_DIR");
}

const result = {
  status: "ok",
  gif: outputGif,
  bytes: statGif(outputGif),
  ffmpeg: ffmpegAvailable(),
  frames: capture.targetFrameCount,
  fps,
  durationSeconds: targetDurationSeconds,
};

console.log(JSON.stringify(result, null, 2));

function buildHtml() {
  const events = [
    {
      at: 0,
      prefill: true,
      tone: "wake",
      tag: "nlfr.boot",
      text: "evidence recorder // public-safe replay",
    },
    {
      at: 0,
      prefill: true,
      tone: "run",
      tag: "nlfr run",
      text: "nlfr run --mode generic --scenario canvas-build --run-group canvas-dev",
    },
    {
      at: 0.6,
      tone: "artifact",
      tag: "manifest.write",
      text: "artifact manifest written with SHA-256 hashes",
    },
    {
      at: 1.2,
      tone: "ingest",
      tag: "sqlite.ingest",
      text: "SQLite ingest complete // idempotent upsert into ${NLFR_DATA}/canvas-dev/nlfr.sqlite",
    },
    {
      at: 1.8,
      tone: "export",
      tag: "graph.export",
      text: "nlfr graph export --run-group canvas-dev -> projections/action-graph.json",
    },
    {
      at: 2.4,
      tone: "export",
      tag: "proof.export",
      text: "nlfr proof export --run-group canvas-dev -> projections/proof.json",
    },
    {
      at: 3.0,
      tone: "export",
      tag: "runway.export",
      text: "nlfr runway export --run-group canvas-dev -> projections/runway.json",
    },
    {
      at: 3.6,
      tone: "redact",
      tag: "redact.publish",
      text: "redact-projection.py publishes safe JSON to apps/canvas/public/projections/",
    },
    {
      at: 4.2,
      tone: "compare",
      tag: "compare.export",
      text: "nlfr compare export record-proof vs canvas-dev -> compare-projection.json",
    },
    {
      at: 4.8,
      tone: "build",
      tag: "canvas.build",
      text: "npm --prefix apps/canvas run build // dist serves projection JSON only",
    },
    {
      at: 5.4,
      tone: "summary",
      tag: "summary.json",
      text: "summary.json written // source_kind: collectable_v1 // confidence: high",
    },
    {
      at: 6.0,
      tone: "truth",
      tag: "truth.labels",
      text: "every projected node carries source_kind, confidence, evidence_refs, redaction_state",
    },
    {
      at: 6.6,
      tone: "canvas",
      tag: "canvas.preview",
      text: "canvas reads projection JSON only — no invented backend state",
    },
    {
      at: 7.2,
      tone: "done",
      tag: "cycle.complete",
      text: "record -> ingest -> export -> project -> render // public-safe paths only",
    },
  ];

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NLFR Evidence Loop</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #060b10;
    --panel: #0b1219;
    --ink: #eef4f7;
    --muted: #8fa2a8;
    --line: rgba(210, 230, 236, 0.14);
    --teal: #5ec4d4;
    --cyan: #7ce6eb;
    --green: #72f0a4;
    --yellow: #ffd479;
    --violet: #c7a8ff;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    width: 1280px;
    height: 720px;
    overflow: hidden;
    background:
      radial-gradient(circle at 12% 0%, rgba(94, 196, 212, 0.14), transparent 32%),
      radial-gradient(circle at 82% 18%, rgba(124, 230, 235, 0.08), transparent 34%),
      linear-gradient(135deg, #05080d 0%, #08111a 52%, #111722 100%);
    color: var(--ink);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  }

  body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background: repeating-linear-gradient(0deg, rgba(255,255,255,0.03), rgba(255,255,255,0.03) 1px, transparent 1px, transparent 4px);
    opacity: 0.12;
    mix-blend-mode: screen;
  }

  .shell { width: 100%; height: 100%; padding: 18px; }

  .frame {
    height: 100%;
    border: 1px solid rgba(210, 230, 236, 0.16);
    border-radius: 8px;
    background: rgba(7, 12, 18, 0.94);
    box-shadow: 0 28px 90px rgba(0, 0, 0, 0.46);
    overflow: hidden;
  }

  header {
    height: 62px;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 0 20px;
    border-bottom: 1px solid var(--line);
    background: rgba(14, 23, 32, 0.94);
  }

  .status-dot {
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: var(--teal);
    box-shadow: 0 0 28px rgba(94, 196, 212, 0.72);
  }

  h1 { margin: 0; font-size: 21px; line-height: 1; font-weight: 850; }

  .subtitle { margin-top: 4px; color: var(--muted); font-size: 12px; }

  .pill {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 0 10px;
    border: 1px solid var(--line);
    border-radius: 999px;
    color: #d8e8eb;
    background: rgba(255, 255, 255, 0.045);
    font-size: 11px;
    white-space: nowrap;
  }

  .clock { margin-left: auto; color: var(--teal); font-size: 15px; }

  .command {
    height: 43px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px;
    border-bottom: 1px solid var(--line);
    background: #060b11;
    font-size: 14px;
  }

  .prompt { color: var(--yellow); }

  .terminal {
    position: relative;
    height: calc(100% - 105px);
    padding: 18px 22px 20px;
    background:
      linear-gradient(rgba(255,255,255,0.026) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.022) 1px, transparent 1px),
      rgba(6, 11, 16, 0.84);
    background-size: 26px 26px;
  }

  .terminal-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
    color: #dce8eb;
    font-size: 14px;
    text-transform: uppercase;
  }

  .terminal-lines { display: grid; gap: 10px; }

  .line {
    display: grid;
    grid-template-columns: 108px 220px minmax(0, 1fr);
    gap: 16px;
    align-items: baseline;
    min-height: 34px;
    padding: 7px 11px;
    border-left: 3px solid transparent;
    border-radius: 6px;
    color: #eaf2f5;
    background: rgba(255, 255, 255, 0.022);
    font-size: 15px;
    line-height: 1.25;
  }

  .line.hot {
    background: rgba(94, 196, 212, 0.09);
    border-left-color: var(--teal);
    box-shadow: 0 0 24px rgba(94, 196, 212, 0.08);
  }

  .line.impact {
    min-height: 44px;
    padding-top: 9px;
    padding-bottom: 9px;
    background: rgba(124, 230, 235, 0.075);
    border-left-color: rgba(124, 230, 235, 0.72);
    font-size: 19px;
    font-weight: 760;
  }

  .time { color: #768789; }
  .tag { color: var(--cyan); }

  .tone-wake .tag, .tone-done .tag, .tone-summary .tag { color: var(--green); }
  .tone-run .tag, .tone-ingest .tag, .tone-export .tag { color: var(--cyan); }
  .tone-redact .tag, .tone-build .tag { color: var(--yellow); }
  .tone-compare .tag, .tone-canvas .tag { color: var(--violet); }
  .tone-truth .tag, .tone-artifact .tag { color: var(--teal); }
</style>
</head>
<body>
  <main class="shell" data-testid="nlfr-evidence-loop">
    <section class="frame">
      <header>
        <span class="status-dot"></span>
        <div>
          <h1>NLFR Evidence Loop</h1>
          <div class="subtitle">record -> ingest -> export -> project // public-safe</div>
        </div>
        <span class="pill">collectable_v1</span>
        <span class="pill">SHA-256 manifest</span>
        <span class="pill">SQLite ingest</span>
        <span class="clock" data-clock>00:00.000</span>
      </header>
      <div class="command"><span class="prompt">$</span><span>nlfr evidence replay --scenario canvas-build --privacy public-safe</span></div>
      <section class="terminal" aria-label="Curated NLFR evidence loop events">
        <div class="terminal-title">
          <span>structured evidence stream</span>
          <span>redacted paths // no secrets // no raw logs</span>
        </div>
        <div class="terminal-lines" data-lines></div>
      </section>
    </section>
  </main>
<script>
const EVENTS = ${JSON.stringify(events)};

function renderNlfrEvidenceFrame(seconds) {
  document.querySelector('[data-clock]').textContent = formatClock(seconds);
  renderLines(seconds);
}

function renderLines(seconds) {
  const visible = EVENTS.filter((event) => event.at <= seconds).slice(-9);
  const latest = visible.at(-1);
  document.querySelector('[data-lines]').innerHTML = visible.map((event) => {
    const classes = ['line', 'tone-' + event.tone];
    if (event === latest) classes.push('hot');
    if (event.tone === 'run' || event.tone === 'summary') classes.push('impact');
    return '<div class="' + classes.join(' ') + '">' +
      '<span class="time">' + (event.prefill ? 'cached' : formatClock(event.at)) + '</span>' +
      '<span class="tag">' + escapeHtml(event.tag) + '</span>' +
      '<span>' + escapeHtml(event.text) + '</span>' +
      '</div>';
  }).join('');
}

function formatClock(seconds) {
  const whole = Math.floor(seconds);
  const millis = Math.floor((seconds - whole) * 1000);
  return '00:' + String(whole).padStart(2, '0') + '.' + String(millis).padStart(3, '0');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

window.renderNlfrEvidenceFrame = renderNlfrEvidenceFrame;
renderNlfrEvidenceFrame(0);
</script>
</body>
</html>`;
}
