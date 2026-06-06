import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";
import pixelmatch from "pixelmatch";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(canvasRoot, "../..");

const outputRoot =
  process.env.NLFR_PLAYWRIGHT_OUTPUT ?? path.join(repoRoot, "output", "playwright");
const baselineRoot =
  process.env.NLFR_SCREENSHOT_BASELINES ??
  path.join(canvasRoot, "baselines", "screenshots");
const diffRoot = path.join(outputRoot, "diff");
const threshold = Number(process.env.NLFR_DIFF_THRESHOLD ?? "0.1");

const shots = [
  "canvas-desktop.png",
  "canvas-proof.png",
  "canvas-remote-boundary.png",
  "canvas-failure-focus.png",
  "canvas-agent-loop.png",
  "canvas-mobile.png",
];

await fs.mkdir(diffRoot, { recursive: true });

const report = {
  baselineRoot,
  outputRoot,
  threshold,
  comparisons: [],
  ok: true,
};

for (const name of shots) {
  const baselinePath = path.join(baselineRoot, name);
  const currentPath = path.join(outputRoot, name);
  const diffPath = path.join(diffRoot, name);

  try {
    await fs.access(baselinePath);
    await fs.access(currentPath);
  } catch {
    report.ok = false;
    report.comparisons.push({
      name,
      status: "missing",
      detail: "baseline or current screenshot missing; run npm run capture with UPDATE_BASELINES=1",
    });
    continue;
  }

  const baseline = PNG.sync.read(await fs.readFile(baselinePath));
  const current = PNG.sync.read(await fs.readFile(currentPath));

  if (baseline.width !== current.width || baseline.height !== current.height) {
    report.ok = false;
    report.comparisons.push({
      name,
      status: "size_mismatch",
      baseline: { width: baseline.width, height: baseline.height },
      current: { width: current.width, height: current.height },
    });
    continue;
  }

  const diff = new PNG({ width: baseline.width, height: baseline.height });
  const mismatched = pixelmatch(
    baseline.data,
    current.data,
    diff.data,
    baseline.width,
    baseline.height,
    { threshold },
  );
  await fs.writeFile(diffPath, PNG.sync.write(diff));

  const totalPixels = baseline.width * baseline.height;
  const mismatchRatio = mismatched / totalPixels;
  const passed = mismatchRatio <= threshold;
  if (!passed) {
    report.ok = false;
  }
  report.comparisons.push({
    name,
    status: passed ? "pass" : "fail",
    mismatchedPixels: mismatched,
    mismatchRatio,
    diffPath,
  });
}

const reportPath = path.join(outputRoot, "diff-report.json");
await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);

console.log(JSON.stringify(report, null, 2));
if (!report.ok) {
  process.exitCode = 1;
}
