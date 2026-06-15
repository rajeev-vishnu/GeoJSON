// E2E test: top-nav search bar UX.
//
// Bug A — drop-down scrolls horizontally and bleeds onto the map.
// Bug B — search text persists in the input after clicking a result.
//
// Locked-in acceptance criteria (see spec §Test plan):
//   1. dropdown.scrollWidth === clientWidth for any result count
//   2. dropdown.scrollHeight > clientHeight (vertical scroll still works)
//      for ≥ 5 results
//   3. After clicking a result, input.value === "" and focus returns to
//      the input

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { strict as assert } from "node:assert";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = `e2e-searchux-${Date.now()}@example.test`;
const PASSWORD = "test-password-1234";
const SCREENSHOT_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "screenshots",
);

async function setup() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const request = context.request;

  await request.post(`${BASE}/api/auth/register/`, {
    data: { email: EMAIL, password: PASSWORD, password_confirm: PASSWORD },
  });
  const login = await request.post(`${BASE}/api/auth/login/`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  const { access, refresh } = await login.json();

  await context.addInitScript(
    ({ a, r }) => {
      localStorage.setItem("access", a);
      localStorage.setItem("refresh", r);
    },
    { a: access, r: refresh },
  );

  return { browser, context };
}

async function measureOverflow(dropdown) {
  return dropdown.evaluate((el) => ({
    clientWidth: el.clientWidth,
    scrollWidth: el.scrollWidth,
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight,
  }));
}

async function main() {
  await mkdir(SCREENSHOT_DIR, { recursive: true });
  const { browser, context } = await setup();
  const page = await context.newPage();
  page.on("pageerror", (e) => console.error("PAGEERROR:", e.message));

  await page.goto(`${BASE}/map/`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => Boolean(window.__geojsonMap), null, {
    timeout: 15000,
  });
  await page.waitForTimeout(500);

  // Preflight: this test depends on seeded features. If the database is
  // empty, the test cannot reproduce the bugs it locks in.
  const seedCount = await page.evaluate(async () => {
    const response = await fetch("/api/features/?page=1", {
      headers: { Authorization: "Bearer " + localStorage.getItem("access") },
    });
    const body = await response.json();
    return body.count ?? body.results?.length ?? 0;
  });
  if (seedCount < 5) {
    throw new Error(
      `preflight: database has ${seedCount} features; this test needs ≥ 5. Run: docker compose exec web python manage.py seed_features`,
    );
  }

  const input = page.locator("#search-input");
  const dropdown = page.locator("#search-dropdown");

  // ── Bug A, part 1: 1 result, no horizontal overflow ────────────────
  await input.click();
  await input.fill("gr");
  await page.waitForSelector("#search-dropdown:not(.d-none) li", {
    timeout: 5000,
  });
  const oneResultMeasure = await measureOverflow(dropdown);
  console.log("1-result measure:", oneResultMeasure);
  assert.equal(
    oneResultMeasure.scrollWidth,
    oneResultMeasure.clientWidth,
    `Bug A: drop-down has horizontal overflow with 1 result (scrollWidth ${oneResultMeasure.scrollWidth} > clientWidth ${oneResultMeasure.clientWidth})`,
  );

  // ── Bug A, part 2: many results, vertical scroll but no horizontal ─
  await input.fill("");
  await page.waitForTimeout(300);
  await input.fill("a");
  await page.waitForFunction(
    () => document.querySelectorAll("#search-dropdown li").length >= 5,
    null,
    { timeout: 5000 },
  );
  const manyResultMeasure = await measureOverflow(dropdown);
  console.log("many-result measure:", manyResultMeasure);
  assert.ok(
    manyResultMeasure.scrollHeight > manyResultMeasure.clientHeight,
    `vertical scroll expected with ≥ 5 results (got scrollHeight ${manyResultMeasure.scrollHeight}, clientHeight ${manyResultMeasure.clientHeight})`,
  );
  assert.equal(
    manyResultMeasure.scrollWidth,
    manyResultMeasure.clientWidth,
    `Bug A: drop-down has horizontal overflow with many results (scrollWidth ${manyResultMeasure.scrollWidth} > clientWidth ${manyResultMeasure.clientWidth})`,
  );

  // ── Visual confirmation ───────────────────────────────────────────
  await input.fill("");
  await page.waitForTimeout(300);
  await input.fill("gr");
  await page.waitForSelector("#search-dropdown:not(.d-none) li", {
    timeout: 5000,
  });
  await page.screenshot({
    path: resolve(SCREENSHOT_DIR, "search-bar-ux-dropdown.png"),
    fullPage: false,
  });

  // ── Bug B: clear and re-focus on click ────────────────────────────
  await input.fill("");
  await page.waitForTimeout(300);
  await input.fill("gr");
  await page.waitForSelector("#search-dropdown:not(.d-none) li", {
    timeout: 5000,
  });
  await dropdown.locator("li").first().click();
  await page.waitForTimeout(500);

  const valueAfterClick = await input.inputValue();
  const focusedId = await page.evaluate(() => document.activeElement?.id);
  console.log(
    "after click — value:",
    JSON.stringify(valueAfterClick),
    "focusedId:",
    focusedId,
  );
  assert.equal(
    valueAfterClick,
    "",
    `Bug B: search input value is "${valueAfterClick}" after click, expected ""`,
  );
  assert.equal(
    focusedId,
    "search-input",
    `Bug B: focus did not return to search input (active element id is "${focusedId}")`,
  );

  console.log(
    "OK: search bar UX — no horizontal overflow; vertical scroll preserved; clear + focus on click.",
  );
  console.log(
    `Screenshot: ${resolve(SCREENSHOT_DIR, "search-bar-ux-dropdown.png")}`,
  );

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
