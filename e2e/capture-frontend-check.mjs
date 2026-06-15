// Ad-hoc Playwright screenshot utility for frontend visual checks.
//
// Usage:
//   node e2e/capture-frontend-check.mjs <path> <output-png> [wait-ms]
//
// Example:
//   node e2e/capture-frontend-check.mjs /map/ e2e/screenshots/map.png 2000
//
// What it does:
//   1. Registers and logs in a fresh user.
//   2. Navigates to <path> (e.g. /map/ or /edit/).
//   3. Waits for any page-specific init (window.__geojsonMap for the
//      map page) and an additional [wait-ms] of settle time (default
//      1500ms) for the OL map tiles and any animated elements.
//   4. Saves a 1280x800 viewport screenshot to <output-png>.
//
// This is for *ad-hoc* visual checks. The committed E2E tests under
// e2e/*.mjs each take their own screenshots as part of their assertions;
// use this one when you want a quick look without running a full suite.

import { chromium } from "playwright";
import { resolve } from "node:path";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const path = process.argv[2];
const output_png = process.argv[3];
const wait_ms = Number(process.argv[4] || 1500);

if (!path || !output_png) {
  console.error(
    "Usage: node e2e/capture-frontend-check.mjs <path> <output-png> [wait-ms]",
  );
  process.exit(1);
}

const EMAIL = `frontend-check-${Date.now()}@example.test`;
const PASSWORD = "test-password-1234";

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const request = context.request;
  const page = await context.newPage();

  page.on("pageerror", (err) => console.log("PAGEERROR:", err.message));

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

  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });

  // Best-effort wait for page-specific init. The map page sets
  // window.__geojsonMap; the edit page doesn't, so we don't fail
  // if it's absent.
  try {
    await page.waitForFunction(
      () => Boolean(window.__geojsonMap),
      null,
      { timeout: 15000 },
    );
  } catch (_error) {
    // Not the map page, or init didn't fire — keep going.
  }

  await page.waitForTimeout(wait_ms);

  const absolute_path = resolve(output_png);
  await page.screenshot({ path: absolute_path, fullPage: false });
  console.log(`Screenshot saved to ${absolute_path}`);

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
