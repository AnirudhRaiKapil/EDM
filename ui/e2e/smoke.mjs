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

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
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
  const workspaceUrl = page.url();
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

  // A non-file connector type, to exercise the generic connection_config/credentials
  // JSON fields (oracle/s3/rest_api/servicenow/jira/confluence all share this form).
  await page.fill('input[placeholder="Source name"]', "oracle-customers");
  await page.selectOption(".tabs ~ div form select", "oracle");
  await page.fill(
    'textarea[placeholder*="connection_config"]',
    '{"host": "db.internal", "port": 1521, "service_name": "ORCL", "table": "customers"}',
  );
  await page.fill(
    'textarea[placeholder*="credentials"]',
    '{"username": "admin", "password": "do-not-leak-me"}',
  );
  await page.click('button:has-text("Create source")');
  await page.waitForSelector("text=stored (encrypted)");
  await shot(page, "oracle-source-created");
  if ((await page.content()).includes("do-not-leak-me")) {
    throw new Error("credential leaked into the page");
  }

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

  // Pipeline scheduling: set a cron, confirm it's shown and persisted, then clear it.
  await page.fill('input[placeholder*="Cron expression"]', "0 * * * *");
  await page.click('button:has-text("Set schedule")');
  await page.waitForSelector("code:has-text('0 * * * *')");
  await shot(page, "pipeline-schedule-set");

  await page.click('button:has-text("Clear schedule")');
  await page.waitForSelector("text=Not scheduled");
  await shot(page, "pipeline-schedule-cleared");

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

  // Notebook: write code in cells, run it interactively against a sample, then promote
  // it into a real pipeline and run that pipeline too.
  await page.goto(projectUrl);
  await page.click('button:has-text("Notebooks")');
  await page.waitForSelector('input[placeholder="Notebook name"]');

  await page.fill('input[placeholder="Notebook name"]', "explore-events");
  await page.locator(".inline-form select").selectOption({ label: "events-csv" });
  await page.click('button:has-text("Create notebook")');
  await page.waitForSelector("text=explore-events");
  await shot(page, "notebook-created");

  await page.click("text=explore-events");
  await page.waitForURL(/\/notebooks\/[^/]+$/);

  await page.click('button:has-text("+ Add cell")');
  await page.waitForSelector(".card textarea");
  await page.locator(".card textarea").nth(0).fill("df = df.drop_duplicates()");
  await page.locator(".card textarea").nth(0).blur();

  await page.click('button:has-text("+ Add cell")');
  await page.waitForFunction(() => document.querySelectorAll(".card textarea").length === 2);
  await page.locator(".card textarea").nth(1).fill("print(df['amount'].sum())");
  await page.locator(".card textarea").nth(1).blur();
  await shot(page, "notebook-cells-written");

  await page.click('button:has-text("Run all cells")');
  // Cell 2 runs against cell 1's *output*: dedupe drops one Ada row first, so the sum
  // here is over the remaining 91 + 77, proving cells share state in order.
  await page.waitForSelector("text=168", { timeout: 10000 });
  await shot(page, "notebook-run-results");

  await page.fill('section input[placeholder="Output dataset name"]', "events_deduped");
  await page.click('button:has-text("Promote")');
  await page.waitForURL(/\/pipelines\/[^/]+$/, { timeout: 10000 });
  await page.waitForSelector("text=python_code");
  await shot(page, "notebook-promoted-to-pipeline");

  await page.click('button:has-text("Run pipeline")');
  await page.waitForSelector("text=succeeded", { timeout: 15000 });
  await shot(page, "promoted-pipeline-job-succeeded");

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

  // Notification channels: webhook/email/slack/teams, all created through the
  // same generic form on the project's Notifications tab.
  await page.click('button:has-text("Notifications")');
  await page.waitForSelector('button:has-text("Add channel")');

  await page.fill('input[placeholder="https://example.com/webhook"]', "https://hooks.example.com/edm");
  await page.click('button:has-text("Add channel")');
  await page.waitForSelector("text=https://hooks.example.com/edm");
  await shot(page, "webhook-channel-created");

  await page.selectOption(".tabs ~ div form select", "slack");
  await page.fill('input[placeholder="https://hooks.slack.com/services/..."]', "https://hooks.slack.com/services/T0/B0/x");
  await page.click('button:has-text("Add channel")');
  await page.waitForSelector("text=https://hooks.slack.com/services/T0/B0/x");
  await shot(page, "slack-channel-created");

  await page.selectOption(".tabs ~ div form select", "email");
  await page.fill('input[type="email"]', "oncall@example.com");
  await page.click('button:has-text("Add channel")');
  await page.waitForSelector("text=oncall@example.com");
  await shot(page, "email-channel-created");

  await page.click('tr:has-text("slack") >> button:has-text("Delete")');
  await page.waitForSelector("text=https://hooks.slack.com/services/T0/B0/x", { state: "detached" });
  await shot(page, "slack-channel-deleted");

  // Audit log: owner-only section on the workspace page. The oracle source created
  // earlier with credentials should already have produced a source.credentials_set
  // event scoped to this workspace.
  await page.goto(workspaceUrl);
  await page.waitForSelector("text=Audit Log");
  await page.waitForSelector("text=source.credentials_set");
  await shot(page, "audit-log");

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
