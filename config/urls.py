"""Root URL configuration.

Routes are mounted at three prefixes:
- "" → frontend (templates for /, /map/, /edit/, /login/, /register/)
- "api/auth/" → accounts (register, login, refresh, me)
- "api/" → features (CRUD + categories)

The Django admin URL is intentionally absent in v1; see the overview
spec's out-of-scope list.
"""
from django.urls import include, path

urlpatterns = [
    path("", include("frontend.urls", namespace="frontend")),
    path("api/auth/", include("accounts.urls", namespace="accounts")),
    path("api/", include("features.urls", namespace="features")),
]
