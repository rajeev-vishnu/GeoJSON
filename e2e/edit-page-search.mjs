// E2E test: /edit/ page live name filter.
//
// Locked-in acceptance criteria (see spec §Test plan):
//   1. Initial state shows the first page of all features
//   2. Typing a query that matches many rows shows exactly that many
//      rows
//   3. Typing a query that matches a subset shows exactly that subset
//   4. Typing a query that matches zero shows an empty table, no error
//   5. Changing the sort dropdown preserves the active search
//   6. Clicking "Next" preserves the active search
//   7. Clearing the input restores the unfiltered first page
//   8. Rapid typing collapses to the last value via the debounce
//   9. Visual confirmation via screenshot

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { strict as assert } from "node:assert";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const RUN_ID = Date.now();
const NAME_PREFIX = `E2ESearchTest${RUN_ID}`;
const OTHER_NAME = `E2EOtherFeature${RUN_ID}`;
const EMAIL = `e2e-editsearch-${RUN_ID}@example.test`;
const PASSWORD = "test-password-1234";
const SCREENSHOT_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "screenshots",
);

const FEATURE_NAMES = [
  `${NAME_PREFIX} Alpha`,
  `${NAME_PREFIX} Bravo`,
  `${NAME_PREFIX} Charlie`,
  `${NAME_PREFIX} Delta`,
  `${NAME_PREFIX} Echo`,
  `${NAME_PREFIX} Foxtrot`,
  OTHER_NAME,
];

async function registerUser(request) {
  const response = await request.post(`${BASE}/api/auth/register/`, {
    data: { email: EMAIL, password: PASSWORD, password_confirm: PASSWORD },
  });
  assert.equal(response.status(), 201, `register failed: ${response.status()}`);
}

async function loginUser(request) {
  const response = await request.post(`${BASE}/api/auth/login/`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  assert.equal(response.status(), 200, `login failed: ${response.status()}`);
  return response.json();
}

async function createTestFeatures(request, access) {
  const ids = [];
  for (const name of FEATURE_NAMES) {
    const response = await request.post(`${BASE}/api/features/`, {
      headers: { Authorization: `Bearer ${access}` },
      data: {
        type: "Feature",
        geometry: { type: "Point", coordinates: [5.0, 52.0] },
        properties: { name, color: "#aabbcc", category: "city" },
      },
    });
    assert.equal(
      response.status(),
      201,
      `create feature "${name}" failed: ${response.status()}`,
    );
    const body = await response.json();
    ids.push(body.id);
  }
  return ids;
}

async function deleteTestFeatures(access, ids) {
  for (const id of ids) {
    await fetch(`${BASE}/api/features/${id}/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${access}` },
    });
  }
}

async function rowNames(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("tr.feature-row td:first-child")].map(
      (cell) => cell.textContent.trim(),
    ),
  );
}

async function waitForRowCount(page, expected, timeout = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const count = await page.evaluate(
      () => document.querySelectorAll("tr.feature-row").length,
    );
    if (count === expected) return;
    await page.waitForTimeout(100);
  }
  const actual = await page.evaluate(
    () => document.querySelectorAll("tr.feature-row").length,
  );
  throw new Error(
    `expected ${expected} rows, got ${actual} after ${timeout}ms`,
  );
}

async function main() {
  await mkdir(SCREENSHOT_DIR, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const request = context.request;
  const page = await context.newPage();
  page.on("pageerror", (e) => console.error("PAGEERROR:", e.message));

  await registerUser(request);
  const { access, refresh } = await loginUser(request);
  await context.addInitScript(
    ({ a, r }) => {
      localStorage.setItem("access", a);
      localStorage.setItem("refresh", r);
    },
    { a: access, r: refresh },
  );
  const feature_ids = await createTestFeatures(request, access);

  try {
    await runAssertions(page);
  } finally {
    // Best-effort cleanup. The search-bar-ux test depends on the
    // dropdown content fitting in 320px; long test names can break it.
    await deleteTestFeatures(access, feature_ids);
    await browser.close();
  }
}

async function runAssertions(page) {
  await page.goto(`${BASE}/edit/`, { waitUntil: "networkidle" });

  // ── Assertion 1: initial state ────────────────────────────────
  const input = page.locator("#edit-search-input");
  await input.waitFor({ state: "visible", timeout: 10000 });
  assert.equal(await input.inputValue(), "", "input should be empty on load");
  const initialNames = await rowNames(page);
  assert.ok(
    initialNames.includes(OTHER_NAME),
    `initial table should include ${OTHER_NAME}; got: ${JSON.stringify(initialNames)}`,
  );
  assert.equal(
    await page.locator("#page-indicator").textContent(),
    "Page 1",
    "page indicator should read 'Page 1' on load",
  );

  // ── Assertion 2: query that matches many ──────────────────────
  await input.fill(NAME_PREFIX);
  await waitForRowCount(page, 6);
  let names = await rowNames(page);
  assert.equal(names.length, 6, `expected 6 rows, got ${names.length}`);
  for (const name of names) {
    assert.ok(
      name.includes(NAME_PREFIX),
      `row name "${name}" should contain ${NAME_PREFIX}`,
    );
  }
  assert.equal(
    await page.locator("#page-indicator").textContent(),
    "Page 1",
    "page indicator should reset to 'Page 1' after search",
  );

  // ── Assertion 3: query that matches a subset ──────────────────
  await input.fill("");
  await page.waitForTimeout(300);
  // Use the full unique name so the query is deterministic even when
  // the database has pollution from previous test runs.
  await input.fill(`${NAME_PREFIX} Alpha`);
  await waitForRowCount(page, 1);
  names = await rowNames(page);
  assert.equal(names.length, 1, `expected 1 row, got ${names.length}`);
  assert.ok(
    names[0].includes(`${NAME_PREFIX} Alpha`),
    `row name "${names[0]}" should contain "${NAME_PREFIX} Alpha"`,
  );

  // ── Assertion 4: query that matches zero ──────────────────────
  await input.fill("");
  await page.waitForTimeout(300);
  await input.fill("zzzzz");
  await waitForRowCount(page, 0);
  const alert = page.locator("#edit-alert");
  assert.equal(
    await alert.evaluate((el) => el.classList.contains("d-none")),
    true,
    "no error alert should be shown for empty results",
  );
  assert.equal(
    await page.locator("#page-prev").isDisabled(),
    true,
    "prev button should be disabled with zero results",
  );
  assert.equal(
    await page.locator("#page-next").isDisabled(),
    true,
    "next button should be disabled with zero results",
  );

  // ── Assertion 5: sort preserves search ────────────────────────
  await input.fill("");
  await page.waitForTimeout(300);
  await input.fill(NAME_PREFIX);
  await waitForRowCount(page, 6);

  // Intercept the next /api/features/ request to capture its URL.
  const requestPromise = page.waitForRequest(
    (req) =>
      req.url().includes("/api/features/") &&
      req.url().includes("ordering=") &&
      req.method() === "GET",
    { timeout: 5000 },
  );
  await page.locator("#sort-order").selectOption("created_at");
  const sortRequest = await requestPromise;
  const sortUrl = sortRequest.url();
  const encodedPrefix = encodeURIComponent(NAME_PREFIX);
  assert.ok(
    sortUrl.includes(`search=${encodedPrefix}`),
    `sort request URL should include search=${encodedPrefix}: ${sortUrl}`,
  );
  assert.ok(
    sortUrl.includes("ordering=created_at"),
    `sort request URL should include ordering=created_at: ${sortUrl}`,
  );
  await waitForRowCount(page, 6);
  names = await rowNames(page);
  for (const name of names) {
    assert.ok(name.includes(NAME_PREFIX), `row name "${name}" should contain ${NAME_PREFIX}`);
  }

  // ── Assertion 6: Next preserves search ────────────────────────
  const nextButton = page.locator("#page-next");
  if (await nextButton.isEnabled()) {
    const nextRequestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/features/") &&
        req.url().includes("page=2") &&
        req.method() === "GET",
      { timeout: 5000 },
    );
    await nextButton.click();
    const nextRequest = await nextRequestPromise;
    const nextUrl = nextRequest.url();
    assert.ok(
      nextUrl.includes(`search=${encodedPrefix}`),
      `next-page request URL should include search=${encodedPrefix}: ${nextUrl}`,
    );
    assert.ok(
      nextUrl.includes("page=2"),
      `next-page request URL should include page=2: ${nextUrl}`,
    );
    // Wait for the table to update with the page-2 results.
    await page.waitForTimeout(500);
  } else {
    console.log(`(only one page of ${NAME_PREFIX} results; skipped Next click)`);
  }

  // ── Assertion 7: clear restores unfiltered list ──────────────
  await input.fill("");
  await page.waitForTimeout(400); // debounce + network
  const clearedNames = await rowNames(page);
  assert.ok(
    clearedNames.includes(OTHER_NAME),
    `cleared table should include ${OTHER_NAME}; got: ${JSON.stringify(clearedNames)}`,
  );
  assert.equal(
    await page.locator("#page-indicator").textContent(),
    "Page 1",
    "page indicator should reset to 'Page 1' after clear",
  );

  // ── Assertion 8: rapid typing collapses to last value ─────────
  await input.fill(NAME_PREFIX);
  await page.waitForTimeout(50);
  await input.fill("zzzzz");
  await waitForRowCount(page, 0);
  const finalNames = await rowNames(page);
  assert.equal(
    finalNames.length,
    0,
    `expected 0 rows after rapid typing, got ${finalNames.length}`,
  );

  // ── Assertion 9: visual confirmation ─────────────────────────
  await input.fill("");
  await page.waitForTimeout(400);
  await input.fill(NAME_PREFIX);
  await waitForRowCount(page, 6);
  await page.screenshot({
    path: resolve(SCREENSHOT_DIR, "edit-page-search.png"),
    fullPage: false,
  });

  console.log(
    "OK: edit-page search — live filter, sort/pagination preserve search, clear restores list, debounce collapses rapid typing.",
  );
  console.log(
    `Screenshot: ${resolve(SCREENSHOT_DIR, "edit-page-search.png")}`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
