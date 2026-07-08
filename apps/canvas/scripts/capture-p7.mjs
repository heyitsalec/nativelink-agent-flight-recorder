// P7 verification + capture (composer drawer, ⌘K palette, system states).
// Drives the REAL UI controls, asserts the honesty contracts, and writes
// screenshots for both themes. Exits nonzero if any hard assertion fails.
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const canvasRoot = path.resolve(__dirname, "..");
const url = process.env.CANVAS_URL ?? "http://127.0.0.1:5174/";
const outDir = process.env.P7_OUT ?? path.join(canvasRoot, "output", "playwright", "p7");
await fs.mkdir(outDir, { recursive: true });

const results = {};
const failures = [];
function check(name, cond, detail) {
  results[name] = { ok: !!cond, detail };
  if (!cond) failures.push(`${name}: ${detail ?? "failed"}`);
}

const browser = await chromium.launch();

async function newPage(theme) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((t) => {
    try {
      window.localStorage.setItem("nlfr.theme", t);
    } catch {
      /* ignore */
    }
  }, theme);
  const page = await context.newPage();
  return { context, page };
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(outDir, name), fullPage: true });
}

for (const theme of ["light", "dark"]) {
  const { context, page } = await newPage(theme);
  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator('[data-testid="action-graph-svg"]').waitFor();

  // --- Resting / no-selection (default graph) ---
  if (theme === "light") {
    const resting = await page.locator('[data-testid="resting-hint"]').isVisible();
    check("resting_hint_default", resting, "resting hint shown on default graph");
    await shot(page, "p7-resting-light.png");
  }

  // --- Composer drawer via the header Composer button ---
  await page.locator('[data-testid="composer-open-header"]').click();
  await page.locator('[data-testid="composer-drawer"]').waitFor();
  const templateOptions = await page.locator('[data-testid="composer-template-option"]').count();
  const runGroupPills = await page.locator('[data-testid="composer-run-group-pill"]').count();
  const panelToggles = await page.locator('[data-testid="composer-panel-toggle"]').count();
  const okText = (await page.locator('[data-testid="composer-validation-ok"]').textContent()) ?? "";
  const previewVisible = await page.locator('[data-testid="composer-live-preview"]').isVisible();
  const previewCaption =
    (await page.locator(".composer-preview-caption").textContent()) ?? "";
  const exportCaption = (await page.locator(".composer-footer-caption").textContent()) ?? "";
  if (theme === "light") {
    check("composer_templates_real", templateOptions === 5, `${templateOptions} template options (expect 5)`);
    check("composer_run_group_pills", runGroupPills > 0, `${runGroupPills} run-group pills`);
    check("composer_panel_toggles", panelToggles > 0, `${panelToggles} panel toggles`);
    check("composer_validation_ok", /spec valid/.test(okText) && /0 errors/.test(okText), okText);
    check("composer_live_preview", previewVisible && /updates as you edit/.test(previewCaption), previewCaption);
    check("composer_export_caption", /never evidence/.test(exportCaption), exportCaption);
  }
  await shot(page, `p7-composer-${theme}.png`);

  // --- Live preview reflects the REAL spec: toggle off the legend, the wire
  // legend block must disappear (preview.ts wired to the composed spec). ---
  if (theme === "light") {
    const legendBefore = await page.locator(".composer-wire .wire-legend").count();
    // Find the truth_legend toggle by its aria-label and turn it off.
    const legendToggle = page.locator('[data-testid="composer-panel-toggle"][aria-label*="truth legend"]');
    if (await legendToggle.count()) {
      await legendToggle.first().click();
      await page.waitForTimeout(120);
      const legendAfter = await page.locator(".composer-wire .wire-legend").count();
      check(
        "composer_preview_reflects_spec",
        legendBefore >= 1 && legendAfter === 0,
        `legend wire block ${legendBefore} → ${legendAfter} after toggling legend off`,
      );
      await legendToggle.first().click(); // restore
      await page.waitForTimeout(80);
    } else {
      check("composer_preview_reflects_spec", false, "no truth-legend toggle found");
    }
  }

  // close composer
  await page.locator('[data-testid="composer-drawer"] .composer-close').click();

  // --- ⌘K palette: open via the ⌘K keycap button ---
  await page.locator('.operator-key').click();
  await page.locator('[data-testid="command-palette"]').waitFor();
  const groupCount = await page.locator('.palette-group').count();
  const rowCountAll = await page.locator('[data-testid="palette-row"]').count();
  const footer = (await page.locator('[data-testid="palette-nonevidentiary"]').textContent()) ?? "";
  if (theme === "light") {
    check("palette_grouped", groupCount === 3, `${groupCount} groups (expect FOCUS/LENSES/CANVAS)`);
    check("palette_all_commands", rowCountAll === 8, `${rowCountAll} rows on empty query (expect 8)`);
    check("palette_nonevidentiary", /never persisted, never exported as evidence/.test(footer), footer);
  }
  await shot(page, `p7-palette-${theme}.png`);

  // typed filter + highlight
  await page.locator('.palette-input').fill("prf");
  await page.waitForTimeout(120);
  const typedRows = await page.locator('[data-testid="palette-row"]').count();
  const markCount = await page.locator('.palette-mark').count();
  if (theme === "light") {
    check("palette_fuzzy_filter", typedRows >= 1 && typedRows < 8, `${typedRows} rows for "prf"`);
    check("palette_highlight", markCount >= 1, `${markCount} highlighted marks`);
    await shot(page, "p7-palette-typed.png");
  }
  await page.keyboard.press("Escape");

  await context.close();
}

// --- Focus-applied states (light) ---
{
  const { context, page } = await newPage("light");
  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator('[data-testid="action-graph-svg"]').waitFor();

  // focus failures — default projection has 0 failures → HONEST "0 of N match"
  await page.locator('input[aria-label="operator command"]').fill("focus failures");
  await page.locator('input[aria-label="operator command"]').press("Enter");
  await page.waitForTimeout(400);
  const focusPill = await page.locator('[data-testid="focus-applied"]').isVisible();
  const matchText = (await page.locator('[data-testid="focus-match-count"]').textContent()) ?? "";
  check("focus_pill_visible", focusPill, "focus pill shown");
  check("focus_empty_honest", /^0 of \d+ nodes? match$/.test(matchText.trim()), matchText);
  await shot(page, "p7-focus-empty.png");

  // agent loop — non-empty match
  await page.locator('input[aria-label="operator command"]').fill("agent loop");
  await page.locator('input[aria-label="operator command"]').press("Enter");
  await page.waitForTimeout(400);
  const agentMatch = (await page.locator('[data-testid="focus-match-count"]').textContent()) ?? "";
  check("focus_agent_nonzero", /^[1-9]\d* of \d+ nodes? match$/.test(agentMatch.trim()), agentMatch);
  await shot(page, "p7-focus-agent.png");
  await context.close();
}

// --- Fallback banner: abort the action-graph fetch → labeled simulated_v1 fixture ---
{
  const { context, page } = await newPage("light");
  await page.route("**/action-graph.json", (route) => route.abort());
  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator('[data-testid="action-graph-svg"]').waitFor();
  const banner = (await page.locator('[data-testid="context-banner"]').textContent()) ?? "";
  const isFallback =
    (await page.locator(".context-banner--fallback").count()) > 0 &&
    /fixture fallback/i.test(banner) &&
    /simulated_v1/.test(banner);
  check("fallback_banner_labeled", isFallback, banner);
  await shot(page, "p7-fallback-banner.png");
  await context.close();
}

// --- Loading state: throttle the action-graph fetch, screenshot mid-load ---
{
  const { context, page } = await newPage("light");
  await page.route("**/action-graph.json", async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  const nav = page.goto(url, { waitUntil: "domcontentloaded" });
  const loadingSeen = await page
    .locator('[data-testid="projection-loading-state"]')
    .waitFor({ state: "visible", timeout: 1200 })
    .then(() => true)
    .catch(() => false);
  if (loadingSeen) await shot(page, "p7-loading.png");
  check("loading_state_role_status", loadingSeen, "loading state rendered during throttled load");
  await nav.catch(() => {});
  await context.close();
}

// --- Compare "Open Composer" wire: abort compare projection → empty state → click ---
{
  const { context, page } = await newPage("light");
  await page.route("**/compare-projection.json", (route) => route.abort());
  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator('[data-testid="action-graph-svg"]').waitFor();
  await page.locator('[aria-label="Compare Runs"]').click();
  await page.locator('[data-testid="compare-empty-state"]').waitFor();
  await shot(page, "p7-compare-empty.png");
  await page.locator('[data-testid="compare-open-composer"]').click();
  const composerOpened = await page
    .locator('[data-testid="composer-drawer"]')
    .waitFor({ state: "visible", timeout: 2000 })
    .then(() => true)
    .catch(() => false);
  check("compare_open_composer_wired", composerOpened, "compare empty-state button opens composer");
  await shot(page, "p7-compare-open-composer.png");
  await context.close();
}

await browser.close();

console.log(JSON.stringify({ outDir, results, failures }, null, 2));
if (failures.length > 0) {
  console.error(`\nP7 CAPTURE FAILURES (${failures.length}):\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log(`\nP7 capture OK — ${Object.keys(results).length} checks passed.`);
