# GeoJSON API — Frontend Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** [Foundation](./2026-06-12-geojson-foundation.md), [Auth](./2026-06-12-geojson-auth.md), [Feature API](./2026-06-12-geojson-feature-api.md)
**Required by:** CI

## 1. Purpose

Server-rendered HTML pages (home, map, edit, login, register),
top-nav with search, and the 8 small ES-module JS files that wire
up the OpenLayers map and the inline-edit tables. The frontend
hits only the auth and feature APIs defined in the [Auth
spec](./2026-06-12-geojson-auth.md) and the [Feature API
spec](./2026-06-12-geojson-feature-api.md); no other backend code
is consumed.

## 2. Routes and templates

| Route | Template | Auth | Purpose |
| --- | --- | --- | --- |
| `GET /` | `home.html` | none | Landing, two big buttons, login state. |
| `GET /map/` | `map.html` | required | OpenLayers map with bbox filter, draw, import, export, click-to-edit panel, search. |
| `GET /edit/` | `edit.html` | required | Server-paged table of all features and their properties. |
| `GET /login/` | `login.html` | none | Login form. |
| `GET /register/` | `register.html` | none | Registration form. |

`frontend/urls.py` routes these paths to view functions that
render templates. The auth templates POST form-encoded to
`/api/auth/login/` and `/api/auth/register/`; Django's CSRF
middleware protects those requests via `{% csrf_token %}`.

## 3. Top nav (visible on `/map/` and `/edit/`)

```
[Logo] [Map] [Edit Properties]   [🔍 Search by name...]   [user@email] [Logout]
```

Search bar is debounced 250ms. On input, GETs
`/api/features/?search=<query>&page=1`. The API returns up to 100
features per page; the frontend renders every feature in the page
response as a row in a scrollable Bootstrap dropdown below the
search input. The dropdown has a `max-height` of ~360px with
`overflow-y: auto` so it scrolls internally when the result set
is long, instead of growing past the bottom of the viewport. No
row-count cap and no "Load more" in the search dropdown —
scrolling is the only navigation. The implementation lives in
`frontend/static/css/site.css` (a `.search-dropdown` class) and
`frontend/static/js/search.js` (the scroll container is the same
`<ul>` that holds the rows, so keyboard arrow keys / PgDn / PgUp
work natively).

Each result row shows `properties.name` (falls back to
`"(unnamed)"` if the property is absent, empty, or not a string),
a `properties.color` swatch (gray `#cccccc` default if the property
is absent, empty, or not a valid CSS color string), a small
`properties.category` badge (human-readable label, e.g. "City" for
`"city"`; hidden if the property is absent, empty, or not a
string), and the geometry type. Click result → map flies to the
feature's centroid and opens the right-side edit panel. Esc closes
the dropdown.

The category badge label and the set of available categories are
fetched once on page load from
[`GET /api/categories/`](./2026-06-12-geojson-feature-api.md#3-categories-endpoint)
and cached for the session. If the user creates or edits a
feature with a `category` value not in the enum, the badge still
renders the raw string (no client-side validation) — the
open-properties model (see
[Feature Data Model spec §3](./2026-06-12-geojson-feature-model.md#3-featurecategory-enum))
permits non-enum values.

Features whose `properties.name` is absent or empty are not
matched by `?search=` (the search runs against
`properties->>'name'`, which is NULL for those rows) and
therefore do not appear in the dropdown. The seed data gives
every feature a `name` and a `color` (see
[Seed spec §5](./2026-06-12-geojson-seed.md#5-properties-and-category-pool)),
so the populated path is the common case for the demo, but the
API permits features without these properties and the frontend
must gracefully handle the missing-property case as described
above.

## 4. Map page features

1. **Viewport-driven bbox filter** with debounced 250ms `moveend`.
   "Load more" button appends subsequent pages.
2. **Draw mode** with Point/Line/Polygon picker. On draw finish, a
   Bootstrap modal asks for the new feature's `name` (the only
   property captured at draw time — additional properties are
   added on the edit page).
   - The modal has a single text input labeled "Name" with
     placeholder "My new feature" and `maxlength="200"`. The Save
     button is disabled until the input is non-empty (after
     trimming). The frontend sends
     `properties: {name: <user input>}`; the `name` key is
     hard-coded client-side, not user-chosen. This guarantees
     every new feature has a `name` and is therefore findable
     via `?search=` (§3 top-nav search) and consistent with seed
     features.
   - `name` is not unique — two features with the same name
     coexist; the open `properties` model imposes no uniqueness,
     and that is intentional.
   - Cancel paths (Cancel button, Esc key, click outside the
     modal, or starting a new draw) discard the in-progress
     geometry and exit draw mode without POSTing.
   - On a successful save, the modal closes, the draw interaction
     is deactivated (returns to normal pan/zoom), and the new
     feature is rendered on the map.
   - On a save error (e.g. token refresh failed, server
     4xx/5xx), the modal stays open, an inline Bootstrap alert
     is shown above the input with the server's error message,
     and the user can retry or cancel.
3. **Import `.geojson`**: file input, parsed with
   `ol/format/GeoJSON`, rendered on the map temporarily, "Save
   all to server" button batch-POSTs.
4. **Export `.geojson`**: assembles the in-memory features into a
   FeatureCollection, triggers a download.
5. **Click a feature** → right-side slide-in panel with a
   key/value table for that one feature. Inline-edit each property
   (PATCH on Enter, Esc cancels). "Delete feature" button at the
   panel bottom. The panel renders `properties.category` as a
   small dropdown of the `Feature.Category` enum values (see
   [Feature Data Model spec §3](./2026-06-12-geojson-feature-model.md#3-featurecategory-enum));
   the current value is pre-selected. Picking a new value and
   pressing Enter sends a PATCH that updates only the `category`
   key. A free-text "other…" option at the bottom of the dropdown
   lets the user type a non-enum value (the open-properties
   model permits it).
6. **Search bar** (§3).
7. **No `modify` interaction** in v1 (geometry editing is out of
   scope).
8. **No multi-select** in v1 (single-feature click only).

## 5. Edit page features

1. Server-paged table of all features. For each feature, a
   sub-table of `properties` rows: key, value, type badge,
   × delete, + add new.
2. Inline edit per row (PATCH on Enter, Esc cancels).
   - **Value cell is editable, key cell is not** in v1 (avoids
     breaking map color references and other client code that
     reads well-known keys by name).
   - **Type preservation.** When the user edits a value, the
     frontend preserves the original JSON type. For an `int`
     value the input is parsed as integer on save (rejected
     with an inline error if the user types a non-integer); for
     a `float` likewise; for a `bool` the input is a checkbox
     or `true`/`false` selector; for `null` the user must
     delete the row and add a new one (no inline null editor
     in v1); for `str` the input is a plain text field. The
     PATCH body sends the value at its original type, not as
     a string. To change a value's type (e.g.
     `int 5000` → `str "5000 people"`), the user must use the
     `× delete` button on the row and `+ add new` — there is
     no in-place type coercion in v1.
   - **`+ add new` row.** Below the existing property rows, the
     page shows a single button labeled `+ add new property`.
     Clicking it inserts a new row with three fields: a key
     input (max 100 chars, client-side trim), a value-type
     picker (4 options: `str`, `int`, `float`, `bool`), and a
     value input that switches editor based on the picked
     type (`<input type="text">` for `str`,
     `<input type="number" step="any">` for `int` and `float`,
     a checkbox for `bool`). The new row also has a cancel
     `×` button that removes the row from the in-memory edit
     set without saving.

     Rules for the new row:

     1. **Non-empty trimmed key.** The Save button on the new
        row is disabled until the key is non-empty after
        `String.prototype.trim()`. The server's
        `validate_properties()` re-validates and returns 400
        if the client-side check is bypassed.
     2. **No key collision.** The new key must not already
        exist as a property on this feature. The server
        enforces this; a 400 is returned with a body like
        `{"properties": "key 'name' already exists on this feature"}`.
        On a collision the page keeps the user's typed value
        and surfaces the server error in a banner at the top
        of the panel so the user can rename the key and retry.
     3. **Type-pinned value.** The value must match the picked
        type. The server validates and returns 400 on type
        mismatch (e.g. typing `1.5` into an `int` field).
        Inline error shown next to the input.
     4. **Limited value types in v1.** The type picker
        exposes only `str | int | float | bool`. `null`,
        `array`, and `object` are not creatable from the
        edit page in v1; the picker hides them. (A user can
        still see `null` / array / object values on imported
        features but cannot edit them on the edit page in
        v1 — see
        [Overview §18](./2026-06-12-geojson-api-design.md#18-out-of-scope-for-v1).)
     5. **Cancellable.** The new row's `×` button removes it
        from the in-memory edit set. The row's existence is
        purely client-side until the user clicks the panel's
        main Save button.
     6. **Server error surfacing.** If the server returns 400
        (or any 4xx/5xx) on the PATCH that includes the new
        row, the page shows a Bootstrap alert at the top of
        the panel with the server's error message and keeps
        all in-memory edits intact so the user can correct
        and retry.

     **Interaction with the system-managed `name` property.**
     With the v2 invariant that every feature must have a
     `name` property and that `name` cannot be deleted
     (deferred to v2, see
     [Overview §20](./2026-06-12-geojson-api-design.md#20-open-follow-ups-not-blocking-implementation)),
     the `+ add new` mechanic is constrained as follows:

     - `+ add new` cannot be used to add a *second* `name` row.
       The collision check above covers this naturally (the
       server returns 400 "key 'name' already exists on this
       feature"). The UX implication: a user attempting to add
       a row keyed `name` sees the collision banner and is
       expected to either edit the existing `name` value or
       pick a different key.
     - A user cannot use `+ add new` to remove or rename `name`,
       because the PATCH is additive only (PATCH semantics;
       keys not in the body are preserved). The
       system-managed `name` row is therefore never disturbed
       by `+ add new`.
     - The server's `validate_properties()` is extended by one
       line to enforce "the `name` key, if present, must be a
       non-empty `str`". This is the server-side half of the
       "name is required and undeletable" invariant; the
       client-side half is the draw-modal and edit-page rules
       above that ensure every new feature is created with a
       `name` and that `name` cannot be set to an empty value
       via inline edit.
3. Pagination Prev/Next at the bottom (disabled when `prev` /
   `next` is `null`).
4. Sort dropdown (default `-updated_at`). The four options map
   1:1 to the API's `ordering` allowlist (`created_at`,
   `-created_at`, `updated_at`, `-updated_at`) so the dropdown
   and the URL parameter cannot drift.
5. No bulk-edit, no multi-select.

## 6. Static assets

- `frontend/static/css/site.css` — ≤ 100 lines. Includes the
  right-side panel slide-in animation and the search dropdown
  styling (`.search-dropdown` with `max-height: 360px;
  overflow-y: auto` so the dropdown scrolls internally rather
  than overflowing the viewport).
- `frontend/static/js/`:
  - `api.js` — `fetch` wrapper with token refresh on 401.
  - `auth.js` — login/logout, token storage in `localStorage`.
  - `map.js` — OpenLayers map setup, bbox debounce, feature
    rendering.
  - `map-draw.js` — draw interaction.
  - `map-import.js` — GeoJSON import/export.
  - `map-panel.js` — right-side panel for inline edit.
  - `search.js` — top-nav search dropdown with debounce and
    fly-to.
  - `edit.js` — edit-page table with inline edit and
    pagination.

Each module is a small ES module loaded with
`<script type="module">` from the template. `api.js` and `auth.js`
are shared via `{% include %}`-style script tags in `base.html`.

## 7. Token storage trade-off

Tokens live in `localStorage`, which is XSS-readable. This is the
standard pragmatic choice for a small SPA with no
`httpOnly`-cookie infrastructure; the alternative (`httpOnly`
cookies + CSRF tokens on the API) is significantly more code and
requires splitting the auth flow between cookie + header. v1
accepts this trade-off. Mitigations:

- `Content-Security-Policy: default-src 'self'; script-src 'self'
  https://cdn.jsdelivr.net; style-src 'self'
  https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data:;
  connect-src 'self'` is set in `prod.py` (see
  [Foundation spec §10](./2026-06-12-geojson-foundation.md#10-content-security-policy))
  to reduce XSS blast radius (no inline scripts, no third-party
  scripts beyond the CDN).
- No user-supplied content is ever rendered as HTML in the
  frontend (always as text or via safe `textContent`).
- Frontend has no third-party analytics, ads, or comment
  widgets.
- Logout deletes both `access` and `refresh` from `localStorage`.

A `v2` migration to `httpOnly` cookies + CSRF is a follow-up (see
[Overview §20](./2026-06-12-geojson-api-design.md#20-open-follow-ups-not-blocking-implementation)).
