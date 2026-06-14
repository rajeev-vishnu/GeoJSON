"""Features API URL patterns.

Mounts:
- `categories/` — function-based view returning the
  `Feature.Category` enum values.
- `features/` — DRF `DefaultRouter` registered with `FeatureViewSet`,
  exposing `list`, `retrieve`, `create`, `partial_update`, `update`,
  and `destroy` actions at `features/`, `features/{id}/`.
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from features.views import FeatureViewSet, categories_view

app_name = "features"

router = DefaultRouter()
router.register(r"features", FeatureViewSet, basename="features")

urlpatterns = [
    path("categories/", categories_view, name="categories"),
    path("", include(router.urls)),
]
