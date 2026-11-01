// Clicks through the PRD §15 demo in a real browser and saves a screenshot of every screen (data/demo-shots/).
// It doubles as a check that the whole flow works: it stops with an error at the first step that doesn't.
//   NODE_PATH=$(npm root -g) node scripts/demo-walkthrough.mjs
// Needs the app running (BASE_URL, default http://localhost:8000) on a fresh database, so Calendly isn't listed
// yet, and Playwright (npm i -g playwright). Without Playwright's own browser it uses the installed Google Chrome.
// When the app asks to log in, set DEMO_USERNAME and DEMO_PASSWORD for this run.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const { chromium } = createRequire(import.meta.url)("playwright"); // local or global (NODE_PATH) install

const BASE = process.env.BASE_URL || "http://localhost:8000";
const OUT = new URL("../data/demo-shots/", import.meta.url).pathname;
const BUILD_MS = 300000; // a build with live Gemini takes about 1.5 to 2 minutes
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch().catch(() => chromium.launch({ channel: "chrome" }));
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const shot = (name) => page.screenshot({ path: `${OUT}${name}.png`, fullPage: true });

try {
  await page.goto(BASE);
  const login = page.getByRole("button", { name: "Log in" });
  if (await login.isVisible({ timeout: 3000 }).catch(() => false)) {
    if (!process.env.DEMO_USERNAME || !process.env.DEMO_PASSWORD) throw new Error("The app asks to log in: set DEMO_USERNAME and DEMO_PASSWORD");
    await page.getByLabel("Email").fill(process.env.DEMO_USERNAME);
    await page.getByLabel("Password", { exact: true }).fill(process.env.DEMO_PASSWORD);
    await login.click();
  }

  // 0:00 Acme inventory: three apps already connected on sample data; Slack's page shows its users.
  // A new database builds them in the background (about a minute), so reload until they show.
  const slack = page.getByRole("row", { name: /Slack/ });
  await slack.waitFor();
  for (let i = 0; i < 24 && !(await slack.getByText("Connected").isVisible()); i++) {
    await page.waitForTimeout(5000);
    await page.reload();
    await slack.waitFor();
  }
  await shot("01-inventory");
  await slack.click();
  await page.getByRole("tab", { name: /Users/ }).waitFor();
  await shot("02-slack-app-page");
  await page.getByRole("button", { name: "App inventory" }).first().click();

  // Add an app: Calendly with its inventory details and its docs link
  await page.getByRole("button", { name: "Add an app" }).click();
  await page.getByPlaceholder("e.g. Acme Forms").fill("Calendly");
  await page.getByPlaceholder("e.g. Marketing Ops").fill("Marketing Ops");
  await page.getByText("Pick a date").click(); // the button is named by its field label, "Renewal date"
  const picker = page.getByRole("dialog", { name: "Choose a date" });
  for (let i = 0; i < 24 && !(await picker.getByText("December 2026").isVisible()); i++) {
    await picker.getByRole("button", { name: (await picker.getByText("2027").count()) ? "Previous month" : "Next month" }).click();
  }
  await picker.getByRole("button", { name: "26", exact: true }).click();
  await page.getByPlaceholder("12000").fill("14400");
  await page.getByPlaceholder("50").fill("60");
  await page.getByPlaceholder("https://developer.example.com/api").fill("https://developer.calendly.com/api-docs");
  await shot("03-add-an-app");

  // 0:30 Build with AI: each step says what it is doing
  await page.getByRole("button", { name: "Build with AI" }).click();
  await page.waitForURL(/\/build/);
  await page.waitForTimeout(4000);
  await shot("04-building");
  await page.waitForURL(/\/found/, { timeout: BUILD_MS });
  await page.getByRole("heading", { name: "Review what we found" }).waitFor();
  await shot("05-what-we-found");
  await page.getByRole("button", { name: /Proved|Not proved/ }).first().click();
  await page.getByRole("dialog", { name: "Evidence from the docs" }).waitFor();
  await shot("06-evidence");
  await page.keyboard.press("Escape");

  // 1:30 Connect and test: the six items, the generated code, every request
  await page.getByRole("button", { name: "Looks right" }).click();
  await page.getByRole("button", { name: "Run test" }).click();
  await page.getByRole("button", { name: "Continue" }).waitFor({ timeout: BUILD_MS });
  await page.getByText("What the generated code covers").waitFor();
  await shot("07-test-passed");
  await page.getByRole("tab", { name: "Generated code" }).click();
  await shot("08-generated-code");
  await page.getByRole("tab", { name: /Run log/ }).click();
  await shot("09-run-log");

  // 2:15 Savings → Go live → the app page with Calendly's users
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByText("Recoverable before renewal").waitFor();
  await shot("10-savings");
  await page.getByRole("button", { name: /^Go live/ }).first().click();
  const note = page.getByRole("dialog").getByLabel(/Why the counts differ/); // asked only when the count differs from SSO by > 2%
  if (await note.isVisible()) await note.fill("Checked by hand: the gap is explained.");
  await page.getByRole("dialog").getByRole("button", { name: /^Go live/ }).click();
  await page.waitForURL(/\/apps\/Calendly/);
  await page.getByRole("tab", { name: /Users/ }).waitFor();
  await shot("11-calendly-app-page");
  console.log(`Done: the whole flow works. Screenshots in ${OUT}`);
} finally {
  await browser.close();
}
