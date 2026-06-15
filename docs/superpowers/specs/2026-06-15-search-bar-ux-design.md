# Search bar UX — clear on click, no horizontal scroll

Date: 2026-06-15
Status: approved
Scope: `/map/` top-nav search bar
Type: bug fix (UI)

## Problem

The top-nav search bar (`#search-input` + `#search-dropdown`, defined in
`frontend/templates/base.html:20-29`) has two UX defects:

### Bug A — drop-down scrolls horizontally and bleeds onto the map

Measured on 2026-06-15 with `e2e/capture-search-bugs.mjs` against
`http://127.0.0.1:8000/map/`, typing `gr` (single result, "Groningen"):

- Drop-down visible width (`clientWidth`): **177 px** — set by the input's
  `form-control-sm` Bootstrap class.
- Row content width (`scrollWidth`): **236 px** — swatch + name + "Province"
  badge + "Polygon" type.
- Result: the row visually extends 59 px past the drop-down's right edge. With
  long names or longer badge labels (e.g. "Nature reserve"), the overflow is
  larger. The user can scroll horizontally inside the drop-down, which is
  unusual UX for a search list.
- The visible "transparency" effect: because the `.list-group` element does
  not set `overflow-x: hidden`, the row's white `list-group-item` background
  extends into the area where the OL map is rendered underneath, making the
  row look like a tab sticking out of the search bar and overlaying the map.

Reproduced in `e2e/screenshots/search-bug-A-*.png` (full page, drop-down only,
after horizontal scroll).

### Bug B — search text persists after clicking a result

After clicking a row, the map correctly flies to the feature and the drop-down
closes, but the input still shows the query the user typed
(`inputValueAfterClick: "gr"`). The user has to manually clear it before
typing the next search. The map panel for the selected feature is also open
at this point, so the user is likely to want to search for something
different next.

Reproduced in `e2e/screenshots/search-bug-B-after-click.png`.

## Root cause

### Bug A — `frontend/static/css/site.css:6-10`

```css
.search-dropdown {
    max-height: 360px;
    overflow-y: auto;   /* enables vertical scroll; no overflow-x rule */
    z-index: 1050;
}
```

`overflow-y: auto` and no `overflow-x: hidden` means horizontal overflow is
visible. Combined with a narrow input (177 px) and content that needs ~320
px, the row content bleeds.

### Bug B — `frontend/static/js/search.js:78-81`

```js
row.addEventListener("click", () => {
  window.dispatchEvent(new CustomEvent("map:fly-to", { detail: { feature } }));
  closeDropdown();
});
```

`closeDropdown()` empties the drop-down and hides it, but never touches the
input's value or focus.

## Goals

1. Drop-down never scrolls horizontally; rows never bleed onto the map.
2. Drop-down never becomes narrower than the longest expected row content
   (~320 px is enough for swatch + longest Dutch name + longest badge label
   "Nature reserve" + longest type "MultiPolygon" + padding).
3. After clicking a result, the search text clears and the input is focused
   so the user can immediately type the next search.
4. No regression in existing behaviour: empty query closes drop-down, Escape
   closes drop-down, click-outside closes drop-down, vertical scroll still
   works for long result lists.

## Non-goals

- Keyboard navigation (arrow keys + Enter to fly to highlighted result).
- Type-ahead highlighting / fuzzy match / search-syntax.
- Mobile layout (< 320 px viewport).
- API or backend changes.
- Debounce timing changes.

## Design

### CSS — `frontend/static/css/site.css`

```css
#search-input {
    width: 280px;            /* was: default form-control-sm ≈ 177 px */
}

.search-dropdown {
    min-width: 320px;        /* safety net: never narrower than content */
    max-height: 360px;       /* unchanged */
    overflow-y: auto;        /* unchanged: vertical scroll for long lists */
    overflow-x: hidden;      /* NEW: clip any horizontal overflow */
    z-index: 1050;           /* unchanged */
}
```

Why both a width and a min-width:
- `width: 280px` on the input gives most of the visible width (long enough
  to read a 3–4 word Dutch name while typing).
- `min-width: 320px` on the drop-down guarantees the drop-down is at least
  as wide as the longest expected row, even if the input is later made
  narrower for compact layouts.
- `overflow-x: hidden` is a belt-and-braces guarantee that even if some
  future change makes a row wider, it cannot bleed onto the map.

### JS — `frontend/static/js/search.js`

In `renderRows`'s click handler (lines 78–81), add two lines after
`closeDropdown()`:

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

The defensive `if (input)` matches the pattern used elsewhere in the file
(`isVisible()`, `getName()`, etc.) — the search bar may be absent on
templates that don't extend the same base.

### Behaviour matrix

| User action | Before | After |
|---|---|---|
| Type query, get 1+ result, click row | Drop-down closes, map flies, text persists | Drop-down closes, map flies, **text clears, input focused** |
| Type query, get 7+ results | Vertical scroll appears | Vertical scroll appears (unchanged) |
| Type long result (e.g. "a") | Horizontal scroll appears, row bleeds onto map | **No horizontal scroll; no bleed** |
| Press Escape | Drop-down closes, text persists | Drop-down closes, text persists (unchanged) |
| Click outside drop-down | Drop-down closes, text persists | Drop-down closes, text persists (unchanged) |
| Type, press Enter with no row highlighted | Nothing | Nothing (unchanged — keyboard nav is out of scope) |
| Empty query | Drop-down closes | Drop-down closes (unchanged) |

### Files touched

- `frontend/static/css/site.css` — modify (1 new rule on `#search-input`, 2
  new properties on `.search-dropdown`).
- `frontend/static/js/search.js` — modify (2 new lines in click handler,
  1 new `getElementById` lookup, 1 defensive null check).
- `e2e/search-bar-ux.mjs` — **NEW** Playwright E2E.

No backend, no API, no other JS files.

## Test plan

### `e2e/search-bar-ux.mjs` (NEW)

Six assertions, no DB writes, idempotent, no fixture needed.

1. Register + login a fresh user.
2. Navigate to `/map/`, wait for `window.__geojsonMap`.
3. **No-horizontal-overflow with 1 result.** Type `"gr"`, wait for first
   result to render, assert
   `dropdown.scrollWidth === dropdown.clientWidth`.
4. **No-horizontal-overflow with many results.** Clear, type `"a"`, wait
   for ≥ 5 results, assert `dropdown.scrollHeight > dropdown.clientHeight`
   (vertical scroll present) AND `dropdown.scrollWidth === dropdown.clientWidth`
   (no horizontal).
5. **Clear-on-click.** Clear, type `"gr"`, click first result, wait for
   `map:fly-to` response.
   - Assert `input.value === ""`.
   - Assert `document.activeElement.id === "search-input"`.
6. **Visual confirmation.** Type `"gr"`, save drop-down screenshot to
   `e2e/screenshots/search-bar-ux-dropdown.png` (gitignored).

### Backend tests

None. No serializer, view, or model changes.

### Manual regression

- Verify `/edit/` still works (search bar is in the top nav, present on
  every page; the change is CSS + a click handler in shared code, so
  `/edit/` is implicitly covered).
- Verify map panel still opens on `map:fly-to` (it does; the new lines run
  after `map:fly-to` is dispatched).

## Risk assessment

- **Low.** Change is 3 lines of CSS (1 new rule, 2 new properties) and 5
  lines of JS in shared code paths.
  The drop-down is rendered on every page (it's in the top nav), so any
  visual regression would be obvious.
- The `input.value = ""` is not undoable. If the user accidentally clicks
  the wrong row, they have to retype the query. This matches the user's
  explicit request and the common behaviour of most search UIs.
- Focus shift may interfere with screen readers. The previous behaviour
  was that focus stayed on the search input throughout, so a screen-reader
  user already has the search input as their focus. After the fix, focus
  is re-asserted on the (now empty) search input. Net effect: no
  accessibility regression, possibly an improvement (screen reader
  announces the cleared value).

## Out of scope (future work)

- Arrow-key navigation through results.
- Enter key flying to the first/highlighted result.
- Showing keyboard shortcuts in a tooltip.
- Mobile layout / responsive search bar.
