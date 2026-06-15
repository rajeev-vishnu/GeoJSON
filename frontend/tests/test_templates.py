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
    assert "ol@" in body or "openlayers" in body.lower()


def test_map_template_has_map_search_input(client) -> None:
    """`/map/` includes the per-page `#map-search-input`."""
    body = client.get("/map/").content.decode()
    assert 'id="map-search-input"' in body


def test_edit_template_has_edit_search_input(client) -> None:
    """`/edit/` includes the per-page `#edit-search-input`."""
    body = client.get("/edit/").content.decode()
    assert 'id="edit-search-input"' in body
