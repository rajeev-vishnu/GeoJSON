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
