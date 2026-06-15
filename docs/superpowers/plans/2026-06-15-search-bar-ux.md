# Search Bar UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two search-bar UX bugs: (A) drop-down scrolls horizontally and bleeds onto the map; (B) search text persists in the input after clicking a result.

**Architecture:** Three small changes. CSS rule to widen the input and clip horizontal overflow; one click-handler line to clear + focus the input; one new Playwright E2E that locks both behaviours in.

**Tech Stack:** Playwright (`node`), vanilla CSS, vanilla JS (no build step). Django + Bootstrap 5 in the surrounding stack (untouched).

**Spec:** `docs/superpowers/specs/2026-06-15-search-bar-ux-design.md`

**Working rule for this session:** keep all implementation changes unStaged; do not commit implementation files. Spec/plan commits (this file and the design) are committed; implementation diffs stay unStaged for user review. Pre-commit and the test suite must still pass.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/static/css/site.css` | modify | Width of input + clip horizontal overflow on drop-down |
| `frontend/static/js/search.js` | modify | Clear + focus input on row click |
| `e2e/search-bar-ux.mjs` | create | Playwright E2E that locks in both fixes |

No backend, API, view, or template changes.

---

## Task 1: Write the failing E2E test (RED)

**Files:**
- Create: `e2e/search-bar-ux.mjs`

- [ ] **Step 1: Create the E2E test file**

The test exercises both bugs and asserts all three acceptance criteria from the spec. It exits with code 1 on any failure (matching the convention in `e2e/map-color-style.mjs` and `e2e/edit-page-editable.mjs`).

```javascript
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
  await page.waitForTimeout(300); // let dropdown close
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
  // wait for the map:fly-to response so we know the click handler ran
  await page.waitForTimeout(500);

  const valueAfterClick = await input.inputValue();
  const focusedId = await page.evaluate(() => document.activeElement?.id);
  console.log("after click — value:", JSON.stringify(valueAfterClick), "focusedId:", focusedId);
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
```

- [ ] **Step 2: Run the test to verify it fails (RED)**

```bash
node e2e/search-bar-ux.mjs
```

Expected: FAIL. The first assertion (1-result horizontal overflow) throws because the drop-down is 177 px wide and content is 236 px (`scrollWidth > clientWidth`). The error message will include `scrollWidth 236` and `clientWidth 177`.

- [ ] **Step 3: Confirm the failure is the expected one**

Look for the assertion message in the output:

```
Bug A: drop-down has horizontal overflow with 1 result (scrollWidth 236 > clientWidth 177)
```

If you see a different failure (e.g. `auth/me` 401, or a network error), stop and investigate — the test setup is wrong, not the production code.

If the database is empty, the preflight will abort with a clear instruction
to seed first. Run:

```bash
docker compose exec web python manage.py seed_features
```

---

## Task 2: Fix the CSS (GREEN for Bug A)

**Files:**
- Modify: `frontend/static/css/site.css:1-10`

- [ ] **Step 1: Widen the search input**

In `frontend/static/css/site.css`, add a new rule for `#search-input` above the `.search-dropdown` block (the file is currently only 55 lines, so the change is local).

Replace this block at the top of the file:

```css
#map {
    width: 100%;
    height: calc(100vh - 56px);
}

.search-dropdown {
    max-height: 360px;
    overflow-y: auto;
    z-index: 1050;
}
```

with:

```css
#map {
    width: 100%;
    height: calc(100vh - 56px);
}

#search-input {
    width: 280px;
}

.search-dropdown {
    min-width: 320px;
    max-height: 360px;
    overflow-y: auto;
    overflow-x: hidden;
    z-index: 1050;
}
```

Changes:
- New `#search-input { width: 280px; }` rule (1 line).
- Added `min-width: 320px;` to `.search-dropdown`.
- Added `overflow-x: hidden;` to `.search-dropdown`.

- [ ] **Step 2: Run the E2E test, expect Bug A assertions pass, Bug B still fails**

```bash
node e2e/search-bar-ux.mjs
```

Expected: the test still fails, but the failure is now in Bug B (the `input.value` assertion) — not the scrollWidth/clientWidth assertion. The two Bug A assertions should both pass:

```
many-result measure: { clientWidth: 320, scrollWidth: 320, clientHeight: 360, scrollHeight: ... }
```

- [ ] **Step 3: Visually confirm the drop-down looks right**

Open `e2e/screenshots/search-bar-ux-dropdown.png`. The "Province | Groningen" row should fit on one line, with no cut-off and no bleed onto the map.

If the row is still cut off, double-check that `width: 280px` actually applied (Bootstrap's `form-control-sm` may set `width: 100%` at some breakpoints; if so, the rule needs higher specificity — use `#search-input.form-control { width: 280px; }`).

---

## Task 3: Fix the JS click handler (GREEN for Bug B)

**Files:**
- Modify: `frontend/static/js/search.js:78-81`

- [ ] **Step 1: Update the click handler**

In `frontend/static/js/search.js`, find the click handler in `renderRows` (currently lines 78–81):

```js
    row.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("map:fly-to", { detail: { feature } }));
      closeDropdown();
    });
```

Replace with:

```js
    row.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("map:fly-to", { detail: { feature } }));
      closeDropdown();
      const input = document.getElementById("search-input");
      if (input) {
        input.value = "";
        input.focus();
      }
    });
```

- [ ] **Step 2: Run the E2E test, expect all assertions pass**

```bash
node e2e/search-bar-ux.mjs
```

Expected: the test prints `OK: search bar UX — no horizontal overflow; vertical scroll preserved; clear + focus on click.` and exits 0.

- [ ] **Step 3: Visually confirm the input clears after click**

Open the screenshot one more time and click any result in the dev browser (or just trust the `input.value` assertion in the test — the screenshot is only taken before the click). The screenshot taken at the end of the test is the "before click" state; the post-click state is covered by the assertion.

---

## Task 4: Final verification

- [ ] **Step 1: Run the full backend test suite to ensure no regression**

```bash
docker compose exec web pytest 2>&1 | tail -3
```

Expected: `163 passed, 62 warnings in 18.XXs` (or whatever the current pass count is — should be the same as before, since no backend changed).

- [ ] **Step 2: Run pre-commit on the changed files**

```bash
pre-commit run --files frontend/static/css/site.css frontend/static/js/search.js e2e/search-bar-ux.mjs
```

Expected: all 11 hooks pass. If `ruff` or `biome` reformats, re-read the file to make sure the change is still correct, then re-run.

If `prettier` re-formats the JS, also run the full pre-commit:

```bash
pre-commit run --all-files
```

- [ ] **Step 3: Run the two prior E2E tests for regression**

```bash
node e2e/map-color-style.mjs 2>&1 | tail -1
node e2e/edit-page-editable.mjs 2>&1 | tail -1
```

Expected: both print their respective `OK:` lines. The search bar is in the shared top nav, so any regression in `site.css` or `search.js` would surface here too.

- [ ] **Step 4: Show the user the diff and stop**

```bash
git status --short
git diff --stat
```

Report the file list and the unStaged status to the user. **Do not commit implementation files** — the user will review the diff and commit when ready.

---

## Self-Review

**1. Spec coverage:**
- §Goals 1–4: Task 2 (CSS) + Task 3 (JS).
- §Test plan §1–§6: Task 1 (test file) + Task 2 step 2 (partial GREEN) + Task 3 step 2 (full GREEN).
- §Risk assessment: not a code change; covered by the conservative "5 lines JS" delta.
- §Out of scope: explicitly excluded.

**2. Placeholder scan:** no TBD/TODO/"implement later" markers. All code blocks are complete and runnable.

**3. Type / name consistency:** `#search-input`, `#search-dropdown`, `.search-dropdown`, `getElementById("search-input")`, `__geojsonMap`, `map:fly-to` — all match the spec and the existing codebase.
