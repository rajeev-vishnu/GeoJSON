# Per-page search bars — independent map and edit components

Date: 2026-06-15
Status: approved (brainstorming complete)
Scope: `/map/` and `/edit/` search bars; `frontend/templates/base.html` top-nav search removal.
Type: refactor (split shared component) + new feature (edit-page live filtering)

## Problem

The current top-nav search bar (defined in `frontend/templates/base.html:20-29`,
implemented in `frontend/static/js/search.js`) is shared by every page in the
app. On `/map/`, typing shows a dropdown of matching features and clicking a
result dispatches `map:fly-to` (`frontend/static/js/map.js:142`) which zooms
the map and opens the side panel — useful behavior. On `/edit/`, the same
search bar shows the same dropdown, but clicking a result does nothing
useful: there's no map to fly to, and the edit page is a paginated table
(`frontend/static/js/edit.js:384-401`) that has no knowledge of the search
results. The search bar is effectively a "does nothing on the edit page"
component.

The desired behavior is for each page to own its own search experience:

- **Map page:** a per-page search bar with the same dropdown + fly-to
  behavior as today.
- **Edit page:** a per-page search bar that, as the user types, filters the
  existing table of features to those whose `name` matches the query.
  Pagination, sort, and the table itself update live; no dropdown is shown.
- **Top nav:** no search bar at all. `base.html` no longer carries search
  markup or loads the shared search script.

The locked-in UX details from `2026-06-15-search-bar-ux-design.md` (no
horizontal overflow on the dropdown, clear input and refocus after clicking
a row, `width: 280px` on the input) carry over verbatim to the map page's
per-page bar.

## Goals

1. The `/map/` search bar lives within the map page (floating top-left) and
   retains the same dropdown + fly-to behavior as today.
2. The `/edit/` search bar lives within the edit page (in the table
   toolbar row) and filters the table live as the user types. No dropdown
   is shown.
3. The two bars are independent components: each can be added, removed, or
   modified without touching the other.
4. The top nav (`base.html`) carries no search markup or script.
5. The existing `?search=` API filter (`features/views.py:62-64`) is reused
   unchanged. No new backend endpoints.
6. The existing `e2e/search-bar-ux.mjs` continues to pass (with selector
   updates for the renamed IDs).
7. New E2E `e2e/edit-page-search.mjs` locks in the edit-page filter
   behavior.

## Non-goals

- Searching across fields other than `properties.name` (no category / color
  / arbitrary-property matching).
- Highlighting the matched substring in dropdown rows.
- Server-side full-text search (Postgres FTS / trigram) — `__icontains`
  is fast enough on the seed dataset.
- Keyboard navigation through dropdown results (arrow keys + Enter).
- Mobile / responsive layout for either search bar.
- A search bar on `/`, `/login/`, or `/register/`.
- Changing the dropdown's CSS properties (width, min-width, max-height,
  overflow) from what `2026-06-15-search-bar-ux-design.md` locked in.

## Design

### File layout

| File | Action | Notes |
|---|---|---|
| `frontend/templates/base.html` | **MODIFY** | Remove `#search-container`, `#search-input`, `#search-dropdown` markup (lines 20-29) and the `search.js` script tag (line 41). |
| `frontend/templates/map.html` | **MODIFY** | Add per-page search bar (`#map-search-container` floating top-left) inside the existing `.position-relative` wrapper. |
| `frontend/templates/edit.html` | **MODIFY** | Add per-page search bar (`#edit-search-input`) in the existing top toolbar row alongside the sort dropdown. |
| `frontend/static/js/search.js` | **REFACTOR** | Reduce to a shared core: `fetchMatches(query)`, `renderDropdownRow(feature, { onClick })`, and a `DEBOUNCE_MS` constant. The existing auto-init `initSearch()` is removed. |
| `frontend/static/js/search-map.js` | **NEW** | Owns the map page's search bar. Wires input → dropdown → `map:fly-to`. Exports `initMapSearch()`. |
| `frontend/static/js/search-edit.js` | **NEW** | Owns the edit page's search bar. Wires input → `onChange` callback. Exports `initEditSearch({ onChange })`, `readQuery()`, `lastQuery`. |
| `frontend/static/js/map.js` | **MODIFY** | Add `import { initMapSearch } from "./search-map.js";` and call `initMapSearch()` inside `initMap()`. |
| `frontend/static/js/edit.js` | **MODIFY** | Add `import { initEditSearch } from "./search-edit.js";`; call `initEditSearch({ onChange: load_page })`; adjust `load_page` to read the current search value and thread it into the URL. |
| `frontend/static/css/site.css` | **MODIFY** | Replace `#search-input` / `.search-dropdown` rules with `#map-search-input` / `#edit-search-input` and `#map-search-dropdown`. Net line count unchanged. |
| `e2e/search-bar-ux.mjs` | **MODIFY** | Update selectors (`#search-input` → `#map-search-input`, etc.). Assertions unchanged. |
| `e2e/edit-page-search.mjs` | **NEW** | Playwright E2E for the edit-page live filter. |
| `features/tests/test_search.py` | unchanged | Backend API tests still pass. |

No backend, model, serializer, URL, or other JS file changes.

### Map page component

Markup in `frontend/templates/map.html`, sibling to the existing
`#map-toolbar`:

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

`z-index: 1030` matches the existing `#map-toolbar` inline style at
`map.html:4`.

Component in `frontend/static/js/search-map.js`:

```js
import { api } from "./api.js";
import { getCategoryLabel } from "./categories.js";
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

Behavior matrix — same as the current top-nav version, plus the locked-in
clear-and-refocus from `2026-06-15-search-bar-ux-design.md`:

| User action | Result |
|---|---|
| Type a query, get ≥ 1 result | Dropdown opens below the input |
| Click a row | `map:fly-to` dispatched → map zooms + side panel opens; input clears, input refocused |
| Type a query, get 0 results | Dropdown opens with no rows |
| Empty input | Dropdown closes |
| Press Escape | Dropdown closes; input keeps its value |
| Click outside input + dropdown | Dropdown closes; input keeps its value |
| Network error | Dropdown closes (no error UI; same as current) |

### Edit page component

Markup in `frontend/templates/edit.html`, in the existing top toolbar row
of the `container.py-3` block:

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

`width: 280px` matches the locked spec value. **No dropdown** — the table
is the result UI.

Component in `frontend/static/js/search-edit.js`:

```js
import { DEBOUNCE_MS, fetchMatches } from "./search.js";

let debounce_handle = null;
let _last_query = "";

function readQuery() {
  const input = document.getElementById("edit-search-input");
  return input ? input.value.trim() : "";
}

function onInput(event, { onChange }) {
  if (debounce_handle) clearTimeout(debounce_handle);
  const query = event.target.value.trim();
  _last_query = query;
  debounce_handle = setTimeout(() => onChange({ search: query }), DEBOUNCE_MS);
}

function initEditSearch({ onChange }) {
  const input = document.getElementById("edit-search-input");
  if (!input) return;
  input.addEventListener("input", (event) => onInput(event, { onChange }));
}

export { initEditSearch, readQuery };
```

`readQuery` is exported so `edit.js` can read the current value when the
user clicks "Previous" / "Next" or changes the sort dropdown — those
actions must preserve the active search.

### Changes to `load_page()` in `frontend/static/js/edit.js`

The existing function gains an optional `search` parameter, a request-id
guard for race conditions, and a debounce-clearing note. Final shape:

```js
let _current_request_id = 0;

async function load_page({ search } = {}) {
  const query = search !== undefined ? search : readQuery();
  const request_id = ++_current_request_id;
  try {
    const base = `${LIST_URL}?page=${current_page}&ordering=${encodeURIComponent(current_ordering)}`;
    const final_url = query
      ? `${base}&search=${encodeURIComponent(query)}`
      : base;
    const body = await api.get(final_url);
    if (request_id !== _current_request_id) return;  // stale response
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

And `initEdit()` wires the search component:

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

Behavior matrix (edit page):

| User action | Result |
|---|---|
| Type a query | After `DEBOUNCE_MS` (250 ms), table clears and re-fetches `?search=...&page=1&ordering=...` |
| Type a query, then change sort | Table re-fetches with current search value preserved; sort applies within filtered set |
| Type a query, then click "Next" | Table re-fetches next page of filtered set; search preserved |
| Type a query, get 0 results | Table is empty; pagination shows "Page 1" with both buttons disabled; no error banner |
| Clear the search input | Table returns to the unfiltered list, page 1 |
| Page load with no interaction | Existing behavior — `load_page()` with no args, no `?search=`, displays page 1 of all features |
| Network error | Existing `show_alert` banner; previous table contents cleared |
| Type `A` then `B` rapidly (race) | The later query's response wins; the earlier is dropped via the request-id guard |

### Shared core — `frontend/static/js/search.js`

Reduced to primitives that both page modules import:

```js
import { api } from "./api.js";
import { getCategoryLabel } from "./categories.js";

const DEBOUNCE_MS = 250;
const LIST_URL = "/api/features/";

async function fetchMatches(query) {
  const body = await api.get(`${LIST_URL}?search=${encodeURIComponent(query)}&page=1`);
  return body.results || [];
}

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

function renderDropdownRow(feature, { onClick }) {
  const properties = feature.properties || {};
  const name = getName(properties);
  const color = getColor(properties);
  const category_label = getCategoryLabel(properties?.category);
  const geometry_type = feature.geometry?.type || "Unknown";

  const row = document.createElement("li");
  row.className = "list-group-item search-result-row d-flex align-items-center gap-2";
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

The auto-init `initSearch()` call at the bottom of the old file is removed.
No other module imports it.

### CSS — `frontend/static/css/site.css`

Replace lines 6-16:

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

The `.search-result-row` and `.swatch` rules (lines 50-60) stay as-is —
class-based, used by the map dropdown.

### Visual placement

**Map page** — top-left floating, sibling to the existing top-right toolbar:

```
┌──────────────────────────────────────────────────────────────────────┐
│ [ Search by name... ▾ ]                              [Point] [Line] … │
│ [ Groningen                Polygon  Province  ]                      │
│ [ ...results...             ]                                        │
│                                                                      │
│                  (OL map fills the rest)                             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Edit page** — in the existing top toolbar row, right-aligned alongside
the sort dropdown:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Edit Properties                       [ Search by name...  ]  Sort: [▼]│
├──────────────────────────────────────────────────────────────────────┤
│ Name    Color  Category  Type   Properties                           │
│ ...                                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

On narrow viewports the flex wraps; the search and sort stack below the
heading. No responsive tweaks in scope.

### Authentication

Both pages already call `auth.requireAuth()` before any data fetch
(`map.js:155`, `edit.js:404`). The search fetches inherit the same
`Authorization: Bearer <access>` header from `api.js:42-44`. No new auth
wiring.

### Data flow summary

```
map page                                  edit page
─────────                                 ─────────
user types in #map-search-input           user types in #edit-search-input
        │                                          │
        ▼ (debounce 250 ms)                        ▼ (debounce 250 ms)
performSearch(query)                     onChange({ search: query })
        │                                          │
        ▼                                          ▼
fetchMatches(query)                       load_page({ search: query })
        │                                          │
        ▼ GET /api/features/?search=…&page=1       ▼ GET /api/features/?search=…&page=N&ordering=…
api.get                                  api.get
        │                                          │
        ▼ results[]                                ▼ { count, next, prev, results[] }
render <li> for each result               clear_table() + render_feature(f) for each result
        │                                          │
        ▼ user clicks row                          ▼
dispatch map:fly-to + clear input        user changes sort → load_page() (preserves search)
        │                                  user clicks Next → load_page() (preserves search)
        ▼                                           │
map.js flies + opens panel                         ▼
                                            pagination updated
```

## Test plan

### `e2e/search-bar-ux.mjs` (modify)

Three selector updates:
- `#search-input` → `#map-search-input`
- `#search-dropdown` → `#map-search-dropdown`
- `#search-container` → `#map-search-container`

All assertions unchanged (no horizontal overflow, vertical scroll present,
clear-and-refocus on click).

### `e2e/edit-page-search.mjs` — **NEW**

Self-contained: registers a fresh user (`Date.now()` suffix email),
creates ≥ 7 features with distinguishable names (6 named `SearchTest
<Greek letter>`, 1 named `OtherFeature`) via the API. Opens `/edit/`.
Drives `#edit-search-input`.

Assertions:

1. **Initial state.** On page load, table shows page 1 of all features;
   `#edit-search-input` is present and empty; pagination reads "Page 1".

2. **Type a query that matches many.** Type `SearchTest`. After the
   debounce window, table shows exactly 6 rows; pagination reads
   "Page 1"; all visible names contain "SearchTest".

3. **Type a query that matches a subset.** Clear, type `Alpha`. Table
   shows exactly 1 row; that row's name contains "Alpha".

4. **Type a query that matches zero.** Clear, type `zzzzz`. Table body
   is empty; pagination buttons disabled; no error banner.

5. **Sort is preserved across search.** With `SearchTest` typed, change
   the sort dropdown to "Created (oldest)". Verify (via network
   interception or by re-querying the API) that the request includes
   `&search=SearchTest` and `&ordering=created_at`. All 6 matching
   features are still visible.

6. **Pagination preserves search.** With `SearchTest` typed, click
   "Next" (if enabled). Verify the request includes `page=2` and
   `search=SearchTest`. All visible names contain "SearchTest".

7. **Clearing the input restores the unfiltered list.** With
   `SearchTest` typed, clear the input. After the debounce window, the
   table shows page 1 of all features, including the
   non-`SearchTest` `OtherFeature` row.

8. **Race-condition guard.** Type `SearchTest`, then within the
   debounce window type `zzzzz`. After the debounce + network, the
   table is empty (the `zzzzz` response won).

9. **Visual confirmation.** Screenshot `/edit/` with a typed query and
   filtered table to `e2e/screenshots/edit-page-search.png`
   (gitignored).

### Backend tests

`features/tests/test_search.py` is unchanged and still passes.

### Manual regression

- `/map/` — search bar floats top-left, dropdown opens on type, click
  flies the map and clears the input, side panel opens. Covered by
  updated `e2e/search-bar-ux.mjs`.
- `/edit/` — search bar filters the table live, sort/pagination
  preserve the active filter, clearing the input restores all features.
  Covered by `e2e/edit-page-search.mjs`.
- `/`, `/login/`, `/register/` — top nav has only "Map", "Edit
  Properties", and the user menu. No search input. No console errors.
- Map drawing / importing / exporting — unaffected.
- Map side panel — unaffected.

### Pre-commit / CI

`pre-commit run --all-files` after the change. Biome runs on the new JS
files, Prettier on the modified HTML, Ruff on no Python (no Python
changes). Expect clean run.

## Risk assessment

- **Low–medium.** The change is mostly a relocation of existing
  functionality plus one new component (the edit-page filter). The
  locked-in UX from `2026-06-15-search-bar-ux-design.md` is preserved
  verbatim on the map page.
- **Wire-type risk: none.** No backend / API changes. PATCH bodies are
  unchanged. Only GET requests with the existing `?search=` param.
- **Race-condition risk: mitigated.** The `request_id` guard in
  `load_page` matches the pattern in `map.js:103-112`. Locked in by
  assertion 8 of `e2e/edit-page-search.mjs`.
- **Test coverage risk: low.** The 2026-06-15 search-bar UX E2E was
  just written and locks in map-page behavior. The new edit-page E2E
  locks in the new behavior. The backend tests lock in the API.
- **Accessibility risk: low.** The map-page search retains the
  keyboard / click-outside / Escape behavior from before. The
  edit-page search is a single `<input type="search">` with no
  dropdown, which is the simplest possible accessibility story.

## Out of scope (future work)

- Highlight matched substring in dropdown rows.
- Search across other fields (category, color, arbitrary properties).
- Server-side full-text search / trigram.
- Keyboard navigation through dropdown results (arrow keys + Enter).
- Mobile / responsive layout for either search bar.
- A search bar on `/`, `/login/`, or `/register/`.
- "Name + category" search extension (would need a new API param).
- Showing match count in the edit page ("Showing 6 of 47 features").
