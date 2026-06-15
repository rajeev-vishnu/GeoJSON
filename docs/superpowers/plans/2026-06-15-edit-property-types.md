# Edit Property Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the add-new-property bug (empty value sent to backend) and make Boolean properties render as a `<select>` (true/false) in both `/edit/` and the `/map/` side panel, with the right JSON type on the wire.

**Architecture:** Three small frontend changes (`edit.js` reassign variable, add boolean branch in `render_property_row`; same boolean branch in `map-panel.js`) plus one new Playwright E2E and two pytest cases for the backend round-trip. No API, view, model, or template changes.

**Tech Stack:** Playwright (`node`), vanilla JS (no build step), Django REST Framework on the backend. Bootstrap 5 in the surrounding stack (untouched).

**Spec:** `docs/superpowers/specs/2026-06-15-edit-property-types-design.md`

**Working rule for this session:** keep all implementation changes unStaged; do not commit implementation files. Spec/plan commits (this file and the design) are committed; implementation diffs stay unStaged for user review. Pre-commit and the test suite must still pass.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/static/js/edit.js` | modify | `let` value_input + reassign after `replaceWith`; boolean branch in `render_property_row` |
| `frontend/static/js/map-panel.js` | modify | boolean branch in `render_property_row` |
| `e2e/add-new-property.mjs` | create | Playwright E2E: 4 types × add-new wire-type assertions + map panel boolean UI |
| `features/tests/test_serializers.py` | extend | 2 round-trip cases: boolean, float |

No CSS, no API, no view, no template changes.

---

## Task 1: Write the failing E2E test (RED)

**Files:**
- Create: `e2e/add-new-property.mjs`

- [ ] **Step 1: Create the E2E test file**

The test exercises all four types in the add-new flow, asserts the
PATCH body has the right JS type, asserts the server round-trip
preserves the JSON type, and asserts the `/map/` side panel renders
a Boolean property as a `<select>`. It registers a fresh user,
creates a fresh test feature via the API, and cleans up.

```javascript
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
  { type: "str", key: "test_str", value: "hello", expected_js_type: "string" },
  { type: "int", key: "test_int", value: "42", expected_js_type: "number" },
  { type: "float", key: "test_float", value: "3.14", expected_js_type: "number" },
  { type: "bool", key: "test_bool", value: "true", expected_js_type: "boolean" },
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
      properties: { name: "E2E AddNew Original", color: "#aabbcc", category: "city" },
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
  await propertiesCell.locator("button", { hasText: "+ add new property" }).click();

  // Wait for the add-new row
  const addRow = page.locator("tr[data-add-new='true']");
  await addRow.waitFor({ state: "visible", timeout: 5000 });

  // Fill key
  const keyInput = addRow.locator("td").nth(0).locator("input");
  await keyInput.fill(key);

  // Pick type
  const typeSelect = addRow.locator("td").nth(1).locator("select");
  await typeSelect.selectOption(type);

  // Fill value (for str/int/float: text/number input; for bool: select)
  const valueCell = addRow.locator("td").nth(2);
  if (type === "bool") {
    const boolSelect = valueCell.locator("select");
    await boolSelect.selectOption(value);
  } else {
    const valueInput = valueCell.locator("input");
    await valueInput.fill(value);
  }

  // Capture the PATCH request body
  const patchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  const patchRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith(`/api/features/${featureId}/`) &&
      request.method() === "PATCH",
  );
  const [response, request] = await Promise.all([patchResponse, patchRequest]);

  // Click Save
  const saveButton = addRow.locator("td").nth(3).locator("button", { hasText: "Save" });
  await saveButton.click();
  await response;
  const requestBody = JSON.parse(request.postData() || "{}");

  // Wait for the add-new row to be removed (success)
  await addRow.waitFor({ state: "detached", timeout: 5000 });

  return { requestBody, responseBody: await response.json() };
}

function assertWireType(label, actualValue, expectedJsType) {
  // JSON.parse gives us a plain JS value. The "expected JS type" maps to:
  //   "string" -> typeof === "string"
  //   "number" -> typeof === "number" (covers both int and float in JS)
  //   "boolean" -> typeof === "boolean"
  const actual = typeof actualValue;
  assert.equal(
    actual,
    expectedJsType,
    `${label}: expected wire type ${expectedJsType}, got ${actual} (value=${JSON.stringify(actualValue)})`,
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

  // For each of {str, int, float, bool}: add a new property, assert
  // the PATCH body has the right JS type, assert the server response
  // has the right value, and assert the round-tripped server value
  // is the right type.
  for (const fixture of TYPE_FIXTURES) {
    const { requestBody, responseBody } = await addNewPropertyViaUI(
      page,
      featureId,
      fixture.type,
      fixture.key,
      fixture.value,
    );

    // PATCH body wire type
    assertWireType(
      `[${fixture.type}] PATCH body.${fixture.key}`,
      requestBody.properties[fixture.key],
      fixture.expected_js_type,
    );
    // PATCH body has the right value
    const expectedValue = fixture.type === "bool" ? fixture.value === "true" : fixture.value === "42" ? 42 : fixture.value === "3.14" ? 3.14 : fixture.value;
    assert.equal(
      requestBody.properties[fixture.key],
      expectedValue,
      `[${fixture.type}] PATCH body.${fixture.key} = ${JSON.stringify(requestBody.properties[fixture.key])}, expected ${JSON.stringify(expectedValue)}`,
    );

    // Server response value
    assert.equal(
      responseBody.properties[fixture.key],
      expectedValue,
      `[${fixture.type}] server response.properties.${fixture.key} = ${JSON.stringify(responseBody.properties[fixture.key])}, expected ${JSON.stringify(expectedValue)}`,
    );

    // Round-trip: GET from server, assert JS type is preserved
    const getResponse = await request.get(`${BASE}/api/features/${featureId}/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    const getBody = await getResponse.json();
    assertWireType(
      `[${fixture.type}] GET .${fixture.key}`,
      getBody.properties[fixture.key],
      fixture.expected_js_type,
    );
    assert.equal(
      getBody.properties[fixture.key],
      expectedValue,
      `[${fixture.type}] GET .${fixture.key} = ${JSON.stringify(getBody.properties[fixture.key])}, expected ${JSON.stringify(expectedValue)}`,
    );
  }

  // Screenshot of the /edit/ page in its post-add state
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

  // Open our test feature in the side panel by id
  await page.evaluate((id) => {
    window.dispatchEvent(
      new CustomEvent("map:open-panel", {
        detail: {
          feature: {
            id,
            properties: { name: "E2E AddNew Original", color: "#aabbcc", category: "city" },
            geometry: { type: "Point", coordinates: [5.0, 52.0] },
            type: "Feature",
          },
        },
      }),
    );
  }, featureId);
  await page.waitForSelector("#panel-properties-tbody tr", { timeout: 10000 });

  // Find the test_bool row
  const boolRow = await page.evaluateHandle((key) => {
    const rows = document.querySelectorAll("#panel-properties-tbody tr");
    for (const row of rows) {
      const keyCell = row.querySelector("td");
      if (keyCell && keyCell.textContent.trim() === key) return row;
    }
    return null;
  }, "test_bool");
  assert.ok(boolRow, "expected a row for 'test_bool' in the side panel");

  // The row must contain a <select>, not a contenteditable cell
  const hasSelect = await boolRow.evaluate((row) =>
    Boolean(row.querySelector("td:nth-child(2) select")),
  );
  const hasContentEditable = await boolRow.evaluate((row) =>
    Boolean(
      row.querySelector("td:nth-child(2)")?.getAttribute("contenteditable") === "true",
    ),
  );
  assert.ok(
    hasSelect,
    "Boolean property row in /map/ side panel must use a <select> (true/false)",
  );
  assert.ok(
    !hasContentEditable,
    "Boolean property row in /map/ side panel must NOT be contentEditable",
  );

  // Change the boolean via the select and capture the PATCH body
  const newValue = "false";
  const patchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/features/${featureId}/`) &&
      response.request().method() === "PATCH" &&
      response.status() === 200,
  );
  const patchRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith(`/api/features/${featureId}/`) &&
      request.method() === "PATCH",
  );
  await boolRow.evaluate((row, value) => {
    const select = row.querySelector("td:nth-child(2) select");
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }, newValue);
  const [response, request] = await Promise.all([patchResponse, patchRequest]);
  const sidePanelRequestBody = JSON.parse(request.postData() || "{}");
  await response;

  // Assert the PATCH body has a JSON boolean
  assertWireType(
    "[map-panel bool change] PATCH body.test_bool",
    sidePanelRequestBody.properties.test_bool,
    "boolean",
  );
  assert.equal(
    sidePanelRequestBody.properties.test_bool,
    false,
    `[map-panel bool change] expected false, got ${JSON.stringify(sidePanelRequestBody.properties.test_bool)}`,
  );

  // Cleanup: delete the test feature
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
```

- [ ] **Step 2: Run the test to verify it fails (RED)**

```bash
node e2e/add-new-property.mjs
```

Expected: FAIL on the FIRST fixture (`str`). The `addNewPropertyViaUI`
helper sends the right PATCH, but the PATCH body has
`properties.test_str === ""` (empty string) instead of
`"hello"`. The assertion message will include
`[str] PATCH body.test_str: expected wire type string, got string (value="")`.

If you see a different failure (e.g. 401, network error, or "add-new
button not found"), stop and investigate — the test setup is wrong,
not the production code.

---

## Task 2: Add the two backend round-trip tests (RED for the frontend bug, GREEN for the backend)

**Files:**
- Modify: `features/tests/test_serializers.py` (append two new test functions)

These tests pass on master — they only assert the backend preserves
type across a round-trip. They are a safety net for the round-trip
assertions in the E2E.

- [ ] **Step 1: Add the boolean round-trip test**

Append to `features/tests/test_serializers.py`:

```python
def test_properties_boolean_round_trip(make_feature):
    """A boolean value survives a serialize → deserialize → save round-trip as bool."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    body = FeatureSerializer(feature).data
    body["properties"]["flag"] = True
    rebuilt = FeatureSerializer(data=body)
    assert rebuilt.is_valid(), rebuilt.errors
    new_feature = rebuilt.save()

    assert new_feature.properties.get("flag") is True
    assert isinstance(new_feature.properties.get("flag"), bool)


def test_properties_float_round_trip(make_feature):
    """A float value survives a round-trip and stays float (not int-coerced)."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    body = FeatureSerializer(feature).data
    body["properties"]["ratio"] = 3.14
    rebuilt = FeatureSerializer(data=body)
    assert rebuilt.is_valid(), rebuilt.errors
    new_feature = rebuilt.save()

    assert new_feature.properties.get("ratio") == 3.14
    assert isinstance(new_feature.properties.get("ratio"), float)
```

- [ ] **Step 2: Run the new tests to verify they pass on master**

```bash
docker compose exec web pytest features/tests/test_serializers.py::test_properties_boolean_round_trip features/tests/test_serializers.py::test_properties_float_round_trip -v
```

Expected: `2 passed`. If they fail on master, stop and investigate —
the bug is on the backend, not the frontend, and the spec/plan need
revision.

---

## Task 3: Fix `edit.js` `update_value_input` (GREEN for Bug 1)

**Files:**
- Modify: `frontend/static/js/edit.js:124, 150–172`

- [ ] **Step 1: Change `const value_input` to `let`**

In `frontend/static/js/edit.js`, find the line that creates the
original `<input>` inside `render_add_new_row`:

```js
const value_input = document.createElement("input");
value_input.className = "form-control form-control-sm";
value_cell.appendChild(value_input);
```

Change `const` to `let`:

```js
let value_input = document.createElement("input");
value_input.className = "form-control form-control-sm";
value_cell.appendChild(value_input);
```

- [ ] **Step 2: Reassign `value_input` after each `replaceWith`**

In the same function, in `update_value_input`, change the bool
branch from:

```js
if (type_select.value === "bool") {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  for (const value of ["true", "false"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  value_input.replaceWith(select);
  value_input.value = "true";
  value_input.disabled = true;
}
```

to:

```js
if (type_select.value === "bool") {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  for (const value of ["true", "false"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  value_input.replaceWith(select);
  value_input = select;
  value_input.value = "true";
}
```

(Drop the `value_input.disabled = true` line — it was vestigial and
no longer makes sense on a `<select>`.)

And change the else branch from:

```js
} else {
  const input = document.createElement("input");
  input.type = type_select.value === "str" ? "text" : "number";
  if (type_select.value === "float") input.step = "any";
  input.className = "form-control form-control-sm";
  value_input.replaceWith(input);
  value_input.disabled = false;
}
```

to:

```js
} else {
  const input = document.createElement("input");
  input.type = type_select.value === "str" ? "text" : "number";
  if (type_select.value === "float") input.step = "any";
  input.className = "form-control form-control-sm";
  value_input.replaceWith(input);
  value_input = input;
}
```

(Drop the `value_input.disabled = false` line — the original input
was never disabled, so this line was a no-op.)

- [ ] **Step 3: Run the E2E test, expect all 4 add-new assertions pass; the map-panel test still fails**

```bash
node e2e/add-new-property.mjs
```

Expected: the test still fails, but the failure is now in the
`/map/` side panel section (the boolean row is still
`contentEditable`, not a `<select>`). The four add-new assertions
should all pass.

If the test still fails on the add-new assertions, double-check
that the `let` change took effect and that both `replaceWith`
branches have the reassignment. If the failure message references
a wire-type mismatch on any of the four types, the fix is
incomplete.

---

## Task 4: Fix `render_property_row` for booleans in `edit.js` (GREEN for Bug 2)

**Files:**
- Modify: `frontend/static/js/edit.js:29–99`

- [ ] **Step 1: Add the boolean branch to `render_property_row`**

In `render_property_row`, find the current cell-creation block:

```js
const value_cell = document.createElement("td");
value_cell.contentEditable = "true";
value_cell.spellcheck = false;
value_cell.textContent = value === null || value === undefined ? "" : String(value);
value_cell.dataset.original = value_cell.textContent;
value_cell.dataset.type = typeof value;
```

Replace it with the boolean-aware version:

```js
const value_cell = document.createElement("td");
if (typeof value === "boolean") {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  for (const option_value of ["true", "false"]) {
    const option = document.createElement("option");
    option.value = option_value;
    option.textContent = option_value;
    if (String(value) === option_value) option.selected = true;
    select.appendChild(option);
  }
  value_cell.appendChild(select);
  select.addEventListener("change", async () => {
    const next = select.value === "true";
    try {
      await api.patch(`/api/features/${feature_id}/`, {
        properties: { [key]: next },
      });
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
      select.value = String(value);
    }
  });
} else {
  value_cell.contentEditable = "true";
  value_cell.spellcheck = false;
  value_cell.textContent = value === null || value === undefined ? "" : String(value);
  value_cell.dataset.original = value_cell.textContent;
  value_cell.dataset.type = typeof value;
}
```

The existing `keydown` and `blur` listeners on the `contentEditable`
cell only fire for the non-boolean branch, so they stay attached as
before (they're added after the cell creation, regardless of which
branch ran). Move them AFTER the `if/else` and gate them on the
`contentEditable` path, OR leave the listeners attached
unconditionally and let them be no-ops on the boolean branch (a
`<select>` has no `textContent` in the editable sense, so they
won't fire).

The simplest, lowest-risk move: leave the `keydown` and `blur`
listeners attached unconditionally. On a `<select>`, the `keydown`
listener's `event.key === "Enter"` and `Escape` branches won't
fire (selects handle their own keyboard), and the `blur` listener
checks `if (next_text === value_cell.dataset.original) return` —
for a select cell, `value_cell.dataset.original` is undefined and
the cell's `textContent` is the empty string, so the listener
returns early. Net effect: no-op, no breakage.

- [ ] **Step 2: Run the E2E test, expect the 4 add-new assertions pass; the map-panel test still fails**

```bash
node e2e/add-new-property.mjs
```

Expected: same as Task 3 step 3 — add-new green, map-panel red.
(Editing existing booleans in `/edit/` is exercised by an
intermediate test in Task 5, not by this E2E directly.)

---

## Task 5: Fix `render_property_row` for booleans in `map-panel.js` (GREEN for Bug 3)

**Files:**
- Modify: `frontend/static/js/map-panel.js:38–90`

- [ ] **Step 1: Add the boolean branch to `render_property_row`**

In `map-panel.js`, find the cell-creation block:

```js
const value_cell = document.createElement("td");
value_cell.contentEditable = "true";
value_cell.spellcheck = false;
value_cell.textContent = value === null || value === undefined ? "" : String(value);
value_cell.dataset.original = value_cell.textContent;
```

Replace with:

```js
const value_cell = document.createElement("td");
if (typeof value === "boolean") {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  for (const option_value of ["true", "false"]) {
    const option = document.createElement("option");
    option.value = option_value;
    option.textContent = option_value;
    if (String(value) === option_value) option.selected = true;
    select.appendChild(option);
  }
  value_cell.appendChild(select);
  select.addEventListener("change", async () => {
    const feature_id = row.closest("aside").dataset.featureId;
    const next = select.value === "true";
    try {
      await api.patch(`/api/features/${feature_id}/`, {
        properties: { [key]: next },
      });
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
      select.value = String(value);
    }
  });
} else {
  value_cell.contentEditable = "true";
  value_cell.spellcheck = false;
  value_cell.textContent = value === null || value === undefined ? "" : String(value);
  value_cell.dataset.original = value_cell.textContent;
}
```

Leave the existing `keydown` and `blur` listeners on
`value_cell` attached unconditionally. They are no-ops on a
`<select>` (a select has no `textContent` in the editable sense,
so the listeners' early-return conditions trigger).

The category row (lines 106–151) is already a `<select>` and is
untouched.

- [ ] **Step 2: Run the E2E test, expect everything passes**

```bash
node e2e/add-new-property.mjs
```

Expected: the test prints
`OK: add-new property sends the right wire type for str/int/float/bool; round-trip preserves type; /map/ side panel renders Boolean as <select>.`
and exits 0.

If the test fails on the map-panel section, double-check that
`typeof value === "boolean"` actually fires for the `test_bool`
property. If the panel `open_feature` handler fetches the feature
via the API first, the value should be a JSON boolean
`true` / `false` (the test verified this in Task 3).

---

## Task 6: Final verification

- [ ] **Step 1: Run the full backend test suite to ensure no regression**

```bash
docker compose exec web pytest 2>&1 | tail -3
```

Expected: pass count is the previous baseline + 2 (the two new
round-trip cases). No other test should fail.

- [ ] **Step 2: Run all three E2E tests for regression**

```bash
node e2e/edit-page-editable.mjs 2>&1 | tail -1
node e2e/search-bar-ux.mjs 2>&1 | tail -1
node e2e/map-color-style.mjs 2>&1 | tail -1
node e2e/add-new-property.mjs 2>&1 | tail -1
```

Expected: all four print their respective `OK:` lines. The
`edit-page-editable` test creates a feature with no boolean
properties, so the boolean branch in `render_property_row` is
never exercised there; no regression expected.

- [ ] **Step 3: Run pre-commit on the changed files**

```bash
pre-commit run --files frontend/static/js/edit.js frontend/static/js/map-panel.js e2e/add-new-property.mjs features/tests/test_serializers.py
```

Expected: all hooks pass. If `biome` or `prettier` re-formats,
re-read the file to make sure the change is still correct, then
re-run. If `ruff` reformats the pytest additions, re-read the
test file and re-run.

If `prettier` or `ruff` reformatted anything, also run the full
pre-commit:

```bash
pre-commit run --all-files
```

- [ ] **Step 4: Show the user the diff and stop**

```bash
git status --short
git diff --stat
```

Report the file list and the unStaged status to the user. **Do not
commit implementation files** — the user will review the diff and
commit when ready.

---

## Self-Review

**1. Spec coverage:**
- §Goals 1, 4: Task 3 (edit.js `let` + reassign) + Task 1 (E2E wire-type assertions).
- §Goals 2, 3: Task 4 (edit.js boolean branch) + Task 5 (map-panel.js boolean branch) + Task 1 (E2E `<select>` assertion).
- §Goals 5: implicit — the existing `contentEditable` code is preserved verbatim for non-boolean values.
- §Test plan: Task 1 (E2E file) + Task 2 (2 pytest cases) + Task 5 step 2 (full GREEN).

**2. Placeholder scan:** no TBD/TODO/"implement later" markers. All code blocks are complete and runnable.

**3. Type / name consistency:** `typeof value === "boolean"`, `select.value === "true"`, `Feature.Category`, `api.patch`, `clear_alert`, `show_alert` — all match the spec and the existing codebase.

**4. Listener attachment decision:** the `keydown` and `blur` listeners on `value_cell` in `render_property_row` are left attached unconditionally. On a `<select>` cell, they are no-ops. This avoids restructuring the existing function and keeps the diff minimal.
