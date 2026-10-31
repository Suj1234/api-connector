// Clicks through the PRD §15 demo in a real browser, screen by screen.
// Backup video: RECORD_VIDEO=1 node scripts/demo-walkthrough.mjs  → data/demo-video/*.webm
// Needs the app running on http://localhost:8000 with a fresh database, and Playwright:
//   npm i -g playwright && npx playwright install chromium
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const { chromium } = createRequire(import.meta.url)("playwright"); // local or global (NODE_PATH) install

const BASE = process.env.BASE_URL || "http://localhost:8000";
const SLOW = Number(process.env.SLOW_MS || (process.env.RECORD_VIDEO ? 900 : 0));
const OUT = new URL("../data/", import.meta.url).pathname;
mkdirSync(`${OUT}demo-shots`, { recursive: true });

const browser = await chromium.launch({ slowMo: SLOW });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  ...(process.env.RECORD_VIDEO ? { recordVideo: { dir: `${OUT}demo-video`, size: { width: 1440, height: 900 } } } : {}),
});
const page = await context.newPage();
const shot = (name) => page.screenshot({ path: `${OUT}demo-shots/${name}.png`, fullPage: true });
const pause = (ms) => page.waitForTimeout(process.env.RECORD_VIDEO ? ms : 200);

try {
  // 0:00 Acme inventory: Calendly, renews in 58 days, no usage data
  await page.goto(BASE);
  await page.getByRole("row", { name: /Calendly/ }).waitFor();
  await shot("01-inventory"); await pause(2000);
  await page.getByRole("row", { name: /Calendly/ }).getByRole("button", { name: "Connect usage data" }).click();
  // 0:30 Build with AI from the docs
  await page.getByRole("button", { name: "Build with AI" }).click();
  await page.waitForURL(/found/, { timeout: 180000 });
  await page.getByText("What we found").waitFor();
  await shot("02-what-we-found"); await pause(2500);
  await page.getByRole("button", { name: "View evidence" }).click();
  await shot("03-evidence"); await pause(2500);
  await page.getByRole("button", { name: "Close" }).click();
  // 1:30 Test, generated code
  await page.getByRole("button", { name: "Looks right" }).click();
  await page.getByRole("button", { name: "Run test" }).click();
  await page.getByRole("button", { name: "See the savings" }).first().waitFor({ timeout: 180000 });
  await shot("04-test-passed"); await pause(1500);
  await page.getByRole("tab", { name: "Generated code" }).click();
  await shot("05-generated-code"); await pause(3000);
  // 2:15 Savings → live
  await page.getByRole("button", { name: "See the savings" }).first().click();
  await page.getByText("Recoverable before renewal").waitFor();
  await shot("06-savings"); await pause(3000);
  await page.getByRole("button", { name: "Go live" }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Go live" }).click();
  await page.waitForURL(/detail/);
  // 3:00 Library: submit → approve → Globex connects with its own token
  await page.getByRole("button", { name: "Submit to library" }).click();
  await page.getByText("Waiting for review").waitFor(); await pause(1500);
  await page.getByLabel("Switch tenant").selectOption("internal");
  await page.getByRole("row", { name: /Calendly/ }).click();
  await shot("07-review"); await pause(2000);
  await page.getByRole("button", { name: "Approve to library" }).click(); await pause(1000);
  await page.getByLabel("Switch tenant").selectOption("globex");
  await page.getByRole("row", { name: /Calendly/ }).getByText("In library").waitFor();
  await shot("08-globex-in-library"); await pause(1500);
  await page.getByRole("row", { name: /Calendly/ }).getByRole("button", { name: "Connect usage data" }).click();
  await page.getByRole("button", { name: "Connect with your token" }).click();
  await page.getByText("Give the token exactly these scopes").waitFor();
  await shot("09-globex-connect");
  console.log(`Done. Screenshots in ${OUT}demo-shots${process.env.RECORD_VIDEO ? `, video in ${OUT}demo-video` : ""}`);
} finally {
  await context.close();
  await browser.close();
}
