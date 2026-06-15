# Edit properties — correct value types + Boolean dropdown

Date: 2026-06-15
Status: approved
Scope: `/edit/` add-new-property flow + `/edit/` and `/map/` side panel
property display for Booleans.
Type: bug fix (data integrity + UI)

## Problem

Three related defects in the property add/edit UI:

### Bug 1 — Add-new property sends an empty value to the backend

On `/edit/`, the `+ add new property` flow lets the user pick a
type (`str`, `int`, `float`, `bool`), enter a key, and enter a value.
For **every** type, the PATCH sent to `/api/features/{id}/` carries
`properties: { <key>: "" }` (empty string) regardless of what the user
typed.

Reproduction (manual, against `http://127.0.0.1:8000/edit/`):

1. Click `+ add new property`.
2. Type `key = "test"`, leave `type = str` (default), type
   `value = "hello"`, click Save.
3. `GET /api/features/{id}/` → `properties.test === ""` (not `"hello"`).

Same symptom for `int` and `float`. For `bool`, the result is even
worse: backend always receives `false` (see Bug 3 for the wire-type
side of the same root cause).

### Bug 2 — Existing boolean properties in `/edit/` are edited as text

If a feature already has a boolean property (`properties: { is_active: true }`),
`/edit/` renders the value cell as a `contentEditable` `<td>`. The user can
type `"false"` (text), and on blur the PATCH sends
`properties: { is_active: "false" }` — a **string**, not a boolean.

The backend's `_is_json_serializable` accepts strings, so the request
succeeds and the database row is silently corrupted: `true` (bool)
becomes `"false"` (str). Subsequent reads return the wrong type.

### Bug 3 — Boolean in the `/map/` side panel has no true/false UI

`map-panel.js` renders every property as a `contentEditable` cell. The
blur handler at lines 72–79 attempts a string↔number coercion at save
time, but has no equivalent for booleans. The user has no way to
express a boolean value other than typing `"true"` or `"false"`, and
the result is the same string-type corruption as Bug 2.

## Root cause

### Bug 1 — `frontend/static/js/edit.js:124, 150–172`

```js
const value_input = document.createElement("input");
value_cell.appendChild(value_input);
// ...
function update_value_input() {
  if (type_select.value === "bool") {
    const select = document.createElement("select");
    // ... add true / false options ...
    value_input.replaceWith(select);   // ← DOM swap
    value_input.value = "true";        // ← writes to DETACHED original
    value_input.disabled = true;       // ← writes to DETACHED original
  } else {
    const input = document.createElement("input");
    // ... configure type=...
    value_input.replaceWith(input);    // ← DOM swap
    value_input.disabled = false;      // ← writes to DETACHED original
  }
}
```

`replaceWith()` puts the new element in the DOM but the `value_input`
variable (declared `const`) still references the original input,
which is now **detached**. The user types into the new (in-DOM)
element, but the save handler reads `value_input.value` — i.e. from
the detached original, which was never touched and always has
`value = ""`.

For `bool`, the detached original is the empty text input created on
line 124, so `value_input.value === "true"` is always `false` and the
PATCH always sends `false`.

### Bug 2 — `frontend/static/js/edit.js:41, 64–88`

`render_property_row()` creates a `contentEditable` cell for **every**
property value, with `value_cell.dataset.type = typeof value`. The
blur handler (lines 64–88) only special-cases `"number"`:

```js
let parsed = next_text;
if (value_cell.dataset.type === "number") {
  // ... Number() coercion ...
}
// For "boolean", "string", "undefined": fall through with parsed = next_text (string)
```

For `dataset.type === "boolean"`, the PATCH body is the literal text
the user typed — a string, not a boolean.

### Bug 3 — `frontend/static/js/map-panel.js:38–90`

`render_property_row()` in the map panel is structurally the same as
`edit.js`'s: `contentEditable` cell + heuristic save-time coercion
(lines 72–79) that only handles numbers. No boolean branch exists,
so a boolean value is always edited as a string.

## Goals

1. **`/edit/` add-new flow** correctly sends the typed value with the
   right JS type for all four types (`str`, `int`, `float`, `bool`).
2. **Existing boolean properties** in `/edit/` are rendered as a
   `<select>` with `true` / `false` options, not a `contentEditable`
   text cell. PATCHing the property sends a JSON boolean.
3. **Boolean properties** in the `/map/` side panel are also a
   `<select>`, matching the `/edit/` control. PATCHing sends a JSON
   boolean.
4. The backend round-trip preserves the wire type: a `bool` PATCH
   reads back as a `bool` (not a string), a `float` PATCH reads back
   as a `float`, an `int` PATCH reads back as an `int`, a `str` PATCH
   reads back as a `str`.
5. No regression: existing `contentEditable` behaviour for string and
   number properties in both UIs is unchanged.

## Non-goals

- Re-typing an existing property as a different type (no UI to flip
  `"is_active": true` to a string). The type is whatever was last
  written, inferred from `typeof`.
- Adding a `+ add new property` button to the `/map/` side panel.
- Adding a search/filter UI for property keys.
- Changing the existing string↔number heuristic in either UI.

## Design

### JS — `frontend/static/js/edit.js`

Three changes:

1. **Line 124**: `const value_input` → `let value_input`.

2. **`update_value_input()` (lines 150–172)**: after each
   `value_input.replaceWith(newElement)`, reassign the variable so
   subsequent reads see the new element:

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
     value_input = select;          // ← NEW: reassign
     value_input.value = "true";
   } else {
     const input = document.createElement("input");
     input.type = type_select.value === "str" ? "text" : "number";
     if (type_select.value === "float") input.step = "any";
     input.className = "form-control form-control-sm";
     value_input.replaceWith(input);
     value_input = input;            // ← NEW: reassign
   }
   ```

   The `value_input.disabled = true` and `value_input.disabled = false`
   lines are removed; they were vestigial from when `value_input` was
   the original text input and had no effect on the new element
   anyway (and disabling a `<select>` makes no UX sense).

3. **`render_property_row()` (lines 29–99)**: when `typeof value === "boolean"`,
   render a `<select>` with `true` / `false` options instead of a
   `contentEditable` cell. On `change`, PATCH the boolean value. The
   `×` delete button still works the same way. The `dataset.type`
   and `dataset.original` attributes become unused for this branch.

   ```js
   function render_property_row(feature_id, key, value) {
     const tbody = document.getElementById("features-tbody");
     const row = document.createElement("tr");
     row.dataset.key = key;
     const key_cell = document.createElement("td");
     key_cell.textContent = key;
     key_cell.className = "text-muted small";
     const value_cell = document.createElement("td");
     const action_cell = document.createElement("td");
     // ... delete button unchanged ...
     row.appendChild(key_cell);
     row.appendChild(value_cell);
     row.appendChild(action_cell);
     tbody.appendChild(row);

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
           const updated = await api.patch(`/api/features/${feature_id}/`, {
             properties: { [key]: next },
           });
           clear_alert();
         } catch (error) {
           show_alert(error?.message || "Save failed.");
           select.value = String(value);  // revert
         }
       });
     } else {
       value_cell.contentEditable = "true";
       value_cell.spellcheck = false;
       value_cell.textContent = value === null || value === undefined ? "" : String(value);
       value_cell.dataset.original = value_cell.textContent;
       value_cell.dataset.type = typeof value;
       // ... keydown + blur listeners unchanged ...
     }

     // ... delete button listener unchanged ...
   }
   ```

### JS — `frontend/static/js/map-panel.js`

**`render_property_row()` (lines 29–104)**: same boolean branch as
`edit.js`. When `typeof value === "boolean"`, render a `<select>`
with `true` / `false` options; PATCH the boolean on `change`.
Everything else (string, number, null, `×` delete) keeps current
behaviour.

```js
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
  // existing contentEditable cell code, unchanged
}
```

The category row (lines 106–151) is already a `<select>` and is not
touched.

### Behaviour matrix

| Surface | Property | Before | After |
|---|---|---|---|
| `/edit/` add-new | `str`, `int`, `float` | PATCH sends `""` (empty string) | PATCH sends typed value with correct JS type |
| `/edit/` add-new | `bool` | PATCH always sends `false` | PATCH sends selected `true` / `false` |
| `/edit/` existing | `boolean` value | `contentEditable` cell; edit sends string, corrupts type | `<select>` with `true` / `false`; PATCH sends JSON boolean |
| `/edit/` existing | `string`, `number` value | `contentEditable` (unchanged) | `contentEditable` (unchanged) |
| `/map/` side panel | `boolean` value | `contentEditable` cell; edit sends string, corrupts type | `<select>` with `true` / `false`; PATCH sends JSON boolean |
| `/map/` side panel | `string`, `number` value | `contentEditable` (unchanged) | `contentEditable` (unchanged) |
| Backend `GET /api/features/{id}/` | any | echoes the stored JSON | echoes the stored JSON, type preserved across PATCH |

### Files touched

- `frontend/static/js/edit.js` — modify (1 `let`, 2 reassignments, 1
  added boolean branch in `render_property_row`).
- `frontend/static/js/map-panel.js` — modify (1 added boolean branch
  in `render_property_row`).
- `e2e/add-new-property.mjs` — **NEW** Playwright E2E.
- `features/tests/test_serializers.py` — extend (2 new round-trip
  tests: boolean, float).

No CSS, no API, no model, no other JS files.

## Test plan

### `e2e/add-new-property.mjs` (NEW)

Self-contained: registers a fresh user, creates a fresh test feature
via the API, runs the UI, cleans up. Idempotent.

For each of `{str, int, float, bool}`:

1. Open `/edit/`, find the test feature row.
2. Click `+ add new property`.
3. Set up a request listener that captures the **POST body** of the
   `PATCH /api/features/{id}/` call.
4. Fill `key = test_<type>`, pick the `<type>` from the type
   `<select>`, fill the value (`"hello"`, `42`, `3.14`, `true`),
   click Save.
5. Assert the captured PATCH body has
   `properties.test_<type>` of the expected JS `typeof` and value.
6. `GET /api/features/{id}/` via the test's `request` fixture and
   assert the round-tripped value has the matching JSON type on the
   server.

Plus a `/map/` side panel test:

7. Open `/map/`, wait for `window.__geojsonMap`, open the test
   feature in the side panel.
8. For the `test_bool` property, assert the row contains a
   `<select>` (not a `contentEditable` cell).
9. Change the `<select>` to the other value, capture the PATCH
   body, assert it is a JSON boolean.
10. Screenshot `/edit/` to `e2e/screenshots/add-new-property.png`
    (gitignored).

Screenshots confirm visual sanity; the wire-type assertions are the
load-bearing checks.

### `features/tests/test_serializers.py` (extend)

Add two `pytest.mark.django_db` cases:

- `test_properties_boolean_round_trip`: build a payload with
  `properties: {"flag": True}`, run through `FeatureSerializer`,
  assert the rebuilt instance has `properties["flag"] is True`.
- `test_properties_float_round_trip`: same with
  `{"ratio": 3.14}`, assert `properties["ratio"] == 3.14` and
  `isinstance(properties["ratio"], float)`.

These exist to prove the **backend** preserves type across a
round-trip. They are independent of the frontend bug — they would
pass on master — but they form a safety net for the round-trip
assertions in the E2E.

### Manual regression

- `/edit/` existing tests in `e2e/edit-page-editable.mjs` still
  pass: name, color, category editing and the category-options
  consistency check are untouched. The boolean-property rendering
  change only fires for properties whose value is `typeof === "boolean"`,
  and the test feature created in that suite has no such
  properties.
- `/map/` search bar still works (`e2e/search-bar-ux.mjs` covers
  it).
- Map panel category dropdown options still match the canonical
  list (covered by `e2e/edit-page-editable.mjs`).

## Risk assessment

- **Low–medium.** The `replaceWith` reassignment is a 2-line fix in
  well-isolated code. The boolean branch in `render_property_row`
  is a new code path gated on `typeof value === "boolean"`; existing
  property types keep their old code path verbatim.
- **Wire-type risk.** The PATCH body for boolean properties
  previously sent a string. The change sends a JSON boolean. The
  backend's `_is_json_serializable` accepts both, but a stale client
  reading the response may have type assumptions. Since this app has
  no other clients, the risk is contained to the frontend code being
  shipped.
- **The "str" add-new with empty input.** If the user clicks Save on
  a new `str` property without typing a value, the fix makes the
  PATCH send `properties: { key: "" }` (the literal empty string),
  not nothing. The backend accepts it. This matches what the UI
  always suggested (`String(value)` semantics). Not a regression.
- **No accessibility regression.** `<select>` is keyboard- and
  screen-reader-accessible by default; it is at least as accessible
  as `contentEditable`.

## Out of scope (future work)

- Re-typing an existing property as a different type.
- Adding a `+ add new property` button to the `/map/` side panel.
- A "type" column on existing property rows in `/edit/`.
- A search/filter for property keys when a feature has many of them.
