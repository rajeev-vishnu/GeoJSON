"""Test settings. Used by pytest via DJANGO_SETTINGS_MODULE in pyproject.toml."""

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# pytest-django creates and destroys a per-run test database. We use
# SQLite here so the test suite is runnable without a running Postgres
# (the production stack uses PostGIS; this in-memory engine is only for
# the Foundation-level settings tests). The Feature Data Model spec
# replaces this with the test PostGIS service from docker-compose for
# tests that exercise the spatial types.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}
