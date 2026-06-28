import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE_URL = process.env.EDM_UI_URL ?? "http://localhost:5173";
const SHOT_DIR = process.env.SCREENSHOT_DIR ?? "./e2e/shots";
fs.mkdirSync(SHOT_DIR, { recursive: true });
let shotIndex = 0;
const consoleErrors = [];

async function shot(page, name) {
  shotIndex += 1;
  const file = path.join(SHOT_DIR, `${String(shotIndex).padStart(2, "0")}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log("screenshot:", file);
}

const browser = await chromium.launch();
const page = await browser.newPage();
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

const stamp = Date.now();
const email = `uitest${stamp}@example.com`;
const password = "hunter2pass";
let failed = false;

try {
  await page.goto(BASE_URL);
  await page.waitForURL("**/login");
  await shot(page, "login-redirect");

  await page.click("text=Register");
  await page.waitForURL("**/register");
  await page.fill('input[type="email"]', email);
  await page.fill('label:has-text("Name") input', "UI Test User");
  await page.fill('input[type="password"]', password);
  await shot(page, "register-filled");
  await page.click('button[type="submit"]');

  await page.waitForURL("**/workspaces");
  await shot(page, "workspaces-empty");

  const wsName = `ui-test-ws-${stamp}`;
  await page.fill('input[placeholder="Workspace name"]', wsName);
  await page.click('button:has-text("Create workspace")');
  await page.waitForSelector(`text=${wsName}`);
  await shot(page, "workspace-created");

  await page.click(`text=${wsName}`);
  await page.waitForURL(/\/workspaces\/[^/]+$/);
  await shot(page, "workspace-detail");

  await page.fill('input[placeholder="Project name"]', "ops");
  await page.click('button:has-text("Create project")');
  await page.waitForSelector("text=ops");
  await shot(page, "project-created");

  await page.click("text=ops");
  await page.waitForURL(/\/projects\/[^/]+$/);
  const projectUrl = page.url();
  await shot(page, "project-detail-sources-tab");

  await page.fill('input[placeholder="Source name"]', "events-csv");
  await page.click('button:has-text("Create source")');
  await page.waitForSelector("text=events-csv");
  await shot(page, "source-created");

  const csvPath = path.resolve(SHOT_DIR, "fixture.csv");
  fs.writeFileSync(
    csvPath,
    "name,email,amount\nAda,ada@example.com,91\nAda,ada@example.com,91\nLin,lin@example.com,77\n",
  );
  await page.setInputFiles('input[type="file"]', csvPath);
  await page.waitForSelector("text=raw/");
  await shot(page, "source-file-uploaded");

  await page.click('button:has-text("Pipelines")');
  await page.waitForSelector('input[placeholder="Pipeline name"]');

  await page.fill('input[placeholder="Pipeline name"]', "standardize-events");
  await page.locator(".pipeline-form .inline-form select").nth(0).selectOption({ label: "events-csv" });
  await page.fill('input[placeholder="Output dataset name"]', "events");
  await page.click('button:has-text("+ Add transformation")');
  await page.click('button:has-text("+ Add transformation")');
  const typeSelects = page.locator(".steps-builder select");
  await typeSelects.nth(0).selectOption("standardize");
  await typeSelects.nth(1).selectOption("dedupe");
  await shot(page, "pipeline-form-filled");
  await page.click('button:has-text("Create pipeline")');
  await page.waitForSelector("text=standardize-events");
  await shot(page, "pipeline-created");

  await page.click("text=standardize-events");
  await page.waitForURL(/\/pipelines\/[^/]+$/);
  await shot(page, "pipeline-detail");

  await page.click('button:has-text("Run pipeline")');
  await page.waitForSelector("text=succeeded", { timeout: 15000 });
  await shot(page, "job-succeeded");

  await page.click("text=view");
  await page.waitForURL(/\/datasets\/[^/]+$/);
  await page.waitForSelector("text=email");
  await shot(page, "dataset-schema");

  await page.fill('input[placeholder="key"]', "pii");
  await page.fill('input[placeholder="value"]', "true");
  await page.click('button:has-text("Add tag")');
  await page.waitForSelector("text=pii=true");
  await shot(page, "dataset-tagged");

  await page.fill('input[placeholder="comma-separated, e.g. pii, confidential"]', "internal, pii");
  await page.click('button:has-text("Update classification")');
  await page.waitForSelector("text=Classification: internal, pii");
  await shot(page, "dataset-classified");

  await page.selectOption(".page section:has-text('Data quality') select", "not_null");
  await page.fill(".page section:has-text('Data quality') input[placeholder='column']", "email");
  await page.click('button:has-text("Add rule")');
  await page.waitForSelector(".rule-card:has-text('not_null')");
  await shot(page, "quality-rule-added");

  await page.waitForSelector("text=source:");
  await shot(page, "dataset-lineage");

  await page.fill("textarea", "SELECT * FROM dataset ORDER BY email");
  await page.click('button:has-text("Run query")');
  await page.waitForSelector("table.data-table:has-text('lin@example.com')", { timeout: 10000 });
  await shot(page, "query-result");

  // Trigger a job failure (bad transformation parameters) to exercise alerting end to end.
  await page.goto(projectUrl);
  await page.click('button:has-text("Pipelines")');
  await page.waitForSelector('input[placeholder="Pipeline name"]');
  await page.fill('input[placeholder="Pipeline name"]', "broken-events");
  await page.locator(".pipeline-form .inline-form select").nth(0).selectOption({ label: "events-csv" });
  await page.fill('input[placeholder="Output dataset name"]', "broken");
  await page.click('button:has-text("+ Add transformation")');
  await page.locator(".steps-builder select").nth(0).selectOption("select_columns");
  await page.fill(
    '.steps-builder input[placeholder*="parameters JSON"]',
    '{"columns": ["does_not_exist"]}',
  );
  await page.click('button:has-text("Create pipeline")');
  await page.waitForSelector("text=broken-events");
  await page.click("text=broken-events");
  await page.waitForURL(/\/pipelines\/[^/]+$/);

  await page.click('button:has-text("Run pipeline")');
  await page.waitForSelector("text=failed", { timeout: 15000 });
  await shot(page, "broken-pipeline-job-failed");

  await page.goto(projectUrl);
  await page.click('button:has-text("Alerts")');
  await page.waitForSelector(".rule-card:has-text('broken-events')");
  await shot(page, "alerts-open");

  // Switch off the "open" filter so the card stays visible through its status
  // transitions -- acknowledging/resolving correctly removes an alert from the
  // "open" filtered view, which is the behavior under test, not a bug to dodge.
  await page.locator(".tabs ~ div select").selectOption("");
  await page.click('.rule-card:has-text("broken-events") >> button:has-text("Acknowledge")');
  await page.waitForSelector(".rule-card:has-text('broken-events') .status-badge:has-text('acknowledged')");
  await shot(page, "alert-acknowledged");

  await page.click('.rule-card:has-text("broken-events") >> button:has-text("Resolve")');
  await page.waitForSelector(".rule-card:has-text('broken-events') .status-badge:has-text('resolved')");
  await shot(page, "alert-resolved-in-all-view");

  await page.locator(".tabs ~ div select").selectOption("open");
  await page.waitForSelector("text=No open alerts.");
  await shot(page, "alert-resolved");

  console.log("RESULT: PASS");
} catch (err) {
  failed = true;
  console.log("RESULT: FAIL", err.message);
  await shot(page, "failure-state");
} finally {
  console.log("console errors:", consoleErrors.length ? JSON.stringify(consoleErrors, null, 2) : "(none)");
  await browser.close();
  process.exit(failed || consoleErrors.length > 0 ? 1 : 0);
}
