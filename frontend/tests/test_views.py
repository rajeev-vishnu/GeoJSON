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
