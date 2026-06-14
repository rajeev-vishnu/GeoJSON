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
