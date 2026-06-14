"""Test settings. Used by pytest via DJANGO_SETTINGS_MODULE in pyproject.toml."""

from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# pytest-django creates a test_<dbname> database automatically during
# test setup. The DATABASE_URL should point at the docker-compose `db`
# service for local runs; in CI the workflow sets it to the service-
# container URL (see CI spec §2).
DATABASES = {
    "default": dj_database_url.config(  # noqa: F405  (re-exported from base)
        default="postgres://geojson:geojson@db:5432/geojson",
        engine="django.contrib.gis.db.backends.postgis",
    ),
}
