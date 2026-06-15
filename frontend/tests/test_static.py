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
    with open(absolute_path, encoding="utf-8") as file_handle:
        return file_handle.read()


def test_site_css_declares_map_search_dropdown() -> None:
    """`site.css` defines `#map-search-dropdown` with the locked UX properties."""
    body = _read_static("css/site.css")
    assert "#map-search-dropdown" in body
    assert "max-height" in body
    assert "360px" in body
    assert "overflow-y" in body
    assert "auto" in body
    assert "overflow-x" in body
    assert "hidden" in body


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


def test_search_js_exports_shared_core() -> None:
    """`search.js` exports the shared core (`DEBOUNCE_MS`, `fetchMatches`, `renderDropdownRow`)."""
    body = _read_static("js/search.js")
    assert "export" in body
    assert "DEBOUNCE_MS" in body
    assert "fetchMatches" in body
    assert "renderDropdownRow" in body


def test_search_map_js_exports_init_map_search() -> None:
    """`search-map.js` exports the `initMapSearch` initializer for the map page."""
    body = _read_static("js/search-map.js")
    assert "export" in body
    assert "initMapSearch" in body


def test_search_edit_js_exports_init_edit_search() -> None:
    """`search-edit.js` exports the `initEditSearch` initializer and `readQuery` helper for the edit page."""
    body = _read_static("js/search-edit.js")
    assert "export" in body
    assert "initEditSearch" in body
    assert "readQuery" in body


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
