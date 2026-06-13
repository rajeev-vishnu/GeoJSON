"""Tests for the settings package split (base, dev, prod, test)."""
from __future__ import annotations

import importlib
import os

import pytest
from django.core.exceptions import ImproperlyConfigured

PLACEHOLDER_SECRET = "change-me-in-production-please-do-not-use"


@pytest.fixture(autouse=True)
def _scrub_django_settings_env() -> None:
    """Strip DJANGO_SETTINGS_MODULE between tests so reloads are clean."""
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)
    yield
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)


def _reload_settings(module_name: str) -> object:
    """Import (or reimport) a settings module and return the module object."""
    module = importlib.import_module(module_name)
    importlib.reload(module)
    return module


def test_base_settings_module_imports_cleanly() -> None:
    """config.settings.base can be imported with no required env vars set."""
    base = _reload_settings("config.settings.base")

    assert base.SECRET_KEY
    assert base.AUTH_USER_MODEL == "accounts.User"
    assert "django.contrib.contenttypes" in base.INSTALLED_APPS
    assert "accounts" in base.INSTALLED_APPS
    assert "features" in base.INSTALLED_APPS
    assert "frontend" in base.INSTALLED_APPS
    assert "corsheaders" in base.INSTALLED_APPS


def test_base_password_validators_match_spec() -> None:
    """All four NIST-aligned AUTH_PASSWORD_VALIDATORS are configured in order."""
    base = _reload_settings("config.settings.base")
    validator_paths = [validator["NAME"] for validator in base.AUTH_PASSWORD_VALIDATORS]

    assert validator_paths[0] == "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    assert validator_paths[1] == "django.contrib.auth.password_validation.MinimumLengthValidator"
    assert validator_paths[2] == "django.contrib.auth.password_validation.CommonPasswordValidator"
    assert validator_paths[3] == "django.contrib.auth.password_validation.NumericPasswordValidator"


def test_base_minimum_length_validator_uses_eight() -> None:
    """The hard floor for password length is 8."""
    base = _reload_settings("config.settings.base")
    minimum_length = next(
        validator
        for validator in base.AUTH_PASSWORD_VALIDATORS
        if validator["NAME"].endswith("MinimumLengthValidator")
    )

    assert minimum_length["OPTIONS"]["min_length"] == 8


def test_base_drf_uses_jwt_authentication() -> None:
    """The default DRF auth class is JWTAuthentication (no Session)."""
    base = _reload_settings("config.settings.base")

    assert "rest_framework_simplejwt.authentication.JWTAuthentication" in (
        base.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    )
    assert "rest_framework.authentication.SessionAuthentication" not in (
        base.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    )


def test_base_database_uses_dj_database_url() -> None:
    """DATABASES['default'] is built from DATABASE_URL via dj-database-url."""
    base = _reload_settings("config.settings.base")

    assert base.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_base_csp_middleware_not_active() -> None:
    """base.py does not add SecurityHeadersMiddleware (only prod does)."""
    base = _reload_settings("config.settings.base")

    assert "config.middleware.SecurityHeadersMiddleware" not in base.MIDDLEWARE


def test_dev_settings_module_inherits_base() -> None:
    """dev.py imports base and overrides DEBUG and email backend."""
    dev = _reload_settings("config.settings.dev")

    assert dev.DEBUG is True
    assert dev.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
    assert dev.INSTALLED_APPS == _reload_settings("config.settings.base").INSTALLED_APPS


def test_test_settings_module_inherits_base() -> None:
    """test.py imports base, sets DEBUG=False, locmem email, ALLOWED_HOSTS."""
    test_settings = _reload_settings("config.settings.test")

    assert test_settings.DEBUG is False
    assert test_settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend"
    assert "*" in test_settings.ALLOWED_HOSTS


def test_prod_settings_applies_security_table() -> None:
    """prod.py enables the full security table from Foundation spec §9."""
    os.environ["DJANGO_SECRET_KEY"] = "this-is-a-real-production-secret-not-the-placeholder"
    prod = _reload_settings("config.settings.prod")

    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS == 31_536_000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.SECURE_REFERRER_POLICY == "same-origin"
    assert prod.X_FRAME_OPTIONS == "DENY"
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_prod_settings_registers_csp_middleware_with_policy() -> None:
    """prod.py wires SecurityHeadersMiddleware with the documented CSP string."""
    os.environ["DJANGO_SECRET_KEY"] = "this-is-a-real-production-secret-not-the-placeholder"
    prod = _reload_settings("config.settings.prod")

    assert "config.middleware.SecurityHeadersMiddleware" in prod.MIDDLEWARE
    assert prod.CONTENT_SECURITY_POLICY == (
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'"
    )


def test_prod_settings_rejects_placeholder_secret() -> None:
    """Importing prod with the placeholder secret raises ImproperlyConfigured."""
    os.environ["DJANGO_SECRET_KEY"] = PLACEHOLDER_SECRET
    # Reload base first so the wildcard re-import in prod.py picks up
    # the placeholder env var; otherwise prod.py sees the cached
    # SECRET_KEY from a previous test.
    _reload_settings("config.settings.base")

    with pytest.raises(ImproperlyConfigured):
        _reload_settings("config.settings.prod")

    # Restore a real secret so subsequent tests do not see the placeholder.
    os.environ["DJANGO_SECRET_KEY"] = "this-is-a-real-production-secret-not-the-placeholder"
    _reload_settings("config.settings.base")
