# Per-Page Search Bars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the search bar out of the top nav into per-page components. The map page gets its existing dropdown + fly-to behaviour. The edit page gets a new live-filter input that updates the table as the user types. No commit steps are included; the user will commit after reviewing the diff.

**Architecture:** Refactor the existing `search.js` from a 137-line file with an auto-init side effect into a small shared core exporting `fetchMatches`, `renderDropdownRow`, and `DEBOUNCE_MS`. Two new sibling modules (`search-map.js`, `search-edit.js`) each own one page's search bar. Each page template (`map.html`, `edit.html`) carries its own search bar markup. `base.html` loses the top-nav search entirely. CSS rules are renamed to match the per-page IDs. Two E2E tests are updated; one new E2E is added.

**Tech Stack:** Vanilla JS modules (no build step), Playwright (`node`) for E2E, Django + DRF backend (untouched), Bootstrap 5 CSS classes (untouched), plain CSS for sizing.

**Spec:** `docs/superpowers/specs/2026-06-15-search-bar-redesign.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/static/js/search.js` | refactor | Shared core: `fetchMatches`, `renderDropdownRow`, `DEBOUNCE_MS`. Auto-init removed. |
| `frontend/static/js/search-map.js` | create | Map page component: input → debounce → dropdown → `map:fly-to`. Exports `initMapSearch()`. |
| `frontend/static/js/search-edit.js` | create | Edit page component: input → debounce → `onChange` callback. Exports `initEditSearch({ onChange })`, `readQuery()`. |
| `frontend/static/js/map.js` | modify | Add import of `initMapSearch`; call it inside `initMap()`. |
| `frontend/static/js/edit.js` | modify | Add import of `initEditSearch`; call it inside `initEdit()`; change `load_page()` to accept `{ search }` and add a request-id race guard. |
| `frontend/templates/map.html` | modify | Add `#map-search-container` floating top-left, sibling to `#map-toolbar`. |
| `frontend/templates/edit.html` | modify | Add `#edit-search-input` in the existing top toolbar row alongside the sort dropdown. |
| `frontend/templates/base.html` | modify | Remove `#search-container`, `#search-input`, `#search-dropdown` markup and the `search.js` script tag. |
| `frontend/static/css/site.css` | modify | Replace `#search-input` / `.search-dropdown` rules with `#map-search-input`, `#edit-search-input`, `#map-search-dropdown`. |
| `e2e/search-bar-ux.mjs` | modify | Update three selectors: `#search-input` → `#map-search-input`, `#search-dropdown` → `#map-search-dropdown`, `#search-container` → `#map-search-container`. Assertions unchanged. |
| `e2e/edit-page-editable.mjs` | modify | Update selectors in `checkSearchDropdownHumanizedLabel`: `#search-input` → `#map-search-input`, `#search-dropdown` → `#map-search-dropdown`. |
| `e2e/edit-page-search.mjs` | create | New E2E for edit-page live filter. 9 assertions, self-contained (registers user, creates 7 test features, drives the input). |

No backend, model, serializer, URL, or other JS file changes.

---

## Task 1: Update the two E2E tests for the new map-page IDs (RED)

The two existing E2E tests that touch the map page's search bar use the old IDs. Updating them first proves the test code is in a known-failing state — when we add the new map page search component in Task 2, the test should go GREEN.

**Files:**
- Modify: `e2e/search-bar-ux.mjs:89-90, 95, 111, 131, 143, 164`
- Modify: `e2e/edit-page-editable.mjs:249-250, 264, 270`

- [ ] **Step 1: Update selectors in `e2e/search-bar-ux.mjs`**

Apply these find-and-replace operations across the file (each is unique in context; use a larger surrounding snippet if `edit` reports multiple matches):

| Find | Replace with | Lines |
|---|---|---|
| `#search-input` | `#map-search-input` | 89, 95 (locator + waitForSelector args) |
| `#search-dropdown` | `#map-search-dropdown` | 90, 95, 111, 131, 143 |
| `"search-input"` (literal string, no `#` prefix) | `"map-search-input"` | 164 — the focused-id assertion compares `document.activeElement?.id` against the literal string |

There is no `getElementById("search-input")` call in this file; the only call to `getElementById` is `document.getElementById("search-dropdown")` in the visible-overflow helper, which is covered by the row above.

- [ ] **Step 2: Update selectors in `e2e/edit-page-editable.mjs`**

Inside `checkSearchDropdownHumanizedLabel` (lines 247-273), replace:
- `await page.waitForSelector("#search-input", ...)` → `await page.waitForSelector("#map-search-input", ...)`
- `await page.locator("#search-input").fill("Amsterdam")` → `await page.locator("#map-search-input").fill("Amsterdam")`
- `document.getElementById("search-dropdown")` → `document.getElementById("map-search-dropdown")`
- `document.querySelectorAll("#search-dropdown .badge")` → `document.querySelectorAll("#map-search-dropdown .badge")`

The rest of the file (categories, name cell, color picker, etc.) is untouched.

- [ ] **Step 3: Run the updated E2E tests, expect RED**

```bash
node e2e/search-bar-ux.mjs
```

Expected: FAIL with a Playwright timeout — `#map-search-input` is not in the DOM (the new markup doesn't exist yet). The error message will mention `waiting for selector "#map-search-input"` or the locator will fail to fill.

```bash
node e2e/edit-page-editable.mjs
```

Expected: FAIL inside `checkSearchDropdownHumanizedLabel` for the same reason — the new ID doesn't exist yet.

- [ ] **Step 4: Confirm the failures are the expected ones**

If you see a different error (e.g. `auth/me` 401, network error, or a failure in a different assertion), stop and investigate — the test setup is wrong, not the production code.

The 9 remaining assertions in `e2e/edit-page-editable.mjs` (everything before `checkSearchDropdownHumanizedLabel`) should still pass on this run, because the test starts by creating and editing a feature, and only later exercises the search dropdown.

---

## Task 2: Add the map page search component (GREEN)

**Files:**
- Refactor: `frontend/static/js/search.js` (replace entire file)
- Create: `frontend/static/js/search-map.js`
- Modify: `frontend/templates/map.html:2-15` (insert the new container)
- Modify: `frontend/static/js/map.js:1-6, 154-199` (import + call)
- Modify: `frontend/static/css/site.css:6-16` (replace rules)

- [ ] **Step 1: Refactor `frontend/static/js/search.js` to a shared core**

Replace the entire file with:

```js
// Shared search core.
//
// Used by /map/ (dropdown + fly-to) and /edit/ (live table filter).
// Page-specific wiring lives in search-map.js and search-edit.js.

import { api } from "./api.js";
import { getCategoryLabel } from "./categories.js";

const DEBOUNCE_MS = 250;
const LIST_URL = "/api/features/";

function getName(properties) {
  const name = properties?.name;
  return typeof name === "string" && name ? name : "(unnamed)";
}

function getColor(properties) {
  const color = properties?.color;
  if (typeof color === "string" && /^#[0-9a-fA-F]{3,8}$|^rgb/.test(color)) {
    return color;
  }
  return "#cccccc";
}

async function fetchMatches(query) {
  const body = await api.get(
    `${LIST_URL}?search=${encodeURIComponent(query)}&page=1`,
  );
  return body.results || [];
}

function renderDropdownRow(feature, { onClick }) {
  const properties = feature.properties || {};
  const name = getName(properties);
  const color = getColor(properties);
  const category_label = getCategoryLabel(properties?.category);
  const geometry_type = feature.geometry?.type || "Unknown";

  const row = document.createElement("li");
  row.className =
    "list-group-item search-result-row d-flex align-items-center gap-2";
  row.dataset.featureId = feature.id;

  const swatch = document.createElement("span");
  swatch.className = "swatch";
  swatch.style.background = color;

  const nameSpan = document.createElement("span");
  nameSpan.className = "flex-grow-1";
  nameSpan.textContent = name;

  if (category_label) {
    const badge = document.createElement("span");
    badge.className = "badge bg-secondary";
    badge.textContent = category_label;
    row.appendChild(badge);
  }

  const typeSpan = document.createElement("span");
  typeSpan.className = "text-muted small";
  typeSpan.textContent = geometry_type;

  row.appendChild(swatch);
  row.appendChild(nameSpan);
  row.appendChild(typeSpan);

  row.addEventListener("click", onClick);
  return row;
}

export { DEBOUNCE_MS, fetchMatches, renderDropdownRow };
```

- [ ] **Step 2: Create `frontend/static/js/search-map.js`**

```js
import { DEBOUNCE_MS, fetchMatches, renderDropdownRow } from "./search.js";

let debounce_handle = null;
let _active_index = -1;

function closeDropdown() {
  const dropdown = document.getElementById("map-search-dropdown");
  if (!dropdown) return;
  dropdown.classList.add("d-none");
  dropdown.innerHTML = "";
  _active_index = -1;
}

async function performSearch(query) {
  if (!query) {
    closeDropdown();
    return;
  }
  try {
    const results = await fetchMatches(query);
    const dropdown = document.getElementById("map-search-dropdown");
    if (!dropdown) return;
    dropdown.innerHTML = "";
    for (const feature of results) {
      dropdown.appendChild(
        renderDropdownRow(feature, {
          onClick: () => {
            window.dispatchEvent(
              new CustomEvent("map:fly-to", { detail: { feature } }),
            );
            closeDropdown();
            const input = document.getElementById("map-search-input");
            if (input) {
              input.value = "";
              input.focus();
            }
          },
        }),
      );
    }
    dropdown.classList.remove("d-none");
  } catch (_error) {
    closeDropdown();
  }
}

function onInput(event) {
  if (debounce_handle) clearTimeout(debounce_handle);
  const query = event.target.value.trim();
  debounce_handle = setTimeout(() => performSearch(query), DEBOUNCE_MS);
}

function onKeyDown(event) {
  if (event.key === "Escape") closeDropdown();
}

function onDocumentClick(event) {
  const container = document.getElementById("map-search-container");
  if (container && !container.contains(event.target)) closeDropdown();
}

function initMapSearch() {
  const input = document.getElementById("map-search-input");
  if (!input) return;
  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKeyDown);
  document.addEventListener("click", onDocumentClick);
}

export { initMapSearch };
```

- [ ] **Step 3: Add the search container to `frontend/templates/map.html`**

In `map.html`, find the `<div class="position-relative">` opening tag on line 2. Right after it (before the `<div id="map"></div>` on line 3), insert:

```html
    <div class="position-absolute top-0 start-0 m-3" id="map-search-container" style="z-index: 1030">
        <div class="position-relative">
            <input
                type="search"
                class="form-control form-control-sm"
                id="map-search-input"
                placeholder="Search by name..."
                autocomplete="off"
            />
            <ul class="list-group position-absolute w-100 search-dropdown d-none" id="map-search-dropdown"></ul>
        </div>
    </div>
```

The new container is a sibling of the existing `#map-toolbar` (line 4) and `#map` (line 3). The `z-index: 1030` matches the toolbar.

- [ ] **Step 4: Wire `initMapSearch()` into `frontend/static/js/map.js`**

At the top of `map.js`, add a fourth import after the existing three:

```js
import { initMapSearch } from "./search-map.js";
```

Inside `initMap()` (lines 154-199), add `initMapSearch();` as the first line of the function body, before `map_state.map = build_ol_map();`. Final shape of the start of `initMap()`:

```js
function initMap() {
  if (!auth.requireAuth()) return;
  initMapSearch();
  map_state.map = build_ol_map();
  if (!map_state.map) return;
  // ... rest unchanged ...
}
```

- [ ] **Step 5: Update the CSS rules in `frontend/static/css/site.css`**

Replace the `#search-input` and `.search-dropdown` rules (lines 6-16) with:

```css
#map-search-input,
#edit-search-input {
    width: 280px;
}

#map-search-dropdown {
    min-width: 320px;
    max-height: 360px;
    overflow-y: auto;
    overflow-x: hidden;
    z-index: 1050;
}
```

The `.search-result-row` and `.swatch` rules (lines 50-60) stay as-is.

- [ ] **Step 6: Run the E2E tests, expect GREEN**

```bash
node e2e/search-bar-ux.mjs
```

Expected: PASS. Output should include the line `OK: search bar UX — no horizontal overflow; vertical scroll preserved; clear + focus on click.` and exit 0.

```bash
node e2e/edit-page-editable.mjs
```

Expected: PASS. The `checkSearchDropdownHumanizedLabel` step should now find `#map-search-input` and `#map-search-dropdown` and return the humanized category labels.

- [ ] **Step 7: Confirm visual placement**

The Playwright test takes a screenshot to `e2e/screenshots/search-bar-ux-dropdown.png`. Open it and verify the search input is at the top-left of the map (not in the top nav) and the dropdown is not clipped horizontally.

---

## Task 3: Write the failing edit-page E2E test (RED)

**Files:**
- Create: `e2e/edit-page-search.mjs`

- [ ] **Step 1: Create the E2E test file**

The test registers a fresh user, creates 7 test features (6 named "SearchTest `<Greek letter>`" and 1 named "OtherFeature") via the API, opens `/edit/`, and drives the new search input through 9 assertions.

```javascript
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
const EMAIL = `e2e-editsearch-${Date.now()}@example.test`;
const PASSWORD = "test-password-1234";
const SCREENSHOT_DIR = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "screenshots",
);

const FEATURE_NAMES = [
  "SearchTest Alpha",
  "SearchTest Bravo",
  "SearchTest Charlie",
  "SearchTest Delta",
  "SearchTest Echo",
  "SearchTest Foxtrot",
  "OtherFeature",
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
  await createTestFeatures(request, access);

  await page.goto(`${BASE}/edit/`, { waitUntil: "networkidle" });

  // ── Assertion 1: initial state ────────────────────────────────
  const input = page.locator("#edit-search-input");
  await input.waitFor({ state: "visible", timeout: 10000 });
  assert.equal(await input.inputValue(), "", "input should be empty on load");
  const initialNames = await rowNames(page);
  assert.ok(
    initialNames.includes("OtherFeature"),
    `initial table should include OtherFeature; got: ${JSON.stringify(initialNames)}`,
  );
  assert.equal(
    await page.locator("#page-indicator").textContent(),
    "Page 1",
    "page indicator should read 'Page 1' on load",
  );

  // ── Assertion 2: query that matches many ──────────────────────
  await input.fill("SearchTest");
  await waitForRowCount(page, 6);
  let names = await rowNames(page);
  assert.equal(names.length, 6, `expected 6 rows, got ${names.length}`);
  for (const name of names) {
    assert.ok(
      name.includes("SearchTest"),
      `row name "${name}" should contain SearchTest`,
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
  await input.fill("Alpha");
  await waitForRowCount(page, 1);
  names = await rowNames(page);
  assert.equal(names.length, 1, `expected 1 row, got ${names.length}`);
  assert.ok(
    names[0].includes("Alpha"),
    `row name "${names[0]}" should contain Alpha`,
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
  await input.fill("SearchTest");
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
  assert.ok(
    sortUrl.includes("search=SearchTest"),
    `sort request URL should include search=SearchTest: ${sortUrl}`,
  );
  assert.ok(
    sortUrl.includes("ordering=created_at"),
    `sort request URL should include ordering=created_at: ${sortUrl}`,
  );
  await waitForRowCount(page, 6);
  names = await rowNames(page);
  for (const name of names) {
    assert.ok(name.includes("SearchTest"), `row name "${name}" should contain SearchTest`);
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
      nextUrl.includes("search=SearchTest"),
      `next-page request URL should include search=SearchTest: ${nextUrl}`,
    );
    assert.ok(
      nextUrl.includes("page=2"),
      `next-page request URL should include page=2: ${nextUrl}`,
    );
    // Wait for the table to update with the page-2 results.
    await page.waitForTimeout(500);
  } else {
    console.log("(only one page of SearchTest results; skipped Next click)");
  }

  // ── Assertion 7: clear restores unfiltered list ──────────────
  await input.fill("");
  await page.waitForTimeout(400); // debounce + network
  const clearedNames = await rowNames(page);
  assert.ok(
    clearedNames.includes("OtherFeature"),
    `cleared table should include OtherFeature; got: ${JSON.stringify(clearedNames)}`,
  );
  assert.equal(
    await page.locator("#page-indicator").textContent(),
    "Page 1",
    "page indicator should reset to 'Page 1' after clear",
  );

  // ── Assertion 8: rapid typing collapses to last value ─────────
  await input.fill("SearchTest");
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
  await input.fill("SearchTest");
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

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

- [ ] **Step 2: Run the test to verify it fails (RED)**

```bash
node e2e/edit-page-search.mjs
```

Expected: FAIL with a Playwright timeout — `#edit-search-input` is not in the DOM (the new markup doesn't exist yet). The error will mention `waiting for selector "#edit-search-input"` or `fill` on the locator timing out.

- [ ] **Step 3: Confirm the failure is the expected one**

If the failure is something else (e.g. `auth/me` 401, or a failure in `createTestFeatures` because the user registration didn't work), stop and investigate — the test setup is wrong, not the production code.

The first three API calls in `createTestFeatures` should succeed (status 201 each) and `assert.equal` will catch any non-201. If they fail, check the response body and the backend logs.

---

## Task 4: Add the edit page search component (GREEN)

**Files:**
- Create: `frontend/static/js/search-edit.js`
- Modify: `frontend/templates/edit.html:1-14` (insert the input)
- Modify: `frontend/static/js/edit.js:1-3, 384-401, 403-424` (import + call + adjust `load_page`)

- [ ] **Step 1: Create `frontend/static/js/search-edit.js`**

```js
import { DEBOUNCE_MS } from "./search.js";

let debounce_handle = null;

function readQuery() {
  const input = document.getElementById("edit-search-input");
  return input ? input.value.trim() : "";
}

function onInput(event, { onChange }) {
  if (debounce_handle) clearTimeout(debounce_handle);
  const query = event.target.value.trim();
  debounce_handle = setTimeout(() => onChange({ search: query }), DEBOUNCE_MS);
}

function initEditSearch({ onChange }) {
  const input = document.getElementById("edit-search-input");
  if (!input) return;
  input.addEventListener("input", (event) => onInput(event, { onChange }));
}

export { initEditSearch, readQuery };
```

- [ ] **Step 2: Add the search input to `frontend/templates/edit.html`**

In `edit.html`, the current top toolbar (lines 3-14) has a `d-flex` row with the heading on the left and the sort dropdown on the right. Replace the entire `<div class="d-flex justify-content-between align-items-center mb-3">` block (lines 3-14) with:

```html
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h3 m-0">Edit Properties</h1>
        <div class="d-flex align-items-center gap-3">
            <div class="position-relative">
                <input
                    type="search"
                    class="form-control form-control-sm"
                    id="edit-search-input"
                    placeholder="Search by name..."
                    autocomplete="off"
                    style="width: 280px"
                />
            </div>
            <div class="d-flex align-items-center gap-2">
                <label for="sort-order" class="form-label m-0">Sort:</label>
                <select id="sort-order" class="form-select form-select-sm">
                    <option value="-updated_at" selected>Last updated (newest)</option>
                    <option value="updated_at">Last updated (oldest)</option>
                    <option value="-created_at">Created (newest)</option>
                    <option value="created_at">Created (oldest)</option>
                </select>
            </div>
        </div>
    </div>
```

The change: the right side of the row now wraps a `gap-3` flex group that holds the search input (with `width: 280px` matching the locked spec value) and the existing sort `<label>` + `<select>` (preserved verbatim, just nested in another `d-flex`).

- [ ] **Step 3: Adjust `load_page()` and `initEdit()` in `frontend/static/js/edit.js`**

Add a new import at the top of `edit.js` (after the existing three imports):

```js
import { initEditSearch, readQuery } from "./search-edit.js";
```

Add a module-level request-id counter above `load_page`:

```js
let _current_request_id = 0;
```

Replace `load_page()` (lines 384-401) with the version that accepts `{ search }` and drops stale responses:

```js
async function load_page({ search } = {}) {
  const query = search !== undefined ? search : readQuery();
  const request_id = ++_current_request_id;
  try {
    const base = `${LIST_URL}?page=${current_page}&ordering=${encodeURIComponent(current_ordering)}`;
    const final_url = query
      ? `${base}&search=${encodeURIComponent(query)}`
      : base;
    const body = await api.get(final_url);
    if (request_id !== _current_request_id) return;
    clear_table();
    for (const feature of body.results || []) {
      render_feature(feature);
    }
    next_url = body.next;
    prev_url = body.prev;
    document.getElementById("page-prev").disabled = !prev_url;
    document.getElementById("page-next").disabled = !next_url;
    document.getElementById("page-indicator").textContent = `Page ${current_page}`;
    clear_alert();
  } catch (error) {
    if (request_id !== _current_request_id) return;
    show_alert(error?.message || "Failed to load features.");
  }
}
```

The two changes from the original:
1. Accepts optional `{ search }` param. If absent, falls back to the live value in `#edit-search-input` via `readQuery()`. This lets the sort / pagination handlers preserve the active search without threading the query through every call site.
2. Adds the request-id guard: increments `_current_request_id` before the fetch; if the response arrives after a newer request has started, it's silently dropped. This protects against slow `SearchTest` responses overwriting a fast `zzzzz` response (and matches the `map_state.in_flight_bbox` pattern in `map.js:103-112`).

Update `initEdit()` (lines 403-424) to call `initEditSearch`:

```js
function initEdit() {
  if (!auth.requireAuth()) return;
  initEditSearch({ onChange: load_page });
  document.getElementById("sort-order")?.addEventListener("change", (event) => {
    const next = event.target.value;
    if (ALLOWED_ORDERING.includes(next)) {
      current_ordering = next;
      current_page = 1;
      load_page();
    }
  });
  document.getElementById("page-prev")?.addEventListener("click", () => {
    if (current_page > 1) {
      current_page -= 1;
      load_page();
    }
  });
  document.getElementById("page-next")?.addEventListener("click", () => {
    current_page += 1;
    load_page();
  });
  load_page();
}
```

The only change vs. the original is the `initEditSearch({ onChange: load_page });` line as the first statement of the function body. The sort / pagination handlers call `load_page()` with no args, which now falls back to `readQuery()` and re-applies the active search.

- [ ] **Step 4: Run the E2E test, expect GREEN**

```bash
node e2e/edit-page-search.mjs
```

Expected: PASS. Output should include `OK: edit-page search — live filter, sort/pagination preserve search, clear restores list, debounce collapses rapid typing.` and exit 0.

- [ ] **Step 5: Confirm the screenshot looks right**

Open `e2e/screenshots/edit-page-search.png`. The search input should be at the top right of the page (next to the sort dropdown), the table below should show 6 rows named "SearchTest …", and the pagination indicator should read "Page 1".

---

## Task 5: Remove the top-nav search from `base.html`

Once both pages have their own search bars, the shared top-nav search is redundant. Removing it eliminates the dead auto-init path and prevents the "search bar in nav that does nothing" UX.

**Files:**
- Modify: `frontend/templates/base.html:14-36, 41` (delete the search block and the search.js script tag)

- [ ] **Step 1: Delete the search block from the nav**

In `base.html`, delete lines 20-29 (the entire `#search-container` `<div>`, including the `<input>` and `<ul>`).

The nav element (lines 14-36) becomes:

```html
<nav class="navbar navbar-expand bg-light border-bottom px-3" id="top-nav">
    <a class="navbar-brand fw-bold" href="/">GeoJSON</a>
    <ul class="navbar-nav me-auto">
        <li class="nav-item"><a class="nav-link" href="/map/" id="nav-map">Map</a></li>
        <li class="nav-item"><a class="nav-link" href="/edit/" id="nav-edit">Edit Properties</a></li>
    </ul>
    <div id="user-menu" class="d-flex align-items-center gap-2">
        <span id="user-email" class="text-muted small"></span>
        <a class="btn btn-sm btn-outline-secondary d-none" id="login-link" href="/login/">Login</a>
        <a class="btn btn-sm btn-outline-secondary d-none" id="register-link" href="/register/">Register</a>
        <button class="btn btn-sm btn-outline-secondary d-none" id="logout-button" type="button">Logout</button>
    </div>
</nav>
```

- [ ] **Step 2: Delete the search.js script tag**

On line 41, delete:

```html
        <script type="module" src="{% static 'js/search.js' %}"></script>
```

The remaining scripts (`api.js`, `auth.js`) stay. The two page-specific `search-map.js` and `search-edit.js` are loaded transitively via `map.js` and `edit.js` (each imports the one it needs).

- [ ] **Step 3: Re-run both E2E tests, expect GREEN**

```bash
node e2e/search-bar-ux.mjs
node e2e/edit-page-search.mjs
node e2e/edit-page-editable.mjs
```

Expected: all three PASS. The map-page search still works (it lives on the map page now); the edit-page search still works; the edit-page editing still works.

---

## Task 6: Final verification

- [ ] **Step 1: Run the full backend test suite**

```bash
docker compose exec web pytest 2>&1 | tail -3
```

Expected: `N passed, M warnings in T s` (whatever the current pass count is — should be the same as before, since no backend changed).

- [ ] **Step 2: Run pre-commit on the changed files**

```bash
pre-commit run --files \
    frontend/templates/base.html \
    frontend/templates/map.html \
    frontend/templates/edit.html \
    frontend/static/js/search.js \
    frontend/static/js/search-map.js \
    frontend/static/js/search-edit.js \
    frontend/static/js/map.js \
    frontend/static/js/edit.js \
    frontend/static/css/site.css \
    e2e/search-bar-ux.mjs \
    e2e/edit-page-editable.mjs \
    e2e/edit-page-search.mjs
```

Expected: all hooks pass. If `biome` reformats a JS file, re-read the file to make sure the change is still correct, then re-run. If `prettier` re-formats an HTML file, same.

- [ ] **Step 3: Run the full pre-commit (catches anything missed)**

```bash
pre-commit run --all-files
```

Expected: clean run. (Only run if step 2 reformatted anything.)

- [ ] **Step 4: Run the prior E2E tests for regression**

```bash
node e2e/map-color-style.mjs 2>&1 | tail -1
node e2e/edit-page-editable.mjs 2>&1 | tail -1
node e2e/add-new-property.mjs 2>&1 | tail -1
```

Expected: all three print their `OK:` lines.

- [ ] **Step 5: Show the user the diff and stop**

```bash
git status --short
git diff --stat
```

Report the file list and the unstaged status to the user. The user will review the diff and commit when ready.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task |
|---|---|
| §Goals 1 (map page search with dropdown + fly-to) | Task 2 |
| §Goals 2 (edit page search, live filter, no dropdown) | Tasks 3 + 4 |
| §Goals 3 (independent components) | Tasks 2 + 4 (two separate files: `search-map.js`, `search-edit.js`) |
| §Goals 4 (no top-nav search) | Task 5 |
| §Goals 5 (no backend change) | covered by no backend file in File Structure table |
| §Goals 6 (existing E2E continues to pass) | Task 1 (RED) + Task 2 (GREEN) |
| §Goals 7 (new E2E for edit page) | Tasks 3 + 4 |
| §Test plan §search-bar-ux.mjs (selector updates) | Task 1 |
| §Test plan §edit-page-search.mjs 9 assertions | Tasks 3 + 4 |
| §Test plan §backend tests (unchanged) | Task 6 step 1 |
| §Test plan §manual regression | Task 6 steps 3-4 |
| §Test plan §pre-commit / CI | Task 6 step 2 |
| §Risk assessment (request-id guard) | Task 4 step 3 (the guard is added in `load_page`) |

**2. Placeholder scan:** No TBD/TODO/"implement later" markers. All code blocks are complete and runnable. The `if (await nextButton.isEnabled())` branch in Task 3 step 6 is a legitimate test condition (the test still passes if there's only one page), not a placeholder.

**3. Type / name consistency:**
- `initMapSearch`, `initEditSearch`, `readQuery`, `fetchMatches`, `renderDropdownRow`, `DEBOUNCE_MS`, `_current_request_id` — all match the spec.
- IDs: `#map-search-input`, `#map-search-dropdown`, `#map-search-container`, `#edit-search-input` — all match the spec, all match the templates and JS files.
- Event: `map:fly-to` — matches `map.js:142` and `search.js` (old) and `search-map.js` (new).
- Test selectors: `#map-search-input`, `#map-search-dropdown`, `#edit-search-input` — match the new markup.
- CSS: `#map-search-input`, `#edit-search-input`, `#map-search-dropdown` — match the markup and the spec.
