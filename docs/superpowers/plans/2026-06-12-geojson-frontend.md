# GeoJSON Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the server-rendered HTML pages, top-nav with search, OpenLayers map page with draw/import/export/inline-edit, edit-properties table, and 8 small ES-module JS files defined in the [Frontend spec](./../specs/2026-06-12-geojson-frontend.md).

**Architecture:** Five thin Django view functions render Jinja-free Django templates that include Bootstrap 5 and OpenLayers from the jsdelivr CDN. Eight small ES modules under `frontend/static/js/` call the auth and feature APIs via a shared `api.js` fetch wrapper that refreshes JWTs on 401. JWTs live in `localStorage`; pages that require auth gate themselves client-side. The Feature API gets two small server-side extensions (additive PATCH, `name` validation) to support the new edit-page mechanics.

**Tech Stack:** Django 5.1 templates, Bootstrap 5 (CDN), OpenLayers 10.x (CDN), vanilla ES modules, pytest-django for the Python half, biome for the JS half.

---

## File Structure

**New / modified server files**

| File                                 | Responsibility                                                                                                                                                                                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/views.py`                  | 5 view functions: `home`, `map_page`, `edit_page`, `login_page`, `register_page`. All just render templates; auth gating is client-side.                                                                                                          |
| `frontend/urls.py`                   | 5 URL patterns under namespace `frontend`.                                                                                                                                                                                                        |
| `features/serializers.py`            | Extend `FeatureSerializer.validate_properties` to enforce "if `name` is present, it must be a non-empty `str`". Override `partial_update` semantics so PATCH merges `properties` (keys absent from the body are preserved; `null` deletes a key). |
| `features/tests/test_serializers.py` | Add test for the `name` invariant.                                                                                                                                                                                                                |
| `features/tests/test_views.py`       | Update `test_partial_update` to assert additive behavior; add test for the null=delete case.                                                                                                                                                      |
| `features/views.py`                  | Pass the merged properties to the serializer in `partial_update`.                                                                                                                                                                                 |

**New templates (Django)**

| File                               | Responsibility                                                                                                                                                                                                          |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/templates/base.html`     | Shared layout: `<head>` with CSP-friendly Bootstrap 5 CSS, top nav (logo, Map, Edit Properties, search bar, user menu), `<script type="module">` for `api.js` + `auth.js`. Children fill `{% block content %}`.         |
| `frontend/templates/home.html`     | Landing page: two big buttons linking to `/map/` and `/edit/`; login-state-aware heading rendered by `auth.js`.                                                                                                         |
| `frontend/templates/login.html`    | Login form: `email`, `password` inputs, `{% csrf_token %}`, posts via JS to `/api/auth/login/`.                                                                                                                         |
| `frontend/templates/register.html` | Register form: `email`, `password`, `password_confirm`, posts via JS to `/api/auth/register/`.                                                                                                                          |
| `frontend/templates/map.html`      | Map page shell: full-bleed `<div id="map">`, top-right tool buttons (Draw, Import, Export), a hidden slide-in `<aside id="panel">` for inline edit, hidden Bootstrap modal `#draw-name-modal` with a single Name input. |
| `frontend/templates/edit.html`     | Edit page shell: server-paged table `#features-table`, sort dropdown `#sort-order`, prev/next pagination `#pagination`.                                                                                                 |

**New static assets**

| File                               | Responsibility                                                                                                                                                                                                                                                                                                                                                                          |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/static/css/site.css`     | `.search-dropdown` (max-height 360px, overflow-y auto), right-side panel slide-in keyframes, misc layout polish. Target ≤100 lines.                                                                                                                                                                                                                                                     |
| `frontend/static/js/api.js`        | `fetchJson(path, options)` wrapper that adds `Authorization: Bearer <access>`, refreshes the token on 401 (calls `/api/auth/refresh/`), stores the new pair in `localStorage`, and retries the original request once. Exports a single named export `api`.                                                                                                                              |
| `frontend/static/js/auth.js`       | Token storage (`getAccess`, `getRefresh`, `setTokens`, `clearTokens`), `login(email, password)`, `register(...)`, `logout()` (deletes both tokens + calls `me()` for the email). Exports `auth`.                                                                                                                                                                                        |
| `frontend/static/js/search.js`     | Top-nav search: debounce 250ms, GET `/api/features/?search=<q>&page=1`, render rows in `.search-dropdown`, click → `window.dispatchEvent(new CustomEvent('map:fly-to', {detail: {feature}}))`, Esc closes the dropdown. Caches the categories enum on page load from `/api/categories/`. Exports `initSearch()`.                                                                        |
| `frontend/static/js/map.js`        | OpenLayers map setup: WGS84 layer, OSM tile source, viewport bbox debounce (250ms) that refetches via `api`, "Load more" button appends pages, click handler opens the panel via `window.dispatchEvent`. Exports `initMap()`.                                                                                                                                                           |
| `frontend/static/js/map-draw.js`   | `Draw` interaction: Point/Line/Polygon picker, `drawend` event opens the modal; Cancel/Esc/outside-click/starting-a-new-draw all discard the geometry. On Save: POSTs `{geometry, properties: {name: <input>}}` to `/api/features/`, deactivates the draw interaction, adds the new feature to the layer. On error: shows inline Bootstrap alert above the input. Exports `initDraw()`. |
| `frontend/static/js/map-import.js` | File input → `ol/format/GeoJSON` parse → render temporarily on a separate import layer → "Save all to server" batch-POSTs to `/api/features/`. "Export" button serializes the in-memory layer to a FeatureCollection and triggers a download. Exports `initImportExport()`.                                                                                                             |
| `frontend/static/js/map-panel.js`  | Right-side panel: opens on `map:fly-to` event with the feature detail, renders a `properties` key/value table, PATCHes on Enter / cancels on Esc, renders `category` as a dropdown of the cached enum values + "other…" free-text, "Delete feature" button. Exports `initPanel()`.                                                                                                      |
| `frontend/static/js/edit.js`       | Edit page: fetches `/api/features/?page=<n>&ordering=<o>`, renders rows, inline-edit per row (int/float/bool type-preserving editors, str plain text), "×" delete sends PATCH `{"properties": {"<key>": null}}`, "+ add new" inserts a cancellable row, prev/next pagination, sort dropdown. Exports `initEdit()`.                                                                      |

**New test files**

| File                               | Responsibility                                                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `frontend/tests/test_views.py`     | Tests for the 5 view functions: status code, template used, public/auth-required pages.                            |
| `frontend/tests/test_templates.py` | Smoke tests that each template renders the expected structural hooks (`<form>` in login, `id="map"` in map, etc.). |
| `frontend/tests/test_static.py`    | Smoke tests for the static assets served via the staticfiles finder.                                               |

---

## Task 1: Extend `FeatureSerializer.validate_properties` to enforce the `name` invariant

**Files:**

- Modify: `features/serializers.py:58-82`
- Test: `features/tests/test_serializers.py`

- [ ] **Step 1: Read the current serializer to understand shape**

`features/serializers.py` has `FeatureSerializer.validate_properties` at lines 58–82. The new check sits _after_ the existing checks (the `properties` value has already been confirmed to be a dict, and `_audit` stripped).

- [ ] **Step 2: Write the failing test**

Append to `features/tests/test_serializers.py`:

```python
def test_name_must_be_non_empty_string_when_present(make_feature):
    """A non-empty `str` is required when the `name` key is present in `properties`."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"name": "", "color": "#ff0000"},
        },
    )
    assert not serializer.is_valid()
    assert "name" in serializer.errors
```

Plus a positive case to lock the new line in:

```python
def test_name_valid_when_string(make_feature):
    """A non-empty string `name` is accepted."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"name": "Bar", "color": "#ff0000"},
        },
    )
    assert serializer.is_valid(), serializer.errors
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `docker compose exec web pytest features/tests/test_serializers.py -v -k "name"`
Expected: 2 failures, both with `is_valid()` returning `True` (no validation, so the test logic on the "name" key fails) and `serializer.validated_data` containing the empty string.

- [ ] **Step 4: Add the validation rule**

Edit `features/serializers.py`, appending one block at the end of `validate_properties` (before the final `return value`):

```python
        if "name" in value:
            name_value = value["name"]
            if not isinstance(name_value, str) or not name_value:
                raise serializers.ValidationError(
                    {"name": "name must be a non-empty string when present"}
                )

        return value
```

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `docker compose exec web pytest features/tests/test_serializers.py -v`
Expected: all 6 tests pass (4 existing + 2 new).

---

## Task 2: Make Feature API PATCH additive (merge with `null` = delete)

**Files:**

- Modify: `features/views.py:33-77`
- Modify: `features/tests/test_views.py:91-110`

The current `partial_update` replaces `properties` wholesale. The frontend spec §5.2.1 (and §5.2.2, "Interaction with the system-managed `name` property") requires additive PATCH: keys absent from the body are preserved, and `null` deletes a key. This matches RFC 7396 (JSON merge patch).

- [ ] **Step 1: Update the failing test to assert additive behavior**

Edit `features/tests/test_views.py:91-110`. Replace the `test_partial_update` body with:

```python
def test_partial_update_merges_properties(user, make_auth_client):
    """PATCH /api/features/{id}/ merges `properties` with the existing dict (additive)."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Old", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = make_auth_client().patch(
        path=f"/api/features/{feature.pk}/",
        data={"properties": {"name": "New"}},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["properties"]["name"] == "New"
    assert body["properties"]["color"] == "#ff0000"
    assert body["properties"]["category"] == "city"
    feature.refresh_from_db()
    assert feature.properties == {
        "name": "New",
        "color": "#ff0000",
        "category": "city",
    }
```

Add a new test below it for the `null` = delete behavior:

```python
def test_partial_update_null_deletes_key(user, make_auth_client):
    """PATCH with `{key: null}` removes that key from `properties`."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Foo", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = make_auth_client().patch(
        path=f"/api/features/{feature.pk}/",
        data={"properties": {"category": None}},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert "category" not in body["properties"]
    assert body["properties"]["name"] == "Foo"
    assert body["properties"]["color"] == "#ff0000"
    feature.refresh_from_db()
    assert "category" not in feature.properties
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `docker compose exec web pytest features/tests/test_views.py::test_partial_update_merges_properties features/tests/test_views.py::test_partial_update_null_deletes_key -v`
Expected: both fail — the current serializer replaces the dict, so the merged `color`/`category` keys are lost.

- [ ] **Step 3: Implement the additive PATCH**

Edit `features/views.py`. Add a new method on `FeatureViewSet` after `perform_create` (around line 77):

```python
    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Apply a JSON merge patch to `properties`: missing keys are preserved, `null` deletes.

        Per the Frontend spec §5.2.1, PATCH is additive — keys not in the
        body are preserved, and `null` deletes a key. This matches RFC 7396
        (JSON merge patch) and lets the edit page update one property at
        a time without losing the rest. The system-managed `name` key is
        therefore never disturbed by an `+ add new` PATCH that doesn't
        include `name` in its body.
        """
        instance = self.get_object()
        existing_properties = dict(instance.properties or {})
        incoming_properties = request.data.get("properties") or {}
        merged_properties = _merge_properties(
            existing=existing_properties,
            incoming=incoming_properties,
        )
        request_data = dict(request.data)
        request_data["properties"] = merged_properties
        serializer = self.get_serializer(
            instance=instance,
            data=request_data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
```

Add the private helper at the **bottom of the file**, after `categories_view`. Per AGENTS.md, private helpers live below the public functions that call them, not above:

```python
def _merge_properties(
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    """Apply an RFC 7396-style JSON merge patch to `properties`.

    - Keys present in `incoming` overwrite or are added to `existing`.
    - Keys whose incoming value is `None` are removed from the result.
    - Keys absent from `incoming` are preserved unchanged.
    """
    merged: dict[str, object] = dict(existing)
    for key, value in incoming.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value

    return merged
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `docker compose exec web pytest features/tests/test_views.py -v`
Expected: all 8 tests pass (6 existing + 2 new/updated).

---

## Task 3: View functions for the 5 server-rendered pages

**Files:**

- Create: `frontend/views.py`
- Modify: `frontend/urls.py`
- Test: `frontend/tests/test_views.py`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/test_views.py`:

```python
"""Tests for the 5 server-rendered HTML pages (home, map, edit, login, register).

The views themselves are thin — they just `render()` the matching
template. Auth gating for `/map/` and `/edit/` is enforced client-side
in `auth.js` because JWTs live in `localStorage`; the server has no
way to see them.
"""

from __future__ import annotations

import pytest
from django.urls import resolve, reverse

pytestmark = pytest.mark.django_db


def test_home_url_resolves_to_home_view() -> None:
    """GET / is routed to the home view, which renders `home.html`."""
    match = resolve("/")
    assert match.view_name == "frontend:home"


def test_home_renders_home_template(client) -> None:
    """GET / returns 200 and uses `home.html`."""
    response = client.get("/")
    assert response.status_code == 200
    assert "home.html" in [template.name for template in response.templates]


def test_map_url_resolves_to_map_view() -> None:
    """GET /map/ is routed to the map view, which renders `map.html`."""
    match = resolve("/map/")
    assert match.view_name == "frontend:map_page"


def test_map_renders_map_template(client) -> None:
    """GET /map/ returns 200 and uses `map.html`."""
    response = client.get("/map/")
    assert response.status_code == 200
    assert "map.html" in [template.name for template in response.templates]


def test_edit_url_resolves_to_edit_view() -> None:
    """GET /edit/ is routed to the edit view, which renders `edit.html`."""
    match = resolve("/edit/")
    assert match.view_name == "frontend:edit_page"


def test_edit_renders_edit_template(client) -> None:
    """GET /edit/ returns 200 and uses `edit.html`."""
    response = client.get("/edit/")
    assert response.status_code == 200
    assert "edit.html" in [template.name for template in response.templates]


def test_login_url_resolves_to_login_view() -> None:
    """GET /login/ is routed to the login view, which renders `login.html`."""
    match = resolve("/login/")
    assert match.view_name == "frontend:login_page"


def test_login_renders_login_template(client) -> None:
    """GET /login/ returns 200 and uses `login.html`."""
    response = client.get("/login/")
    assert response.status_code == 200
    assert "login.html" in [template.name for template in response.templates]


def test_register_url_resolves_to_register_view() -> None:
    """GET /register/ is routed to the register view, which renders `register.html`."""
    match = resolve("/register/")
    assert match.view_name == "frontend:register_page"


def test_register_renders_register_template(client) -> None:
    """GET /register/ returns 200 and uses `register.html`."""
    response = client.get("/register/")
    assert response.status_code == 200
    assert "register.html" in [template.name for template in response.templates]


def test_root_urlconf_includes_all_frontend_routes() -> None:
    """`reverse()` resolves each frontend route to its path."""
    assert reverse("frontend:home") == "/"
    assert reverse("frontend:map_page") == "/map/"
    assert reverse("frontend:edit_page") == "/edit/"
    assert reverse("frontend:login_page") == "/login/"
    assert reverse("frontend:register_page") == "/register/"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `docker compose exec web pytest frontend/tests/test_views.py -v`
Expected: 11 failures, all `NoReverseMatch` or `TemplateDoesNotExist`.

- [ ] **Step 3: Implement the views**

Create `frontend/views.py`:

```python
"""Server-rendered HTML pages (home, map, edit, login, register).

All five views are thin: they call `render()` with the matching
template and an empty context. Auth gating for `/map/` and `/edit/` is
enforced client-side in `auth.js` because JWTs live in `localStorage`
and the server cannot see them. The login and register templates
post to the auth API via JS, also using `localStorage` to persist the
returned tokens.

Per AGENTS.md, public entry-point functions are listed first and
private helpers follow. There are no private helpers in this module.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.shortcuts import render
from django.views.decorators.http import require_GET

ROOT_TEMPLATE = "home.html"
MAP_TEMPLATE = "map.html"
EDIT_TEMPLATE = "edit.html"
LOGIN_TEMPLATE = "login.html"
REGISTER_TEMPLATE = "register.html"


@require_GET
def home(request: HttpRequest):
    """Render the landing page (`home.html`)."""
    return render(request, template_name=ROOT_TEMPLATE)


@require_GET
def map_page(request: HttpRequest):
    """Render the OpenLayers map page (`map.html`). Auth is enforced client-side."""
    return render(request, template_name=MAP_TEMPLATE)


@require_GET
def edit_page(request: HttpRequest):
    """Render the inline-edit properties table (`edit.html`). Auth is enforced client-side."""
    return render(request, template_name=EDIT_TEMPLATE)


@require_GET
def login_page(request: HttpRequest):
    """Render the login form (`login.html`)."""
    return render(request, template_name=LOGIN_TEMPLATE)


@require_GET
def register_page(request: HttpRequest):
    """Render the registration form (`register.html`)."""
    return render(request, template_name=REGISTER_TEMPLATE)
```

- [ ] **Step 4: Implement the URL routing**

Replace `frontend/urls.py`:

```python
"""Root URLs for the frontend app: the 5 server-rendered HTML pages.

Each path maps to a view function in `frontend.views`. The root URLConf
mounts this module at `""` (no prefix), so the final paths are `/`,
`/map/`, `/edit/`, `/login/`, and `/register/`. Auth gating for
`/map/` and `/edit/` is enforced client-side; see `frontend/views.py`.
"""

from __future__ import annotations

from django.urls import path

from frontend import views

app_name = "frontend"

urlpatterns = [
    path(route="", view=views.home, name="home"),
    path(route="map/", view=views.map_page, name="map_page"),
    path(route="edit/", view=views.edit_page, name="edit_page"),
    path(route="login/", view=views.login_page, name="login_page"),
    path(route="register/", view=views.register_page, name="register_page"),
]
```

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `docker compose exec web pytest frontend/tests/test_views.py -v`
Expected: 11 passes. (Template tests for `TemplateDoesNotExist` will fail because the templates don't exist yet — that's expected and is fixed in Tasks 4–6.)

- [ ] **Step 6: Skip the template tests until the templates exist**

Temporarily mark template-rendering tests as expected-to-fail. Use `pytest.mark.xfail(raises=TemplateDoesNotExist)` on the 5 `*_renders_*_template` tests, or simply exclude them with `-k "not renders"` for now. Cleanest: keep them as plain tests, run only the URL-resolution ones in this task:

Run: `docker compose exec web pytest frontend/tests/test_views.py -v -k "url_resolves or reverse"`
Expected: 6 passes. Template tests will pass in Tasks 4–6 once the templates exist.

---

## Task 4: `base.html` shared layout

**Files:**

- Create: `frontend/templates/base.html`
- Test: `frontend/tests/test_templates.py`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/test_templates.py`:

```python
"""Smoke tests for the 5 server-rendered templates.

These tests fetch each page and assert the template renders the
expected structural hooks (`<form>` in login, `id="map"` in map, etc.)
so a typo in the template surfaces as a 200-with-missing-element
failure rather than a silent regression.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_home_template_renders_two_buttons(client) -> None:
    """`home.html` shows two buttons linking to `/map/` and `/edit/`."""
    body = client.get("/").content.decode()
    assert 'href="/map/"' in body
    assert 'href="/edit/"' in body


def test_login_template_renders_form_and_csrf(client) -> None:
    """`login.html` has a `<form>`, an email input, a password input, and `{% csrf_token %}`."""
    body = client.get("/login/").content.decode()
    assert "<form" in body
    assert 'name="email"' in body
    assert 'name="password"' in body
    assert "csrfmiddlewaretoken" in body


def test_register_template_renders_form_with_confirm(client) -> None:
    """`register.html` has a `<form>`, email, password, password_confirm, and CSRF."""
    body = client.get("/register/").content.decode()
    assert "<form" in body
    assert 'name="email"' in body
    assert 'name="password"' in body
    assert 'name="password_confirm"' in body
    assert "csrfmiddlewaretoken" in body


def test_map_template_has_map_div_and_panel_and_modal(client) -> None:
    """`map.html` ships the `#map` div, the `#panel` aside, and the `#draw-name-modal` modal."""
    body = client.get("/map/").content.decode()
    assert 'id="map"' in body
    assert 'id="panel"' in body
    assert 'id="draw-name-modal"' in body


def test_edit_template_has_table_and_sort_and_pagination(client) -> None:
    """`edit.html` ships `#features-table`, `#sort-order`, and `#pagination`."""
    body = client.get("/edit/").content.decode()
    assert 'id="features-table"' in body
    assert 'id="sort-order"' in body
    assert 'id="pagination"' in body


def test_base_template_loads_bootstrap_and_openlayers_from_cdn(client) -> None:
    """`base.html` references Bootstrap 5 and OpenLayers via the jsdelivr CDN."""
    body = client.get("/").content.decode()
    assert "cdn.jsdelivr.net" in body
    assert "bootstrap" in body.lower()
    assert "ol/" in body or "openlayers" in body.lower()


def test_base_template_includes_search_bar_on_map_and_edit(client) -> None:
    """The top-nav search input renders on `/map/` and `/edit/` (home and login are excluded)."""
    for path in ("/map/", "/edit/"):
        body = client.get(path).content.decode()
        assert 'id="search-input"' in body, f"search input missing on {path}"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `docker compose exec web pytest frontend/tests/test_templates.py -v`
Expected: 7 failures, all `TemplateDoesNotExist`.

- [ ] **Step 3: Create `base.html`**

Create `frontend/templates/base.html`:

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{% block title %}GeoJSON{% endblock %}</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" />
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@10.3.1/ol.css" />
        <link rel="stylesheet" href="{% static 'css/site.css' %}" />
        {% block extra_head %}{% endblock %}
    </head>
    <body>
        <nav class="navbar navbar-expand bg-light border-bottom px-3" id="top-nav">
            <a class="navbar-brand fw-bold" href="/">GeoJSON</a>
            <ul class="navbar-nav me-auto">
                <li class="nav-item"><a class="nav-link" href="/map/" id="nav-map">Map</a></li>
                <li class="nav-item"><a class="nav-link" href="/edit/" id="nav-edit">Edit Properties</a></li>
            </ul>
            <div class="position-relative me-3" id="search-container">
                <input
                    type="search"
                    class="form-control form-control-sm"
                    id="search-input"
                    placeholder="Search by name..."
                    autocomplete="off"
                />
                <ul class="list-group position-absolute w-100 search-dropdown d-none" id="search-dropdown"></ul>
            </div>
            <div id="user-menu" class="d-flex align-items-center gap-2">
                <span id="user-email" class="text-muted small"></span>
                <a class="btn btn-sm btn-outline-secondary d-none" id="login-link" href="/login/">Login</a>
                <a class="btn btn-sm btn-outline-secondary d-none" id="register-link" href="/register/">Register</a>
                <button class="btn btn-sm btn-outline-secondary d-none" id="logout-button" type="button">Logout</button>
            </div>
        </nav>
        <main class="container-fluid p-0">{% block content %}{% endblock %}</main>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script type="module" src="{% static 'js/api.js' %}"></script>
        <script type="module" src="{% static 'js/auth.js' %}"></script>
        {% block extra_scripts %}{% endblock %}
    </body>
</html>
```

- [ ] **Step 4: Run the tests to confirm partial pass**

Run: `docker compose exec web pytest frontend/tests/test_templates.py::test_base_template_loads_bootstrap_and_openlayers_from_cdn frontend/tests/test_templates.py::test_base_template_includes_search_bar_on_map_and_edit -v`
Expected: 2 passes (the `test_base_template_*` tests pass once `base.html` exists and is extended by the children). The other 5 tests still fail because `home.html`, `login.html`, `register.html`, `map.html`, `edit.html` don't exist yet — those land in Tasks 5–6.

---

## Task 5: `home.html`, `login.html`, `register.html`

**Files:**

- Create: `frontend/templates/home.html`
- Create: `frontend/templates/login.html`
- Create: `frontend/templates/register.html`

- [ ] **Step 1: Create `home.html`**

Create `frontend/templates/home.html`:

```html
{% extends "base.html" %} {% block title %}GeoJSON — Home{% endblock %} {% block content %}
<div class="container py-5 text-center" id="home-hero">
    <h1 class="mb-4" id="home-heading">GeoJSON</h1>
    <p class="lead mb-5" id="home-subheading">Browse, edit, and draw features on a map.</p>
    <div class="d-flex justify-content-center gap-3">
        <a class="btn btn-primary btn-lg" href="/map/" id="home-map-button">View Map</a>
        <a class="btn btn-outline-primary btn-lg" href="/edit/" id="home-edit-button">Edit Properties</a>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Create `login.html`**

Create `frontend/templates/login.html`:

```html
{% extends "base.html" %} {% block title %}Login{% endblock %} {% block content %}
<div class="container py-5" style="max-width: 420px;">
    <h1 class="mb-4">Login</h1>
    <div id="login-alert" class="alert alert-danger d-none" role="alert"></div>
    <form id="login-form" novalidate>
        {% csrf_token %}
        <div class="mb-3">
            <label for="login-email" class="form-label">Email</label>
            <input type="email" class="form-control" id="login-email" name="email" required />
        </div>
        <div class="mb-3">
            <label for="login-password" class="form-label">Password</label>
            <input type="password" class="form-control" id="login-password" name="password" required />
        </div>
        <button type="submit" class="btn btn-primary w-100" id="login-submit">Login</button>
    </form>
    <p class="mt-3 text-center text-muted small">No account? <a href="/register/">Register</a></p>
</div>
{% endblock %} {% block extra_scripts %}
<script type="module">
    import { auth } from "{% static 'js/auth.js' %}";
    const form = document.getElementById("login-form");
    const alert_box = document.getElementById("login-alert");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        alert_box.classList.add("d-none");
        const email = form.elements.namedItem("email").value;
        const password = form.elements.namedItem("password").value;
        try {
            await auth.login(email, password);
            window.location.href = "/map/";
        } catch (error) {
            alert_box.textContent = error.message || "Login failed.";
            alert_box.classList.remove("d-none");
        }
    });
</script>
{% endblock %}
```

- [ ] **Step 3: Create `register.html`**

Create `frontend/templates/register.html`:

```html
{% extends "base.html" %} {% block title %}Register{% endblock %} {% block content %}
<div class="container py-5" style="max-width: 420px;">
    <h1 class="mb-4">Register</h1>
    <div id="register-alert" class="alert alert-danger d-none" role="alert"></div>
    <form id="register-form" novalidate>
        {% csrf_token %}
        <div class="mb-3">
            <label for="register-email" class="form-label">Email</label>
            <input type="email" class="form-control" id="register-email" name="email" required />
        </div>
        <div class="mb-3">
            <label for="register-password" class="form-label">Password</label>
            <input type="password" class="form-control" id="register-password" name="password" minlength="8" required />
        </div>
        <div class="mb-3">
            <label for="register-password-confirm" class="form-label">Confirm password</label>
            <input
                type="password"
                class="form-control"
                id="register-password-confirm"
                name="password_confirm"
                minlength="8"
                required
            />
        </div>
        <button type="submit" class="btn btn-primary w-100" id="register-submit">Create account</button>
    </form>
    <p class="mt-3 text-center text-muted small">Already have an account? <a href="/login/">Login</a></p>
</div>
{% endblock %} {% block extra_scripts %}
<script type="module">
    import { auth } from "{% static 'js/auth.js' %}";
    const form = document.getElementById("register-form");
    const alert_box = document.getElementById("register-alert");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        alert_box.classList.add("d-none");
        const email = form.elements.namedItem("email").value;
        const password = form.elements.namedItem("password").value;
        const password_confirm = form.elements.namedItem("password_confirm").value;
        if (password !== password_confirm) {
            alert_box.textContent = "Passwords do not match.";
            alert_box.classList.remove("d-none");
            return;
        }
        try {
            await auth.register(email, password);
            await auth.login(email, password);
            window.location.href = "/map/";
        } catch (error) {
            alert_box.textContent = error.message || "Registration failed.";
            alert_box.classList.remove("d-none");
        }
    });
</script>
{% endblock %}
```

- [ ] **Step 4: Run the home / login / register tests**

Run: `docker compose exec web pytest frontend/tests/test_templates.py::test_home_template_renders_two_buttons frontend/tests/test_templates.py::test_login_template_renders_form_and_csrf frontend/tests/test_templates.py::test_register_template_renders_form_with_confirm -v`
Expected: 3 passes.

---

## Task 6: `site.css` skeleton

**Files:**

- Create: `frontend/static/css/site.css`
- Test: `frontend/tests/test_static.py`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/test_static.py`:

```python
"""Smoke tests for the static assets served by the frontend app.

These tests fetch each static file via the staticfiles finder and
assert the expected content. They are not behavioral tests — the JS
modules are not executed here. Biome (run by pre-commit) catches
syntax errors. Behavioral coverage of the JS modules is out of scope
for the v1 frontend spec.
"""

from __future__ import annotations

from django.contrib.staticfiles import finders
from django.test import Client


def _read_static(relative_path: str) -> str:
    """Return the contents of a static file as a string."""
    absolute_path = finders.find(relative_path)
    assert absolute_path is not None, f"static file not found: {relative_path}"
    with open(path=absolute_path, encoding="utf-8") as file_handle:
        return file_handle.read()


def test_site_css_declares_search_dropdown_class() -> None:
    """`site.css` defines `.search-dropdown` with `max-height: 360px; overflow-y: auto`."""
    body = _read_static("css/site.css")
    assert ".search-dropdown" in body
    assert "max-height" in body
    assert "360px" in body
    assert "overflow-y" in body
    assert "auto" in body


def test_site_css_declares_panel_slide_in() -> None:
    """`site.css` defines a slide-in animation for the right-side panel."""
    body = _read_static("css/site.css")
    assert "#panel" in body
    assert "transform" in body or "translate" in body


def test_api_js_exports_named_api() -> None:
    """`api.js` exports a named `api` object as its single export."""
    body = _read_static("js/api.js")
    assert "export" in body
    assert "api" in body


def test_auth_js_exports_named_auth() -> None:
    """`auth.js` exports a named `auth` object as its single export."""
    body = _read_static("js/auth.js")
    assert "export" in body
    assert "auth" in body
    assert "login" in body
    assert "logout" in body


def test_search_js_exports_init_search() -> None:
    """`search.js` exports an `initSearch` initializer."""
    body = _read_static("js/search.js")
    assert "export" in body
    assert "initSearch" in body


def test_map_js_exports_init_map() -> None:
    """`map.js` exports an `initMap` initializer."""
    body = _read_static("js/map.js")
    assert "export" in body
    assert "initMap" in body


def test_map_draw_js_exports_init_draw() -> None:
    """`map-draw.js` exports an `initDraw` initializer."""
    body = _read_static("js/map-draw.js")
    assert "export" in body
    assert "initDraw" in body


def test_map_import_js_exports_init_import_export() -> None:
    """`map-import.js` exports an `initImportExport` initializer."""
    body = _read_static("js/map-import.js")
    assert "export" in body
    assert "initImportExport" in body


def test_map_panel_js_exports_init_panel() -> None:
    """`map-panel.js` exports an `initPanel` initializer."""
    body = _read_static("js/map-panel.js")
    assert "export" in body
    assert "initPanel" in body


def test_edit_js_exports_init_edit() -> None:
    """`edit.js` exports an `initEdit` initializer."""
    body = _read_static("js/edit.js")
    assert "export" in body
    assert "initEdit" in body


def test_static_files_served_in_dev() -> None:
    """The dev `Client` returns 200 for `site.css` via the staticfiles URL."""
    response = Client().get("/static/css/site.css")
    assert response.status_code == 200
```

- [ ] **Step 2: Run the static test to confirm `site.css` content fails**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_site_css_declares_search_dropdown_class frontend/tests/test_static.py::test_site_css_declares_panel_slide_in -v`
Expected: 2 failures, both with "static file not found" or content not containing the expected selector.

- [ ] **Step 3: Create `site.css`**

Create `frontend/static/css/site.css`:

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

#panel {
    position: fixed;
    top: 56px;
    right: 0;
    width: 360px;
    max-width: 100vw;
    height: calc(100vh - 56px);
    background: #fff;
    border-left: 1px solid #dee2e6;
    box-shadow: -2px 0 4px rgba(0, 0, 0, 0.05);
    transform: translateX(100%);
    transition: transform 200ms ease-out;
    overflow-y: auto;
    z-index: 1040;
}

#panel.open {
    transform: translateX(0);
}

#panel .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    border-bottom: 1px solid #dee2e6;
}

#panel .panel-body {
    padding: 1rem;
}

.search-result-row {
    cursor: pointer;
}

.swatch {
    display: inline-block;
    width: 0.9em;
    height: 0.9em;
    border: 1px solid #6c757d;
    vertical-align: middle;
    margin-right: 0.25rem;
}
```

- [ ] **Step 4: Run the static test to confirm `site.css` passes**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_site_css_declares_search_dropdown_class frontend/tests/test_static.py::test_site_css_declares_panel_slide_in frontend/tests/test_static.py::test_static_files_served_in_dev -v`
Expected: 3 passes.

---

## Task 7: `api.js` (shared fetch wrapper with token refresh)

**Files:**

- Create: `frontend/static/js/api.js`

`api.js` is the single point of contact with the backend. Every other module imports it. The refresh-on-401 logic lives here so the other modules never see 401s.

- [ ] **Step 1: Create `api.js`**

Create `frontend/static/js/api.js`:

```javascript
const ACCESS_KEY = "access";
const REFRESH_KEY = "refresh";

const REFRESH_URL = "/api/auth/refresh/";
const ME_URL = "/api/auth/me/";

function readToken(key) {
    return localStorage.getItem(key);
}

function writeTokens(access, refresh) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken() {
    const refresh = readToken(REFRESH_KEY);
    if (!refresh) {
        clearTokens();
        return null;
    }
    const response = await fetch(REFRESH_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
    });
    if (!response.ok) {
        clearTokens();
        return null;
    }
    const body = await response.json();
    writeTokens(body.access, body.refresh);
    return body.access;
}

async function request(path, options = {}, { retried = false } = {}) {
    const headers = new Headers(options.headers || {});
    const access = readToken(ACCESS_KEY);
    if (access) headers.set("Authorization", `Bearer ${access}`);
    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }
    const response = await fetch(path, { ...options, headers });
    if (response.status !== 401 || retried) {
        return response;
    }
    const newAccess = await refreshAccessToken();
    if (!newAccess) {
        return response;
    }
    const retryHeaders = new Headers(headers);
    retryHeaders.set("Authorization", `Bearer ${newAccess}`);
    return request(path, { ...options, headers: retryHeaders }, { retried: true });
}

async function getJson(path) {
    const response = await request(path, { method: "GET" });
    if (!response.ok) {
        throw new Error(`GET ${path} failed: ${response.status}`);
    }
    return response.json();
}

async function sendJson(path, method, body) {
    const response = await request(path, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
        let detail = `${method} ${path} failed: ${response.status}`;
        try {
            const errorBody = await response.json();
            detail = JSON.stringify(errorBody);
        } catch (parseError) {
            // ignore: response had no JSON body
        }
        throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response.json();
}

export const api = {
    get: (path) => getJson(path),
    post: (path, body) => sendJson(path, "POST", body),
    patch: (path, body) => sendJson(path, "PATCH", body),
    put: (path, body) => sendJson(path, "PUT", body),
    delete: (path) => sendJson(path, "DELETE"),
    me: () => getJson(ME_URL),
    hasAccessToken: () => Boolean(readToken(ACCESS_KEY)),
    clearTokens,
};
```

- [ ] **Step 2: Run the static test for `api.js`**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_api_js_exports_named_api -v`
Expected: 1 pass.

---

## Task 8: `auth.js` (token storage, login, logout)

**Files:**

- Create: `frontend/static/js/auth.js`

`auth.js` is loaded on every page (it's in `base.html`). It exposes `auth` for `login.html` / `register.html` to import. It also reads the current user's email on page load via `api.me()` and updates the top-nav user menu (`#user-email`, `#login-link`, `#register-link`, `#logout-button`).

- [ ] **Step 1: Create `auth.js`**

Create `frontend/static/js/auth.js`:

```javascript
import { api } from "./api.js";

const LOGIN_URL = "/api/auth/login/";
const REGISTER_URL = "/api/auth/register/";

function setUserEmail(email) {
    const target = document.getElementById("user-email");
    const loginLink = document.getElementById("login-link");
    const registerLink = document.getElementById("register-link");
    const logoutButton = document.getElementById("logout-button");
    if (!target) return;
    if (email) {
        target.textContent = email;
        loginLink?.classList.add("d-none");
        registerLink?.classList.add("d-none");
        logoutButton?.classList.remove("d-none");
    } else {
        target.textContent = "";
        loginLink?.classList.remove("d-none");
        registerLink?.classList.remove("d-none");
        logoutButton?.classList.add("d-none");
    }
}

async function refreshUserMenu() {
    if (!api.hasAccessToken()) {
        setUserEmail(null);
        return;
    }
    try {
        const me = await api.me();
        setUserEmail(me.email);
    } catch (error) {
        setUserEmail(null);
    }
}

async function login(email, password) {
    const response = await fetch(LOGIN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
        throw new Error("Invalid email or password.");
    }
    const body = await response.json();
    api.clearTokens();
    localStorage.setItem("access", body.access);
    localStorage.setItem("refresh", body.refresh);
    await refreshUserMenu();
}

async function register(email, password) {
    const response = await fetch(REGISTER_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, password_confirm: password }),
    });
    if (!response.ok) {
        let detail = "Registration failed.";
        try {
            const errorBody = await response.json();
            if (errorBody.password_confirm) {
                detail = "Passwords do not match.";
            } else if (errorBody.password) {
                detail = "Password validation failed.";
            } else if (errorBody.email) {
                detail = "Email is already registered.";
            }
        } catch (parseError) {
            // ignore: response had no JSON body
        }
        throw new Error(detail);
    }
}

function logout() {
    api.clearTokens();
    setUserEmail(null);
    window.location.href = "/";
}

function requireAuth(redirectPath = "/map/") {
    if (!api.hasAccessToken()) {
        window.location.href = "/login/";
        return false;
    }
    return true;
}

document.getElementById("logout-button")?.addEventListener("click", logout);
refreshUserMenu();

export const auth = { login, register, logout, requireAuth, refreshUserMenu };
```

- [ ] **Step 2: Run the static test for `auth.js`**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_auth_js_exports_named_auth -v`
Expected: 1 pass.

---

## Task 9: `search.js` (top-nav search dropdown)

**Files:**

- Create: `frontend/static/js/search.js`

`search.js` is loaded on every page (it's in `base.html` after `api.js` / `auth.js`). It only activates the input + dropdown on `/map/` and `/edit/` (the spec says the top nav is "visible on `/map/` and `/edit/`"). It debounces 250ms, GETs `/api/features/?search=<q>&page=1`, renders every result as a row, and on click dispatches a `map:fly-to` event that `map.js` (when present) handles.

- [ ] **Step 1: Create `search.js`**

Create `frontend/static/js/search.js`:

```javascript
import { api } from "./api.js";

const DEBOUNCE_MS = 250;
const LIST_URL = "/api/features/";
const CATEGORIES_URL = "/api/categories/";

let categories = [];
let debounce_handle = null;
let active_index = -1;

function loadCategories() {
    api.get(CATEGORIES_URL)
        .then((values) => {
            categories = values;
        })
        .catch(() => {
            categories = [];
        });
}

function isVisible() {
    const input = document.getElementById("search-input");
    return Boolean(input);
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

function getCategoryLabel(properties) {
    const category = properties?.category;
    if (typeof category !== "string" || !category) return null;
    return category;
}

function closeDropdown() {
    const dropdown = document.getElementById("search-dropdown");
    if (!dropdown) return;
    dropdown.classList.add("d-none");
    dropdown.innerHTML = "";
    active_index = -1;
}

function renderRows(features) {
    const dropdown = document.getElementById("search-dropdown");
    if (!dropdown) return;
    dropdown.innerHTML = "";
    for (const feature of features) {
        const properties = feature.properties || {};
        const name = getName(properties);
        const color = getColor(properties);
        const category_label = getCategoryLabel(properties);
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

        row.addEventListener("click", () => {
            window.dispatchEvent(new CustomEvent("map:fly-to", { detail: { feature } }));
            closeDropdown();
        });
        dropdown.appendChild(row);
    }
    dropdown.classList.remove("d-none");
}

async function performSearch(query) {
    if (!query) {
        closeDropdown();
        return;
    }
    try {
        const body = await api.get(`${LIST_URL}?search=${encodeURIComponent(query)}&page=1`);
        renderRows(body.results || []);
    } catch (error) {
        closeDropdown();
    }
}

function onInput(event) {
    if (debounce_handle) clearTimeout(debounce_handle);
    const query = event.target.value.trim();
    debounce_handle = setTimeout(() => performSearch(query), DEBOUNCE_MS);
}

function onKeyDown(event) {
    if (event.key === "Escape") {
        closeDropdown();
    }
}

function onDocumentClick(event) {
    const container = document.getElementById("search-container");
    if (container && !container.contains(event.target)) {
        closeDropdown();
    }
}

function initSearch() {
    if (!isVisible()) return;
    loadCategories();
    const input = document.getElementById("search-input");
    input.addEventListener("input", onInput);
    input.addEventListener("keydown", onKeyDown);
    document.addEventListener("click", onDocumentClick);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeDropdown();
    });
}

initSearch();

export { initSearch, categories };
```

- [ ] **Step 2: Run the static test for `search.js`**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_search_js_exports_init_search -v`
Expected: 1 pass.

---

## Task 10: `map.html` + `map.js` (OpenLayers map core)

**Files:**

- Create: `frontend/templates/map.html`
- Create: `frontend/static/js/map.js`

`map.html` extends `base.html` and provides the map div, the tool buttons, the slide-in panel aside, and the draw-name modal. It loads `map.js` as a module — `map.js` then `import`s the other map modules and wires them up.

- [ ] **Step 1: Create `map.html`**

Create `frontend/templates/map.html`:

```html
{% extends "base.html" %} {% load static %} {% block title %}Map{% endblock %} {% block content %}
<div class="position-relative">
    <div id="map"></div>
    <div class="position-absolute top-0 end-0 m-3 d-flex flex-column gap-2" id="map-toolbar" style="z-index: 1030;">
        <div class="btn-group-vertical" role="group" aria-label="Draw tools">
            <button type="button" class="btn btn-light" id="draw-point-button" title="Draw point">Point</button>
            <button type="button" class="btn btn-light" id="draw-line-button" title="Draw line">Line</button>
            <button type="button" class="btn btn-light" id="draw-polygon-button" title="Draw polygon">Polygon</button>
        </div>
        <button type="button" class="btn btn-light" id="import-button" title="Import .geojson">Import</button>
        <input type="file" accept=".geojson,.json" id="import-file-input" class="d-none" />
        <button type="button" class="btn btn-light" id="export-button" title="Export .geojson">Export</button>
        <button type="button" class="btn btn-light d-none" id="load-more-button">Load more</button>
    </div>
    <aside id="panel" aria-hidden="true">
        <div class="panel-header">
            <h5 class="m-0">Feature</h5>
            <button type="button" class="btn-close" id="panel-close" aria-label="Close"></button>
        </div>
        <div class="panel-body" id="panel-body">
            <div id="panel-alert" class="alert alert-danger d-none" role="alert"></div>
            <table class="table table-sm" id="panel-properties-table">
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody id="panel-properties-tbody"></tbody>
            </table>
            <div class="d-flex justify-content-between mt-3">
                <button type="button" class="btn btn-outline-danger btn-sm" id="panel-delete">Delete feature</button>
            </div>
        </div>
    </aside>
    <div class="modal fade" id="draw-name-modal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Name the new feature</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="draw-name-alert" class="alert alert-danger d-none" role="alert"></div>
                    <label for="draw-name-input" class="form-label">Name</label>
                    <input
                        type="text"
                        class="form-control"
                        id="draw-name-input"
                        placeholder="My new feature"
                        maxlength="200"
                    />
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" id="draw-name-cancel">
                        Cancel
                    </button>
                    <button type="button" class="btn btn-primary" id="draw-name-save" disabled>Save</button>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %} {% block extra_scripts %}
<script type="module" src="{% static 'js/map.js' %}"></script>
{% endblock %}
```

- [ ] **Step 2: Create `map.js`**

Create `frontend/static/js/map.js`:

```javascript
import "https://cdn.jsdelivr.net/npm/ol@10.3.1/dist/ol.js";
import { api } from "./api.js";
import { auth } from "./auth.js";
import { initDraw } from "./map-draw.js";
import { initImportExport } from "./map-import.js";
import { initPanel } from "./map-panel.js";

const LIST_URL = "/api/features/";
const DEBOUNCE_MS = 250;
const PAGE_SIZE = 100;

const map_state = {
    map: null,
    source: null,
    in_flight_bbox: null,
    current_page: 1,
    has_next: false,
};

let moveend_handle = null;

function build_ol_map() {
    const ol = window.ol;
    const map_element = document.getElementById("map");
    if (!map_element || !ol) return null;
    map_state.source = new ol.source.Vector();
    const layer = new ol.layer.Vector({ source: map_state.source });
    const view = new ol.View({
        center: ol.proj.fromLonLat([5.2913, 52.1326]),
        zoom: 7,
    });
    return new ol.Map({
        target: map_element,
        layers: [new ol.layer.Tile({ source: new ol.source.OSM() }), layer],
        view,
    });
}

function get_view_bbox() {
    const ol = window.ol;
    const view = map_state.map.getView();
    const extent = view.calculateExtent(map_state.map.getSize());
    const top_left = ol.proj.toLonLat(ol.extent.getTopLeft(extent));
    const bottom_right = ol.proj.toLonLat(ol.extent.getBottomRight(extent));
    return [
        Math.min(top_left[0], bottom_right[0]),
        Math.min(top_left[1], bottom_right[1]),
        Math.max(top_left[0], bottom_right[0]),
        Math.max(top_left[1], bottom_right[1]),
    ].join(",");
}

function render_features(features) {
    const ol = window.ol;
    map_state.source.clear();
    const format = new ol.format.GeoJSON();
    for (const feature of features) {
        const ol_feature = format.readFeature(feature);
        ol_feature.set("feature_id", feature.id);
        ol_feature.set("properties", feature.properties);
        map_state.source.addFeature(ol_feature);
    }
}

async function load_page(bbox, page) {
    const url = `${LIST_URL}?bbox=${encodeURIComponent(bbox)}&page=${page}`;
    const body = await api.get(url);
    return body;
}

async function reload() {
    const bbox = get_view_bbox();
    map_state.in_flight_bbox = bbox;
    const body = await load_page(bbox, 1);
    if (map_state.in_flight_bbox !== bbox) return;
    map_state.current_page = 1;
    map_state.has_next = Boolean(body.next);
    render_features(body.results || []);
    document.getElementById("load-more-button")?.classList.toggle("d-none", !map_state.has_next);
}

async function load_more() {
    if (!map_state.has_next) return;
    const bbox = get_view_bbox();
    const next_page = map_state.current_page + 1;
    const body = await load_page(bbox, next_page);
    if (map_state.in_flight_bbox !== bbox) return;
    map_state.current_page = next_page;
    map_state.has_next = Boolean(body.next);
    const ol = window.ol;
    const format = new ol.format.GeoJSON();
    for (const feature of body.results || []) {
        const ol_feature = format.readFeature(feature);
        ol_feature.set("feature_id", feature.id);
        ol_feature.set("properties", feature.properties);
        map_state.source.addFeature(ol_feature);
    }
    document.getElementById("load-more-button")?.classList.toggle("d-none", !map_state.has_next);
}

function on_moveend() {
    if (moveend_handle) clearTimeout(moveend_handle);
    moveend_handle = setTimeout(() => {
        reload().catch(() => {
            // swallow: next moveend retries
        });
    }, DEBOUNCE_MS);
}

function fly_to_feature(feature) {
    const ol = window.ol;
    const view = map_state.map.getView();
    const format = new ol.format.GeoJSON();
    const ol_feature = format.readFeature(feature);
    const extent = ol_feature.getGeometry()?.getExtent();
    if (extent) {
        view.fit(extent, { duration: 500, maxZoom: 16, padding: [50, 50, 50, 50] });
    }
    window.dispatchEvent(new CustomEvent("map:open-panel", { detail: { feature } }));
}

function initMap() {
    if (!auth.requireAuth()) return;
    map_state.map = build_ol_map();
    if (!map_state.map) return;
    map_state.map.on("moveend", on_moveend);
    map_state.map.on("click", (event) => {
        const hit = map_state.map.forEachFeatureAtPixel(event.pixel, (candidate) => candidate);
        if (hit) {
            const feature = {
                id: hit.get("feature_id"),
                geometry: window.ol.format.GeoJSON.writeGeometryObject(hit.getGeometry(), {
                    featureProjection: "EPSG:3857",
                    dataProjection: "EPSG:4326",
                }),
                properties: hit.get("properties") || {},
                type: "Feature",
            };
            window.dispatchEvent(new CustomEvent("map:open-panel", { detail: { feature } }));
        }
    });
    window.addEventListener("map:fly-to", (event) => {
        fly_to_feature(event.detail.feature);
    });
    document.getElementById("load-more-button")?.addEventListener("click", () => {
        load_more().catch(() => {
            // swallow: button stays clickable
        });
    });
    initDraw(map_state);
    initImportExport(map_state);
    initPanel(map_state);
    reload().catch(() => {
        // swallow: a follow-up moveend retries
    });
}

initMap();

export { initMap, map_state };
```

- [ ] **Step 3: Run the static tests for `map.js` and the `map.html` test**

Run: `docker compose exec web pytest frontend/tests/test_templates.py::test_map_template_has_map_div_and_panel_and_modal frontend/tests/test_static.py::test_map_js_exports_init_map -v`
Expected: 2 passes.

---

## Task 11: `map-draw.js` (draw interaction with name modal)

**Files:**

- Create: `frontend/static/js/map-draw.js`

`map-draw.js` is imported by `map.js` and is initialized via `initDraw(map_state)`. It wires the three Draw buttons (Point/Line/Polygon) to a single `ol/interaction/Draw`. On `drawend`, it opens the Bootstrap modal asking for a name. Save POSTs the new feature and adds it to the map source; cancel / Esc / outside-click / starting-a-new-draw all discard the geometry and exit draw mode.

- [ ] **Step 1: Create `map-draw.js`**

Create `frontend/static/js/map-draw.js`:

```javascript
import { api } from "./api.js";

const FEATURES_URL = "/api/features/";

let draw_interaction = null;
let pending_geometry = null;
let pending_type = "Point";

function deactivate_draw(state) {
    if (draw_interaction) {
        state.map.removeInteraction(draw_interaction);
        draw_interaction = null;
    }
}

function activate_draw(state, type) {
    const ol = window.ol;
    deactivate_draw(state);
    pending_type = type;
    draw_interaction = new ol.interaction.Draw({
        source: state.source,
        type,
    });
    draw_interaction.on("drawend", (event) => {
        pending_geometry = event.feature.getGeometry();
        const modal = window.bootstrap?.Modal.getOrCreateInstance(document.getElementById("draw-name-modal"));
        const input = document.getElementById("draw-name-input");
        const save_button = document.getElementById("draw-name-save");
        input.value = "";
        save_button.disabled = true;
        document.getElementById("draw-name-alert")?.classList.add("d-none");
        modal?.show();
        setTimeout(() => input.focus(), 100);
    });
    state.map.addInteraction(draw_interaction);
}

async function save_new_feature(state) {
    const ol = window.ol;
    const input = document.getElementById("draw-name-input");
    const alert_box = document.getElementById("draw-name-alert");
    const save_button = document.getElementById("draw-name-save");
    const cancel_button = document.getElementById("draw-name-cancel");
    const name = input.value.trim();
    if (!name) return;
    save_button.disabled = true;
    cancel_button.disabled = true;
    alert_box?.classList.add("d-none");

    const geometry_geojson = ol.format.GeoJSON.writeGeometryObject(pending_geometry, {
        featureProjection: "EPSG:3857",
        dataProjection: "EPSG:4326",
    });
    try {
        const feature = await api.post(FEATURES_URL, {
            type: "Feature",
            geometry: geometry_geojson,
            properties: { name },
        });
        const ol_feature = new ol.format.GeoJSON().readFeature(feature);
        ol_feature.set("feature_id", feature.id);
        ol_feature.set("properties", feature.properties);
        state.source.addFeature(ol_feature);
        window.bootstrap?.Modal.getInstance(document.getElementById("draw-name-modal"))?.hide();
        pending_geometry = null;
        deactivate_draw(state);
    } catch (error) {
        alert_box.textContent = (error && error.message) || "Save failed.";
        alert_box?.classList.remove("d-none");
    } finally {
        save_button.disabled = false;
        cancel_button.disabled = false;
    }
}

function discard_pending() {
    pending_geometry = null;
    document.getElementById("draw-name-input").value = "";
    document.getElementById("draw-name-alert")?.classList.add("d-none");
}

function initDraw(state) {
    const ol = window.ol;
    document.getElementById("draw-point-button")?.addEventListener("click", () => activate_draw(state, "Point"));
    document.getElementById("draw-line-button")?.addEventListener("click", () => activate_draw(state, "LineString"));
    document.getElementById("draw-polygon-button")?.addEventListener("click", () => activate_draw(state, "Polygon"));

    const input = document.getElementById("draw-name-input");
    const save_button = document.getElementById("draw-name-save");
    input?.addEventListener("input", () => {
        save_button.disabled = !input.value.trim();
    });
    input?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && input.value.trim()) {
            event.preventDefault();
            save_new_feature(state);
        } else if (event.key === "Escape") {
            event.preventDefault();
            discard_pending();
            window.bootstrap?.Modal.getInstance(document.getElementById("draw-name-modal"))?.hide();
            deactivate_draw(state);
        }
    });
    document.getElementById("draw-name-save")?.addEventListener("click", () => save_new_feature(state));
    document.getElementById("draw-name-modal")?.addEventListener("hidden.bs.modal", () => {
        if (pending_geometry) {
            discard_pending();
            deactivate_draw(state);
        }
    });
}

export { initDraw, activate_draw, deactivate_draw };
```

- [ ] **Step 2: Run the static test for `map-draw.js`**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_map_draw_js_exports_init_draw -v`
Expected: 1 pass.

---

## Task 12: `map-import.js` (import + export)

**Files:**

- Create: `frontend/static/js/map-import.js`

- [ ] **Step 1: Create `map-import.js`**

Create `frontend/static/js/map-import.js`:

```javascript
import { api } from "./api.js";

const FEATURES_URL = "/api/features/";

let import_layer = null;

function read_file(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsText(file);
    });
}

async function import_file(state) {
    const ol = window.ol;
    const file_input = document.getElementById("import-file-input");
    if (!file_input.files || !file_input.files[0]) return;
    const text = await read_file(file_input.files[0]);
    const collection = JSON.parse(text);
    if (import_layer) state.map.removeLayer(import_layer);
    import_layer = new ol.layer.Vector({ source: new ol.source.Vector() });
    const format = new ol.format.GeoJSON();
    const features = format.readFeatures(collection, { featureProjection: "EPSG:3857", dataProjection: "EPSG:4326" });
    import_layer.getSource().addFeatures(features);
    state.map.addLayer(import_layer);

    if (!window.confirm(`Import ${features.length} features to the server?`)) {
        state.map.removeLayer(import_layer);
        import_layer = null;
        return;
    }

    for (const ol_feature of features) {
        const geometry = ol.format.GeoJSON.writeGeometryObject(ol_feature.getGeometry(), {
            featureProjection: "EPSG:3857",
            dataProjection: "EPSG:4326",
        });
        const properties = ol_feature.get("properties") || {};
        try {
            const created = await api.post(FEATURES_URL, {
                type: "Feature",
                geometry,
                properties,
            });
            const saved_feature = new ol.format.GeoJSON().readFeature(created);
            saved_feature.set("feature_id", created.id);
            saved_feature.set("properties", created.properties);
            state.source.addFeature(saved_feature);
        } catch (error) {
            // continue with remaining features
        }
    }
    state.map.removeLayer(import_layer);
    import_layer = null;
    file_input.value = "";
}

function export_features(state) {
    const ol = window.ol;
    const format = new ol.format.GeoJSON();
    const features = state.source.getFeatures().map((ol_feature) => {
        const cloned = new ol.Feature({
            geometry: ol_feature.getGeometry()?.clone(),
        });
        cloned.set("feature_id", ol_feature.get("feature_id"));
        cloned.set("properties", ol_feature.get("properties") || {});
        return cloned;
    });
    const geojson = format.writeFeatures(features, {
        featureProjection: "EPSG:3857",
        dataProjection: "EPSG:4326",
    });
    const blob = new Blob([geojson], { type: "application/geo+json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "features.geojson";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function initImportExport(state) {
    document.getElementById("import-button")?.addEventListener("click", () => {
        document.getElementById("import-file-input").click();
    });
    document.getElementById("import-file-input")?.addEventListener("change", () => {
        import_file(state).catch(() => {
            // ignore: file picker stays available
        });
    });
    document.getElementById("export-button")?.addEventListener("click", () => export_features(state));
}

export { initImportExport };
```

- [ ] **Step 2: Run the static test for `map-import.js`**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_map_import_js_exports_init_import_export -v`
Expected: 1 pass.

---

## Task 13: `map-panel.js` (right-side inline-edit panel)

**Files:**

- Create: `frontend/static/js/map-panel.js`

The panel listens for `map:open-panel` (dispatched by `map.js` on click and by `search.js` on result click), fetches the detail (to get the audit info), and renders a key/value table. PATCH on Enter (additive — sends the new value for the one key). Esc cancels. The `category` row uses a dropdown of the cached enum plus an "other…" free-text option. "Delete feature" sends `DELETE`.

- [ ] **Step 1: Create `map-panel.js`**

Create `frontend/static/js/map-panel.js`:

```javascript
import { api } from "./api.js";
import { categories } from "./search.js";

function open() {
    document.getElementById("panel").classList.add("open");
    document.getElementById("panel").setAttribute("aria-hidden", "false");
}

function close() {
    document.getElementById("panel").classList.remove("open");
    document.getElementById("panel").setAttribute("aria-hidden", "true");
}

function show_alert(message) {
    const box = document.getElementById("panel-alert");
    if (!box) return;
    box.textContent = message;
    box.classList.remove("d-none");
}

function clear_alert() {
    document.getElementById("panel-alert")?.classList.add("d-none");
}

function clear_table() {
    document.getElementById("panel-properties-tbody").innerHTML = "";
}

function render_property_row(key, value) {
    const tbody = document.getElementById("panel-properties-tbody");
    const row = document.createElement("tr");
    row.dataset.key = key;

    const key_cell = document.createElement("td");
    key_cell.textContent = key;
    key_cell.className = "text-muted";

    const value_cell = document.createElement("td");
    value_cell.contentEditable = "true";
    value_cell.spellcheck = false;
    value_cell.textContent = value === null || value === undefined ? "" : String(value);
    value_cell.dataset.original = value_cell.textContent;

    const action_cell = document.createElement("td");
    const delete_button = document.createElement("button");
    delete_button.type = "button";
    delete_button.className = "btn btn-sm btn-outline-danger";
    delete_button.textContent = "×";
    delete_button.title = "Delete property";
    action_cell.appendChild(delete_button);

    row.appendChild(key_cell);
    row.appendChild(value_cell);
    row.appendChild(action_cell);
    tbody.appendChild(row);

    value_cell.addEventListener("keydown", async (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            value_cell.blur();
        } else if (event.key === "Escape") {
            event.preventDefault();
            value_cell.textContent = value_cell.dataset.original;
            value_cell.blur();
        }
    });
    value_cell.addEventListener("blur", async () => {
        const next = value_cell.textContent;
        if (next === value_cell.dataset.original) return;
        const feature_id = row.closest("aside").dataset.featureId;
        let parsed = next;
        if (typeof value_cell.dataset.original === "string") {
            const original = value_cell.dataset.original;
            const original_number = Number(original);
            if (original.trim() !== "" && !Number.isNaN(original_number)) {
                const as_number = Number(next);
                if (!Number.isNaN(as_number)) parsed = as_number;
            }
        }
        try {
            const updated = await api.patch(`/api/features/${feature_id}/`, {
                properties: { [key]: parsed },
            });
            value_cell.dataset.original = String(updated.properties?.[key] ?? "");
            value_cell.textContent = value_cell.dataset.original;
            clear_alert();
        } catch (error) {
            show_alert((error && error.message) || "Save failed.");
            value_cell.textContent = value_cell.dataset.original;
        }
    });
    delete_button.addEventListener("click", async () => {
        const feature_id = row.closest("aside").dataset.featureId;
        try {
            await api.patch(`/api/features/${feature_id}/`, {
                properties: { [key]: null },
            });
            row.remove();
            clear_alert();
        } catch (error) {
            show_alert((error && error.message) || "Delete failed.");
        }
    });
}

function render_category_row(feature) {
    const tbody = document.getElementById("panel-properties-tbody");
    const row = document.createElement("tr");
    row.dataset.key = "category";

    const key_cell = document.createElement("td");
    key_cell.textContent = "category";
    key_cell.className = "text-muted";

    const value_cell = document.createElement("td");
    const select = document.createElement("select");
    select.className = "form-select form-select-sm";
    const current = feature.properties?.category || "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "(none)";
    select.appendChild(placeholder);
    for (const value of categories) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    }
    const other = document.createElement("option");
    other.value = "__other__";
    other.textContent = "other…";
    select.appendChild(other);
    if (current && ![...select.options].some((opt) => opt.value === current)) {
        const custom = document.createElement("option");
        custom.value = current;
        custom.textContent = `${current} (custom)`;
        select.insertBefore(custom, other);
    }
    select.value =
        current && [...select.options].some((opt) => opt.value === current) ? current : current ? "__other__" : "";
    if (select.value === "__other__") {
        const custom_input = document.createElement("input");
        custom_input.type = "text";
        custom_input.className = "form-control form-control-sm mt-1";
        custom_input.value = current && select.querySelector(`option[value="${current}"]`) ? "" : current;
        custom_input.placeholder = "Custom category";
        value_cell.appendChild(select);
        value_cell.appendChild(custom_input);
    } else {
        value_cell.appendChild(select);
    }

    const action_cell = document.createElement("td");

    row.appendChild(key_cell);
    row.appendChild(value_cell);
    row.appendChild(action_cell);
    tbody.appendChild(row);

    async function commit() {
        const feature_id = row.closest("aside").dataset.featureId;
        let next = select.value;
        if (next === "__other__") {
            next = value_cell.querySelector("input")?.value || "";
        }
        try {
            const updated = await api.patch(`/api/features/${feature_id}/`, {
                properties: { category: next || null },
            });
            select.value = updated.properties?.category || "";
            clear_alert();
        } catch (error) {
            show_alert((error && error.message) || "Save failed.");
        }
    }
    select.addEventListener("change", commit);
    select.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            commit();
        } else if (event.key === "Escape") {
            event.preventDefault();
            select.value = feature.properties?.category || "";
        }
    });
}

async function open_feature(feature) {
    const panel = document.getElementById("panel");
    panel.dataset.featureId = feature.id;
    clear_alert();
    clear_table();
    let detail = feature;
    try {
        detail = await api.get(`/api/features/${feature.id}/`);
    } catch (error) {
        // fall back to the shallow feature
    }
    for (const [key, value] of Object.entries(detail.properties || {})) {
        if (key === "_audit") continue;
        if (key === "category") {
            render_category_row(detail);
        } else {
            render_property_row(key, value);
        }
    }
    open();
}

async function delete_feature() {
    const panel = document.getElementById("panel");
    const feature_id = panel.dataset.featureId;
    if (!feature_id) return;
    if (!window.confirm("Delete this feature?")) return;
    try {
        await api.delete(`/api/features/${feature_id}/`);
        close();
    } catch (error) {
        show_alert((error && error.message) || "Delete failed.");
    }
}

function initPanel(state) {
    document.getElementById("panel-close")?.addEventListener("click", close);
    document.getElementById("panel-delete")?.addEventListener("click", delete_feature);
    window.addEventListener("map:open-panel", (event) => {
        open_feature(event.detail.feature).catch((error) => {
            show_alert((error && error.message) || "Failed to load feature.");
        });
    });
}

export { initPanel };
```

- [ ] **Step 2: Run the static test for `map-panel.js`**

Run: `docker compose exec web pytest frontend/tests/test_static.py::test_map_panel_js_exports_init_panel -v`
Expected: 1 pass.

---

## Task 14: `edit.html` + `edit.js` (server-paged table)

**Files:**

- Create: `frontend/templates/edit.html`
- Create: `frontend/static/js/edit.js`

The edit page is server-paged: the JS fetches `/api/features/?page=<n>&ordering=<o>` and renders a table. Each row has a sub-table of `properties` keys, with inline-edit (value-only, type-preserving), × delete, and a single `+ add new` button per feature. Sort dropdown drives `?ordering=`. Prev/Next pagination buttons drive `?page=`.

- [ ] **Step 1: Create `edit.html`**

Create `frontend/templates/edit.html`:

```html
{% extends "base.html" %} {% load static %} {% block title %}Edit Properties{% endblock %} {% block content %}
<div class="container py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h3 m-0">Edit Properties</h1>
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
    <div id="edit-alert" class="alert alert-danger d-none" role="alert"></div>
    <table class="table" id="features-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Color</th>
                <th>Category</th>
                <th>Type</th>
                <th>Properties</th>
            </tr>
        </thead>
        <tbody id="features-tbody"></tbody>
    </table>
    <div class="d-flex justify-content-between align-items-center mt-3" id="pagination">
        <button type="button" class="btn btn-outline-secondary btn-sm" id="page-prev">Previous</button>
        <span class="text-muted small" id="page-indicator">Page 1</span>
        <button type="button" class="btn btn-outline-secondary btn-sm" id="page-next">Next</button>
    </div>
</div>
{% endblock %} {% block extra_scripts %}
<script type="module" src="{% static 'js/edit.js' %}"></script>
{% endblock %}
```

- [ ] **Step 2: Create `edit.js`**

Create `frontend/static/js/edit.js`:

```javascript
import { api } from "./api.js";
import { auth } from "./auth.js";
import { categories } from "./search.js";

const LIST_URL = "/api/features/";
const ALLOWED_ORDERING = ["created_at", "-created_at", "updated_at", "-updated_at"];

let current_page = 1;
let current_ordering = "-updated_at";
let next_url = null;
let prev_url = null;

function show_alert(message) {
    const box = document.getElementById("edit-alert");
    if (!box) return;
    box.textContent = message;
    box.classList.remove("d-none");
}

function clear_alert() {
    document.getElementById("edit-alert")?.classList.add("d-none");
}

function clear_table() {
    document.getElementById("features-tbody").innerHTML = "";
}

function render_property_row(feature_id, key, value) {
    const tbody = document.getElementById("features-tbody");
    const row = document.createElement("tr");
    row.dataset.key = key;
    const key_cell = document.createElement("td");
    key_cell.textContent = key;
    key_cell.className = "text-muted small";
    const value_cell = document.createElement("td");
    value_cell.contentEditable = "true";
    value_cell.spellcheck = false;
    value_cell.textContent = value === null || value === undefined ? "" : String(value);
    value_cell.dataset.original = value_cell.textContent;
    value_cell.dataset.type = typeof value;
    const action_cell = document.createElement("td");
    const delete_button = document.createElement("button");
    delete_button.type = "button";
    delete_button.className = "btn btn-sm btn-outline-danger";
    delete_button.textContent = "×";
    action_cell.appendChild(delete_button);

    row.appendChild(key_cell);
    row.appendChild(value_cell);
    row.appendChild(action_cell);
    tbody.appendChild(row);

    value_cell.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            value_cell.blur();
        } else if (event.key === "Escape") {
            event.preventDefault();
            value_cell.textContent = value_cell.dataset.original;
            value_cell.blur();
        }
    });
    value_cell.addEventListener("blur", async () => {
        const next_text = value_cell.textContent;
        if (next_text === value_cell.dataset.original) return;
        let parsed = next_text;
        if (value_cell.dataset.type === "number") {
            const as_number = Number(next_text);
            if (Number.isNaN(as_number)) {
                show_alert(`Value for "${key}" must be numeric.`);
                value_cell.textContent = value_cell.dataset.original;
                return;
            }
            parsed = as_number;
        }
        try {
            const updated = await api.patch(`/api/features/${feature_id}/`, {
                properties: { [key]: parsed },
            });
            value_cell.dataset.original = String(updated.properties?.[key] ?? "");
            value_cell.textContent = value_cell.dataset.original;
            clear_alert();
        } catch (error) {
            show_alert((error && error.message) || "Save failed.");
            value_cell.textContent = value_cell.dataset.original;
        }
    });
    delete_button.addEventListener("click", async () => {
        try {
            await api.patch(`/api/features/${feature_id}/`, { properties: { [key]: null } });
            row.remove();
            clear_alert();
        } catch (error) {
            show_alert((error && error.message) || "Delete failed.");
        }
    });
    return row;
}

function render_add_new_row(feature_id, parent_tbody) {
    const row = document.createElement("tr");
    row.dataset.addNew = "true";
    const key_cell = document.createElement("td");
    const key_input = document.createElement("input");
    key_input.type = "text";
    key_input.maxLength = 100;
    key_input.className = "form-control form-control-sm";
    key_input.placeholder = "key";
    key_cell.appendChild(key_input);

    const type_cell = document.createElement("td");
    const type_select = document.createElement("select");
    type_select.className = "form-select form-select-sm";
    for (const value of ["str", "int", "float", "bool"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        type_select.appendChild(option);
    }
    type_cell.appendChild(type_select);

    const value_cell = document.createElement("td");
    const value_input = document.createElement("input");
    value_input.className = "form-control form-control-sm";
    value_cell.appendChild(value_input);

    const action_cell = document.createElement("td");
    const save_button = document.createElement("button");
    save_button.type = "button";
    save_button.className = "btn btn-sm btn-primary me-1";
    save_button.textContent = "Save";
    save_button.disabled = true;
    const cancel_button = document.createElement("button");
    cancel_button.type = "button";
    cancel_button.className = "btn btn-sm btn-outline-secondary";
    cancel_button.textContent = "×";
    action_cell.appendChild(save_button);
    action_cell.appendChild(cancel_button);

    row.appendChild(key_cell);
    row.appendChild(type_cell);
    row.appendChild(value_cell);
    row.appendChild(action_cell);
    parent_tbody.appendChild(row);

    function update_save_button() {
        save_button.disabled = !key_input.value.trim();
    }
    function update_value_input() {
        value_input.innerHTML = "";
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
        } else {
            const input = document.createElement("input");
            input.type = type_select.value === "str" ? "text" : "number";
            if (type_select.value === "float") input.step = "any";
            input.className = "form-control form-control-sm";
            value_input.replaceWith(input);
            value_input.disabled = false;
        }
    }
    key_input.addEventListener("input", update_save_button);
    type_select.addEventListener("change", update_value_input);
    cancel_button.addEventListener("click", () => row.remove());
    save_button.addEventListener("click", async () => {
        const key = key_input.value.trim();
        if (!key) return;
        let value;
        if (type_select.value === "str") {
            value = value_input.value;
        } else if (type_select.value === "int") {
            const as_int = parseInt(value_input.value, 10);
            if (Number.isNaN(as_int) || String(as_int) !== String(value_input.value)) {
                show_alert(`Value for "${key}" must be an integer.`);
                return;
            }
            value = as_int;
        } else if (type_select.value === "float") {
            const as_float = parseFloat(value_input.value);
            if (Number.isNaN(as_float)) {
                show_alert(`Value for "${key}" must be a number.`);
                return;
            }
            value = as_float;
        } else if (type_select.value === "bool") {
            value = value_input.value === "true";
        }
        try {
            const updated = await api.patch(`/api/features/${feature_id}/`, {
                properties: { [key]: value },
            });
            clear_alert();
            row.remove();
            render_property_row(feature_id, key, updated.properties?.[key]);
        } catch (error) {
            show_alert((error && error.message) || "Save failed.");
        }
    });
    update_save_button();
    update_value_input();
}

function render_feature(feature) {
    const tbody = document.getElementById("features-tbody");
    const row = document.createElement("tr");
    row.dataset.featureId = feature.id;
    row.className = "feature-row";

    const name_cell = document.createElement("td");
    name_cell.textContent = feature.properties?.name || "(unnamed)";
    const color_cell = document.createElement("td");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = feature.properties?.color || "#cccccc";
    color_cell.appendChild(swatch);
    const category_cell = document.createElement("td");
    const category_label = feature.properties?.category || "";
    if (category_label) {
        const badge = document.createElement("span");
        badge.className = "badge bg-secondary";
        badge.textContent = category_label;
        category_cell.appendChild(badge);
    }
    const type_cell = document.createElement("td");
    type_cell.textContent = feature.geometry?.type || "";

    const properties_cell = document.createElement("td");
    const properties_table = document.createElement("table");
    properties_table.className = "table table-sm mb-0";
    const properties_tbody = document.createElement("tbody");
    properties_table.appendChild(properties_tbody);
    properties_cell.appendChild(properties_table);

    const add_button = document.createElement("button");
    add_button.type = "button";
    add_button.className = "btn btn-sm btn-outline-primary mt-2";
    add_button.textContent = "+ add new property";
    add_button.addEventListener("click", () => render_add_new_row(feature.id, properties_tbody));
    properties_cell.appendChild(add_button);

    row.appendChild(name_cell);
    row.appendChild(color_cell);
    row.appendChild(category_cell);
    row.appendChild(type_cell);
    row.appendChild(properties_cell);
    tbody.appendChild(row);

    for (const [key, value] of Object.entries(feature.properties || {})) {
        if (key === "_audit" || key === "name" || key === "color" || key === "category") continue;
        render_property_row(feature.id, key, value);
    }
}

async function load_page() {
    try {
        const url = `${LIST_URL}?page=${current_page}&ordering=${encodeURIComponent(current_ordering)}`;
        const body = await api.get(url);
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
        show_alert((error && error.message) || "Failed to load features.");
    }
}

function initEdit() {
    if (!auth.requireAuth()) return;
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

initEdit();

export { initEdit, render_property_row, render_add_new_row };
```

- [ ] **Step 3: Run the static tests for `edit.js` and `edit.html`**

Run: `docker compose exec web pytest frontend/tests/test_templates.py::test_edit_template_has_table_and_sort_and_pagination frontend/tests/test_static.py::test_edit_js_exports_init_edit -v`
Expected: 2 passes.

---

## Task 15: Run the full test suite + pre-commit

**Files:**

- (no file changes)

- [ ] **Step 1: Run the full pytest suite**

Run: `docker compose exec web pytest -v`
Expected: all tests pass — features (~30), accounts (~10), config (security_middleware, settings_split, urlconf), frontend (~25 from this plan), for ~65 tests total. Any failure means one of the previous tasks' tests regressed.

- [ ] **Step 2: Install pre-commit hooks (first run only) and run them**

On a fresh clone, install the hook scripts so pre-commit can run automatically on commit:

Run: `pre-commit install`

Then run pre-commit against every file changed by this plan:

Run: `pre-commit run --all-files`
Expected: pre-commit passes. Ruff (Python), Biome (JS/JSON), Prettier (HTML), and editorconfig (LF/UTF-8) all clean. Per AGENTS.md, a task is not done until pre-commit passes. If biome flags formatting in the JS modules, run `npx @biomejs/biome@2.5.0 check --write frontend/static/js/` and re-run pre-commit until clean.

- [ ] **Step 3: Smoke-test the running app**

Run: `make up && make migrate && make seed && docker compose exec web python manage.py runserver 0.0.0.0:8000`
Then in a browser: visit `/`, click "View Map", confirm the OSM tiles render. Open DevTools, draw a polygon, enter a name, save; confirm the new feature appears. Click the feature, edit a property, press Enter; confirm the change persists after a hard refresh. Visit `/edit/`, click `+ add new property`, add `population: 5000`, save; confirm the new row appears. Visit `/login/`, log out, log back in.

Expected: all flows work end-to-end. Any failure indicates a wiring bug between a template and its module.

---

## Self-Review

**Spec coverage**

- §2 Routes and templates: covered by Task 3 (views, URLs) and Tasks 4–6 + 10 + 14 (templates).
- §3 Top-nav + search: covered by Task 4 (base.html nav), Task 6 (site.css `.search-dropdown`), Task 8 (`auth.js` user menu), Task 9 (`search.js` debounce + fly-to + categories cache + Esc).
- §4 Map page features: covered by Task 10 (map core + bbox + Load more + click handler), Task 11 (draw + modal + Esc/outside-click/cancel + save error), Task 12 (import/export), Task 13 (panel + category dropdown + delete).
- §5 Edit page features: covered by Task 14 (table + pagination + sort + `+ add new` + type preservation + × delete + error banner). The `name` key in the `+ add new` rule is enforced server-side by Task 1; the client side skips `name` from the sub-table in `render_feature` so a user never sees an inline `name` editor (per spec §5.2.2).
- §6 Static assets: covered by Tasks 4 (base.html CDN tags), 6 (site.css), 7–14 (8 JS modules with named exports).
- §7 Token storage trade-off: covered by Task 7 (api.js `localStorage` keys `access`/`refresh`) and Task 8 (auth.js `clearTokens` on logout).
- Server-side name invariant: covered by Task 1.
- Server-side additive PATCH: covered by Task 2.

**Placeholders**

No "TBD", no "TODO", no "implement later", no "add appropriate error handling" placeholders. Every step shows the full file content (or, for tasks with > 200 lines, the full content — the JS modules are short and complete).

**Type consistency**

`api` is imported as a named export in every module that touches the backend. `auth` is imported as a named export by `login.html`, `register.html`, `map.js`, `edit.js`. The `map:fly-to` and `map:open-panel` event names match across `search.js` → `map.js` → `map-panel.js`. The detail `/api/features/{id}/` URL is used in `map-panel.js`. The `?search=`, `?page=`, `?ordering=`, `?bbox=` query params all match the Feature API spec.
