"""Root URL configuration.

Routes are mounted at three prefixes:
- "" → frontend (templates for /, /map/, /edit/, /login/, /register/)
- "api/auth/" → accounts (register, login, refresh, me)
- "api/" → features (CRUD + categories)

The Django admin URL is intentionally absent in v1; see the overview
spec's out-of-scope list.

The static files URL is wired in unconditionally (not gated on
`DEBUG`) so `runserver` and the test client can both load
`/static/js/*.js` without running `collectstatic`. The view is passed
`insecure=True` so it serves even when `DEBUG=False` (which the test
settings force). In production, `collectstatic` populates
`STATIC_ROOT` and a real web server (nginx, etc.) serves those files;
the Django URL match for `/static/` is harmless.
"""

import re

from django.conf import settings
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path, re_path

urlpatterns = [
    path("", include("frontend.urls", namespace="frontend")),
    path("api/auth/", include("accounts.urls", namespace="accounts")),
    path("api/", include("features.urls", namespace="features")),
    re_path(
        r"^{}(?P<path>.*)$".format(re.escape(settings.STATIC_URL.lstrip("/"))),
        staticfiles_serve,
        kwargs={"insecure": True},
    ),
]
