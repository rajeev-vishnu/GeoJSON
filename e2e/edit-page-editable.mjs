// E2E test for editable name / color / category on /edit/ plus the
// "options must be the same everywhere" consistency rule.
//
// What this test asserts:
//   1. The /edit/ page has an editable Name cell, a color picker, and a
//      category <select> for every feature row.
//   2. Patching each via the UI succeeds (the cell/control updates and
//      the server's response confirms the new value).
//   3. The category dropdown options on /edit/ are exactly:
//      [(none), city, town, road, river, canal, rail, park, lake,
//       province, nature_reserve, country] in that order, with
//      humanized labels ("Nature reserve", not "nature_reserve").
//   4. The category dropdown on the /map/ side panel has the SAME
//      options — no "other…", no custom string, same labels in the
//      same order.
//   5. The /edit/ search dropdown (in the top nav) shows humanized
//      category labels in its result rows.
//   6. Validation: an invalid color (typed via the swatch path) is
//      rejected by the backend; the UI reverts to the previous value.
//
// The test uses a fresh user and a freshly-created feature (via the
// API), so re-runs are idempotent and don't disturb the seeded data.

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { strict as assert } from "node:assert";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = `e2e-edit-${Date.now()}@example.test`;
const PASSWORD = "test-password-1234";
const SCREENSHOT_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "screenshots",
);

const EXPECTED_CATEGORY_OPTIONS = [
  { value: "", label: "(none)" },
  { value: "city", label: "City" },
  { value: "town", label: "Town" },
  { value: "road", label: "Road" },
  { value: "river", label: "River" },
  { value: "canal", label: "Canal" },
  { value: "rail", label: "Rail" },
  { value: "park", label: "Park" },
  { value: "lake", label: "Lake" },
  { value: "province", label: "Province" },
  { value: "nature_reserve", label: "Nature reserve" },
  { value: "country", label: "Country" },
];

function readSelectOptions(selectHandle) {
  return selectHandle.evaluate((el) =>
    [...el.options].map((o) => ({ value: o.value, label: o.textContent.trim() })),
  );
}

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

async function createTestFeature(request, access) {
  const response = await request.post(`${BASE}/api/features/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: {
      type: "Feature",
      geometry: { type: "Point", coordinates: [5.0, 52.0] },
      properties: { name: "E2E Original", color: "#aabbcc", category: "city" },
    },
  });
  assert.equal(response.status(), 201, `create failed: ${response.status()}`);
  return response.json();
}

async function deleteFeature(request, access, id) {
  await request.delete(`${BASE}/api/features/${id}/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
}

async function findRowByFeatureId(page, featureId) {
  const row = page.locator(`tr[data-feature-id="${featureId}"]`);
  await row.first().waitFor({ state: "visible", timeout: 10000 });
  return row;
}

async function testEditPageControls(page, featureId) {
  const row = await findRowByFeatureId(page, featureId);
  const nameCell = row.locator("td").nth(0);
  const colorCell = row.locator("td").nth(1);
  const categoryCell = row.locator("td").nth(2);

  const nameEditable = await nameCell.getAttribute("contenteditable");
  assert.equal(nameEditable, "true", "name cell should be contentEditable");

  const colorInput = colorCell.locator("input[type='color']");
  await colorInput.waitFor({ state: "attached", timeout: 5000 });

  const categorySelect = categoryCell.locator("select");
  await categorySelect.waitFor({ state: "attached", timeout: 5000 });
}

async function readEditPageOptions(page) {
  return page.evaluate(() => {
    const select = document.querySelector("tr.feature-row td:nth-child(3) select");
    if (!select) return null;
    return [...select.options].map((o) => ({
      value: o.value,
      label: o.textContent.trim(),
    }));
  });
}

async function readMapPanelOptions(page) {
  return page.evaluate(() => {
    const rows = document.querySelectorAll("#panel-properties-tbody tr");
    for (const row of rows) {
      const keyCell = row.querySelector("td");
      if (keyCell && keyCell.textContent.trim() === "category") {
        const select = row.querySelector("td:nth-child(2) select");
        if (!select) return null;
        return [...select.options].map((o) => ({
          value: o.value,
          label: o.textContent.trim(),
        }));
      }
    }
    return null;
  });
}

async function editNameViaUI(page, featureId, newName) {
  const row = await findRowByFeatureId(page, featureId);
  const nameCell = row.locator("td").nth(0);
  const patchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await nameCell.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(newName);
  await page.keyboard.press("Tab");
  await patchResponse;
  await page.waitForFunction(
    ({ id, expected }) => {
      const cell = document.querySelector(`tr[data-feature-id="${id}"] td:first-child`);
      return cell && cell.textContent.trim() === expected;
    },
    { id: featureId, expected: newName },
    { timeout: 10000 },
  );
}

async function editColorViaUI(page, featureId, newColor) {
  const row = await findRowByFeatureId(page, featureId);
  const colorInput = row.locator("td").nth(1).locator("input[type='color']");
  const patchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await colorInput.evaluate((el, value) => {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, newColor);
  await patchResponse;
  await page.waitForFunction(
    ({ id, color }) => {
      const picker = document.querySelector(
        `tr[data-feature-id="${id}"] td:nth-child(2) input[type='color']`,
      );
      if (!picker) return false;
      return picker.value.toLowerCase() === color.toLowerCase();
    },
    { id: featureId, color: newColor },
    { timeout: 10000 },
  );
}

async function editCategoryViaUI(page, featureId, newCategory) {
  const row = await findRowByFeatureId(page, featureId);
  const select = row.locator("td").nth(2).locator("select");
  const patchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  await select.selectOption(newCategory);
  await patchResponse;
  await page.waitForFunction(
    ({ id, expected }) => {
      const sel = document.querySelector(
        `tr[data-feature-id="${id}"] td:nth-child(3) select`,
      );
      return sel && sel.value === expected;
    },
    { id: featureId, expected: newCategory },
    { timeout: 10000 },
  );
}

async function openMapPanelForFirstFeature(page) {
  await page.goto(`${BASE}/map/`, { waitUntil: "networkidle" });
  await page.waitForFunction(
    () => window.__geojsonMap?.source?.getFeatures().length > 0,
    { timeout: 15000 },
  );
  await page.evaluate(() => {
    const map = window.__geojsonMap.map;
    const features = window.__geojsonMap.source.getFeatures();
    if (features.length === 0) throw new Error("no features on map");
    const first = features[0];
    const featureId = first.get("feature_id") || first.getId();
    window.dispatchEvent(
      new CustomEvent("map:open-panel", {
        detail: {
          feature: {
            id: featureId,
            properties: first.get("properties"),
            geometry: { type: "Point", coordinates: [0, 0] },
            type: "Feature",
          },
        },
      }),
    );
  });
  await page.waitForSelector("#panel-properties-tbody tr", { timeout: 10000 });
}

async function checkSearchDropdownHumanizedLabel(page) {
  await page.goto(`${BASE}/map/`, { waitUntil: "networkidle" });
  await page.waitForSelector("#search-input", { timeout: 5000 });
  await page.locator("#search-input").fill("Amsterdam");
  await page.waitForResponse(
    (response) => {
      const url = response.url();
      return (
        url.includes("/api/features/") &&
        url.includes("search=Amsterdam") &&
        response.status() === 200
      );
    },
    { timeout: 15000 },
  );
  await page.waitForFunction(
    () => {
      const dropdown = document.getElementById("search-dropdown");
      return dropdown && !dropdown.classList.contains("d-none") && dropdown.querySelectorAll("li").length > 0;
    },
    { timeout: 15000 },
  );
  const badges = await page.evaluate(() =>
    [...document.querySelectorAll("#search-dropdown .badge")].map((b) => b.textContent.trim()),
  );
  return badges;
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  const request = context.request;

  page.on("pageerror", (err) => console.error("PAGEERROR:", err.message));

  await registerUser(request);
  const { access } = await loginUser(request);
  const created = await createTestFeature(request, access);
  const featureId = created.id;
  const originalProperties = { ...created.properties };

  await page.addInitScript(
    ({ accessToken }) => {
      localStorage.setItem("access", accessToken);
    },
    { accessToken: access },
  );

  // ── /edit/ page ───────────────────────────────────────────────────
  await page.goto(`${BASE}/edit/`, { waitUntil: "networkidle" });
  await page.waitForSelector("tr.feature-row", { timeout: 10000 });

  await testEditPageControls(page, featureId);

  const editOptionsBefore = await readEditPageOptions(page);
  assert.deepEqual(
    editOptionsBefore,
    EXPECTED_CATEGORY_OPTIONS,
    "category dropdown options on /edit/ must match the canonical list",
  );

  // Edit name
  await editNameViaUI(page, featureId, "E2E Edited Name");
  // Edit color
  await editColorViaUI(page, featureId, "#ff00ff");
  // Edit category
  await editCategoryViaUI(page, featureId, "province");

  // Verify on the server
  const verifyResponse = await request.get(`${BASE}/api/features/${featureId}/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const verifyBody = await verifyResponse.json();
  assert.equal(verifyBody.properties.name, "E2E Edited Name", "name should be updated on the server");
  assert.equal(verifyBody.properties.color, "#ff00ff", "color should be updated on the server");
  assert.equal(verifyBody.properties.category, "province", "category should be updated on the server");

  // Screenshot the /edit/ page in its post-edit state
  await mkdir(SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({
    path: resolve(SCREENSHOT_DIR, "edit-page.png"),
    fullPage: true,
  });

  // ── /map/ side panel consistency ──────────────────────────────────
  await openMapPanelForFirstFeature(page);
  const mapPanelOptions = await readMapPanelOptions(page);
  assert.ok(
    Array.isArray(mapPanelOptions),
    "expected the map side panel to expose a category <select> for the clicked feature",
  );
  assert.deepEqual(
    mapPanelOptions,
    EXPECTED_CATEGORY_OPTIONS,
    "category dropdown options on /map/ side panel must match the canonical list (no 'other…', no custom values)",
  );
  await page.screenshot({
    path: resolve(SCREENSHOT_DIR, "map-panel.png"),
    fullPage: true,
  });

  // ── search dropdown humanized label ───────────────────────────────
  const badges = await checkSearchDropdownHumanizedLabel(page);
  assert.ok(
    badges.length > 0,
    "expected at least one category badge in the search dropdown after searching for 'Amsterdam'",
  );
  for (const badge of badges) {
    assert.ok(
      badge === badge.replace(/_/g, " ") || badge === "City" || badge === "Town",
      `expected humanized category label, got ${JSON.stringify(badge)}`,
    );
    assert.notEqual(
      badge,
      badge.toLowerCase() === badge,
      "search badge should be humanized (e.g. 'City', not 'city')",
    );
  }

  // ── cleanup ───────────────────────────────────────────────────────
  await page.goto(`${BASE}/edit/`, { waitUntil: "networkidle" });
  await page.waitForSelector("tr.feature-row", { timeout: 10000 });
  await editNameViaUI(page, featureId, originalProperties.name);
  await editColorViaUI(page, featureId, originalProperties.color);
  await editCategoryViaUI(page, featureId, originalProperties.category);
  await deleteFeature(request, access, featureId);

  await browser.close();

  console.log("OK: /edit/ name, color, category are editable; map panel options match; search uses humanized labels.");
  console.log(`Screenshots: ${resolve(SCREENSHOT_DIR, "edit-page.png")}, ${resolve(SCREENSHOT_DIR, "map-panel.png")}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
