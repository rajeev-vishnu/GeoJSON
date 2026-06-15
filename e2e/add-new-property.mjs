// E2E test: add-new property flow sends the right wire type for
// all four supported types, and the /map/ side panel renders
// Boolean properties as a <select> (true/false).
//
// Locked-in acceptance criteria (see spec §Test plan):
//   1. /edit/ add-new flow PATCH body has the correct JS type for
//      str, int, float, bool
//   2. /edit/ add-new flow PATCH round-trips to the server with
//      the same JSON type
//   3. /map/ side panel renders a Boolean property row as a
//      <select> (not contentEditable), and PATCHing it sends a
//      JSON boolean

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { strict as assert } from "node:assert";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = `e2e-addnew-${Date.now()}@example.test`;
const PASSWORD = "test-password-1234";
const SCREENSHOT_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "screenshots",
);

const TYPE_FIXTURES = [
  { type: "str", key: "test_str", value: "hello", expected_value: "hello" },
  { type: "int", key: "test_int", value: "42", expected_value: 42 },
  { type: "float", key: "test_float", value: "3.14", expected_value: 3.14 },
  { type: "bool", key: "test_bool", value: "true", expected_value: true },
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

async function createTestFeature(request, access) {
  const response = await request.post(`${BASE}/api/features/`, {
    headers: { Authorization: `Bearer ${access}` },
    data: {
      type: "Feature",
      geometry: { type: "Point", coordinates: [5.0, 52.0] },
      properties: {
        name: "E2E AddNew Original",
        color: "#aabbcc",
        category: "city",
      },
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

async function addNewPropertyViaUI(page, featureId, type, key, value) {
  const row = await findRowByFeatureId(page, featureId);
  const propertiesCell = row.locator("td").nth(4);
  await propertiesCell
    .locator("button", { hasText: "+ add new property" })
    .click();

  const addRow = page.locator("tr[data-add-new='true']");
  await addRow.waitFor({ state: "visible", timeout: 5000 });

  const keyInput = addRow.locator("td").nth(0).locator("input");
  await keyInput.fill(key);

  const typeSelect = addRow.locator("td").nth(1).locator("select");
  await typeSelect.selectOption(type);

  const valueCell = addRow.locator("td").nth(2);
  if (type === "bool") {
    const boolSelect = valueCell.locator("select");
    await boolSelect.selectOption(value);
  } else {
    const valueInput = valueCell.locator("input");
    await valueInput.fill(value);
  }

  const patchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH",
  );
  const patchRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith(`/api/features/${featureId}/`) &&
      request.method() === "PATCH",
  );

  const saveButton = addRow
    .locator("td")
    .nth(3)
    .locator("button", { hasText: "Save" });
  await saveButton.click();

  const [response, request] = await Promise.all([patchResponse, patchRequest]);
  assert.equal(
    response.status(),
    200,
    `[${type}] PATCH response was ${response.status()}, expected 200`,
  );
  const requestBody = JSON.parse(request.postData() || "{}");
  const responseBody = await response.json();

  await addRow.waitFor({ state: "detached", timeout: 5000 });

  return { requestBody, responseBody };
}

function assertWireType(label, actualValue, expectedValue) {
  const expectedType = typeof expectedValue;
  const actualType = typeof actualValue;
  assert.equal(
    actualType,
    expectedType,
    `${label}: expected wire type ${expectedType}, got ${actualType} (value=${JSON.stringify(actualValue)})`,
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
  const { access } = await loginUser(request);
  const created = await createTestFeature(request, access);
  const featureId = created.id;

  await context.addInitScript(
    ({ accessToken }) => {
      localStorage.setItem("access", accessToken);
    },
    { accessToken: access },
  );

  // ── /edit/ page ───────────────────────────────────────────────────
  await page.goto(`${BASE}/edit/`, { waitUntil: "networkidle" });
  await page.waitForSelector("tr.feature-row", { timeout: 10000 });

  for (const fixture of TYPE_FIXTURES) {
    const { requestBody, responseBody } = await addNewPropertyViaUI(
      page,
      featureId,
      fixture.type,
      fixture.key,
      fixture.value,
    );

    assertWireType(
      `[${fixture.type}] PATCH body.${fixture.key}`,
      requestBody.properties[fixture.key],
      fixture.expected_value,
    );
    assert.equal(
      requestBody.properties[fixture.key],
      fixture.expected_value,
      `[${fixture.type}] PATCH body.${fixture.key} = ${JSON.stringify(requestBody.properties[fixture.key])}, expected ${JSON.stringify(fixture.expected_value)}`,
    );

    assert.equal(
      responseBody.properties[fixture.key],
      fixture.expected_value,
      `[${fixture.type}] server response.properties.${fixture.key} = ${JSON.stringify(responseBody.properties[fixture.key])}, expected ${JSON.stringify(fixture.expected_value)}`,
    );

    const getResponse = await request.get(
      `${BASE}/api/features/${featureId}/`,
      { headers: { Authorization: `Bearer ${access}` } },
    );
    const getBody = await getResponse.json();
    assertWireType(
      `[${fixture.type}] GET .${fixture.key}`,
      getBody.properties[fixture.key],
      fixture.expected_value,
    );
    assert.equal(
      getBody.properties[fixture.key],
      fixture.expected_value,
      `[${fixture.type}] GET .${fixture.key} = ${JSON.stringify(getBody.properties[fixture.key])}, expected ${JSON.stringify(fixture.expected_value)}`,
    );
  }

  await page.screenshot({
    path: resolve(SCREENSHOT_DIR, "add-new-property.png"),
    fullPage: true,
  });

  // ── /map/ side panel Boolean UI ───────────────────────────────────
  await page.goto(`${BASE}/map/`, { waitUntil: "networkidle" });
  await page.waitForFunction(
    () => window.__geojsonMap?.source?.getFeatures().length > 0,
    { timeout: 15000 },
  );

  const shallowProperties = {
    name: "E2E AddNew Original",
    color: "#aabbcc",
    category: "city",
    test_str: "hello",
    test_int: 42,
    test_float: 3.14,
    test_bool: true,
  };
  await page.evaluate(
    ({ id, properties }) => {
      window.dispatchEvent(
        new CustomEvent("map:open-panel", {
          detail: {
            feature: {
              id,
              properties,
              geometry: { type: "Point", coordinates: [5.0, 52.0] },
              type: "Feature",
            },
          },
        }),
      );
    },
    { id: featureId, properties: shallowProperties },
  );
  await page.waitForSelector("#panel-properties-tbody tr", { timeout: 10000 });

  const boolRowExists = await page.evaluate((key) => {
    const rows = document.querySelectorAll("#panel-properties-tbody tr");
    for (const row of rows) {
      const keyCell = row.querySelector("td");
      if (keyCell && keyCell.textContent.trim() === key) return true;
    }
    return false;
  }, "test_bool");
  assert.ok(
    boolRowExists,
    "expected a row for 'test_bool' in the /map/ side panel",
  );

  const hasSelect = await page.evaluate((key) => {
    const rows = document.querySelectorAll("#panel-properties-tbody tr");
    for (const row of rows) {
      const keyCell = row.querySelector("td");
      if (keyCell && keyCell.textContent.trim() === key) {
        return Boolean(row.querySelector("td:nth-child(2) select"));
      }
    }
    return null;
  }, "test_bool");
  const hasContentEditable = await page.evaluate((key) => {
    const rows = document.querySelectorAll("#panel-properties-tbody tr");
    for (const row of rows) {
      const keyCell = row.querySelector("td");
      if (keyCell && keyCell.textContent.trim() === key) {
        return (
          row.querySelector("td:nth-child(2)")?.getAttribute("contenteditable") ===
          "true"
        );
      }
    }
    return null;
  }, "test_bool");

  assert.ok(
    hasSelect,
    "Boolean property row in /map/ side panel must use a <select> (true/false)",
  );
  assert.ok(
    !hasContentEditable,
    "Boolean property row in /map/ side panel must NOT be contentEditable",
  );

  const sidePanelPatchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH",
  );
  const sidePanelPatchRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith(`/api/features/${featureId}/`) &&
      request.method() === "PATCH",
  );
  await page.evaluate((key) => {
    const rows = document.querySelectorAll("#panel-properties-tbody tr");
    for (const row of rows) {
      const keyCell = row.querySelector("td");
      if (keyCell && keyCell.textContent.trim() === key) {
        const select = row.querySelector("td:nth-child(2) select");
        if (!select) throw new Error("expected <select> in row " + key);
        select.value = "false";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
    }
    throw new Error("no row for " + key);
  }, "test_bool");
  const [sidePanelResponse, sidePanelRequest] = await Promise.all([
    sidePanelPatchResponse,
    sidePanelPatchRequest,
  ]);
  assert.equal(
    sidePanelResponse.status(),
    200,
    `[map-panel bool change] PATCH response was ${sidePanelResponse.status()}, expected 200`,
  );
  const sidePanelRequestBody = JSON.parse(
    sidePanelRequest.postData() || "{}",
  );
  assertWireType(
    "[map-panel bool change] PATCH body.test_bool",
    sidePanelRequestBody.properties.test_bool,
    false,
  );
  assert.equal(
    sidePanelRequestBody.properties.test_bool,
    false,
    `[map-panel bool change] expected false, got ${JSON.stringify(sidePanelRequestBody.properties.test_bool)}`,
  );

  await deleteFeature(request, access, featureId);
  await browser.close();

  console.log(
    "OK: add-new property sends the right wire type for str/int/float/bool; round-trip preserves type; /map/ side panel renders Boolean as <select>.",
  );
  console.log(`Screenshot: ${resolve(SCREENSHOT_DIR, "add-new-property.png")}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
