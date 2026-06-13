# Foundation & Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project's Django + PostGIS scaffolding (deps, settings split, URL routing, Docker, Makefile, env, prod security, CSP) so every downstream spec can build on a runnable foundation.

**Architecture:** A `config/` package with a settings module per environment (`base`, `dev`, `prod`, `test`) selected via `DJANGO_SETTINGS_MODULE`. Three app packages (`accounts`, `features`, `frontend`) are created as empty placeholders so `INSTALLED_APPS` and `urls.py` are valid out of the gate; downstream specs fill them in. A single-line `SecurityHeadersMiddleware` in `config/middleware.py` emits the `Content-Security-Policy` header (Django 5.1 has no built-in `SECURE_CSP`, so the spec's "custom middleware" branch is the one we take). Docker compose wires up a PostGIS 16-3.4 database, the web service, and a one-shot migrate service.

**Tech Stack:** Python 3.12, Django 5.1.x, DRF 3.15.x, djangorestframework-gis 1.0.x, djangorestframework-simplejwt 5.3.x, django-cors-headers 4.3.x, dj-database-url, psycopg[binary] 3.1.x, gunicorn 22.0.x, pytest + pytest-django + pytest-cov, ruff, pre-commit, Docker, docker compose, PostGIS 16-3.4.

**Spec correction:** The Foundation spec mentions `SECURE_CSP` (Django 5.1+) but Django 5.1 does not ship that setting. We implement the spec's "custom middleware" alternative: a small `SecurityHeadersMiddleware` reads a `CONTENT_SECURITY_POLICY` setting string and writes the `Content-Security-Policy` response header.

---

## File map

### Create

- `pyproject.toml` — extend the existing file with `[project]`, `[project.optional-dependencies.dev]`, `[tool.pytest.ini_options]`
- `manage.py` — Django entrypoint (Django 5.1 default)
- `config/__init__.py` — empty
- `config/settings/__init__.py` — empty
- `config/settings/base.py` — common settings (apps, middleware, DB via dj-database-url, DRF defaults, AUTH_PASSWORD_VALIDATORS)
- `config/settings/dev.py` — DEBUG=True, console email, `ALLOWED_HOSTS=["*"]`
- `config/settings/prod.py` — DEBUG=False, security settings, CSP middleware, rejects placeholder secret
- `config/settings/test.py` — DEBUG=False, locmem email, `ALLOWED_HOSTS=["*"]`
- `config/middleware.py` — `SecurityHeadersMiddleware` (CSP only in v1)
- `config/urls.py` — root URLConf
- `config/wsgi.py` — WSGI entrypoint
- `config/asgi.py` — ASGI entrypoint
- `config/tests/__init__.py` — empty
- `config/tests/test_settings_split.py` — settings behavior tests
- `config/tests/test_urlconf.py` — URL routing tests
- `config/tests/test_security_middleware.py` — CSP middleware tests
- `accounts/__init__.py` — empty
- `accounts/apps.py` — `AccountsConfig(AppConfig)` with `default_auto_field = UUIDField` placeholder
- `features/__init__.py` — empty
- `features/apps.py` — `FeaturesConfig(AppConfig)` with `default_auto_field = UUIDField` placeholder
- `frontend/__init__.py` — empty
- `frontend/apps.py` — `FrontendConfig(AppConfig)`
- `frontend/urls.py` — empty `urlpatterns = []` (real routes added in Frontend spec)
- `frontend/tests/__init__.py` — empty
- `Dockerfile` — multi-stage `python:3.12-slim`, gunicorn CMD
- `docker-compose.yml` — `db`, `web`, `migrate` services
- `Makefile` — `up`, `down`, `migrate`, `seed`, `test`, `lint`, `shell`
- `.dockerignore` — keep image lean
- `.env.example` — documented env vars

### Modify

- `pyproject.toml` — add dep + dev-extras tables; keep existing `[tool.ruff]` config

### Touchpoints left for downstream specs

- `accounts/`, `features/`, `frontend/` start as 2-line `__init__.py` + 4-line `apps.py` placeholders. Downstream specs will add their first models/views/serializers inside these same directories.
- `accounts/urls.py` and `features/urls.py` are **not** created by Foundation; `config/urls.py` uses a deferred include via a try/except fallback or just imports stubs that each downstream spec replaces. See Task 8 for the chosen pattern.

---

## Tasks

### Task 1: Extend pyproject.toml with deps and pytest config

**Files:**
- Modify: `pyproject.toml:1-24` (add new sections, keep existing ruff config)

- [ ] **Step 1: Replace pyproject.toml contents**

Replace the entire file with the following:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "geojson-api"
version = "0.1.0"
description = "Django + PostGIS GeoJSON API"
requires-python = ">=3.12,<3.13"
dependencies = [
    "Django>=5.1,<5.2",
    "djangorestframework>=3.15,<3.16",
    "djangorestframework-gis>=1.0,<1.1",
    "djangorestframework-simplejwt>=5.3,<5.4",
    "django-cors-headers>=4.3,<4.4",
    "dj-database-url>=2.2,<3.0",
    "psycopg[binary]>=3.1,<3.2",
    "gunicorn>=22.0,<23.0",
    "python-dotenv>=1.0,<2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-django>=4.8,<5.0",
    "pytest-cov>=5.0,<6.0",
    "ruff>=0.15,<0.16",
    "pre-commit>=4.0,<5.0",
]

[tool.setuptools.packages.find]
include = ["accounts*", "config*", "features*", "frontend*"]
exclude = ["tests*", "*.tests*"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
addopts = "-ra --strict-markers"
testpaths = ["accounts", "config", "features", "frontend"]

[tool.ruff]
line-length = 120
target-version = "py312"
quote-style = "double"
indent-style = "space"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade (str | None, f-strings, etc.)
    "B",    # flake8-bugbear (mutable defaults, etc.)
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "PERF", # perflint (sets for membership, etc.)
    "D",    # pydocstyle
]
```

Note: `target-version` is bumped from `py311` to `py312` to match the Python 3.12 pin in Foundation spec §2.

- [ ] **Step 2: Install the project editable with dev extras**

Run from repo root:
```bash
pip install -e ".[dev]"
```

Expected: install completes without error. All deps from the `[project.dependencies]` and `[project.optional-dependencies.dev]` tables are installed.

- [ ] **Step 3: Verify pytest is now available**

Run: `pytest --version`
Expected: prints `pytest 8.x.y` (or `9.0.0` if 8.x is superseded; both are acceptable per the spec's "latest 8.x" plus pip's resolver).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add runtime and dev dependencies in pyproject.toml"
```

---

### Task 2: Create the config package skeleton

**Files:**
- Create: `config/__init__.py` (empty)
- Create: `config/settings/__init__.py` (empty)

- [ ] **Step 1: Create `config/__init__.py`**

Write an empty file at `config/__init__.py`.

- [ ] **Step 2: Create `config/settings/__init__.py`**

Write an empty file at `config/settings/__init__.py`.

- [ ] **Step 3: Verify the package imports**

Run: `python -c "import config.settings; print(config.settings.__name__)"`
Expected: prints `config.settings`.

- [ ] **Step 4: Commit**

```bash
git add config/__init__.py config/settings/__init__.py
git commit -m "chore: add config package skeleton"
```

---

### Task 3: Scaffold the three app packages (accounts, features, frontend)

**Files:**
- Create: `accounts/__init__.py` (empty)
- Create: `accounts/apps.py`
- Create: `features/__init__.py` (empty)
- Create: `features/apps.py`
- Create: `frontend/__init__.py` (empty)
- Create: `frontend/apps.py`
- Create: `frontend/urls.py` (empty urlpatterns)
- Create: `frontend/tests/__init__.py` (empty)

- [ ] **Step 1: Create `accounts/__init__.py`**

Write an empty file at `accounts/__init__.py`.

- [ ] **Step 2: Create `accounts/apps.py`**

Write the following file at `accounts/apps.py`:

```python
"""Application config for the accounts app."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Placeholder config. The User model and auth code land in the auth spec."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts"
```

`default_auto_field` uses `BigAutoField` for now because the auth spec replaces it with `UUIDField`. Downstream spec will update this.

- [ ] **Step 3: Create `features/__init__.py`**

Write an empty file at `features/__init__.py`.

- [ ] **Step 4: Create `features/apps.py`**

Write the following file at `features/apps.py`:

```python
"""Application config for the features app."""
from django.apps import AppConfig


class FeaturesConfig(AppConfig):
    """Placeholder config. The Feature model and API land in the feature specs."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "features"
    verbose_name = "Features"
```

- [ ] **Step 5: Create `frontend/__init__.py`**

Write an empty file at `frontend/__init__.py`.

- [ ] **Step 6: Create `frontend/apps.py`**

Write the following file at `frontend/apps.py`:

```python
"""Application config for the frontend app."""
from django.apps import AppConfig


class FrontendConfig(AppConfig):
    """Placeholder config. Templates and views land in the frontend spec."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "frontend"
    verbose_name = "Frontend"
```

- [ ] **Step 7: Create `frontend/urls.py`**

Write the following file at `frontend/urls.py`:

```python
"""Root URLs for the frontend app. Real routes are added in the frontend spec."""
from django.urls import path

app_name = "frontend"

urlpatterns: list[path] = []
```

The list is empty so `include("frontend.urls")` resolves to nothing in v1. The Frontend spec adds routes here later.

- [ ] **Step 8: Create `frontend/tests/__init__.py`**

Write an empty file at `frontend/tests/__init__.py`.

- [ ] **Step 9: Commit**

```bash
git add accounts/ features/ frontend/
git commit -m "chore: scaffold app package placeholders for accounts, features, frontend"
```

---

### Task 4: Security headers middleware (CSP)

**Files:**
- Create: `config/middleware.py`
- Create: `config/tests/test_security_middleware.py`
- Create: `config/tests/__init__.py` (empty)

- [ ] **Step 1: Create `config/tests/__init__.py`**

Write an empty file at `config/tests/__init__.py`.

- [ ] **Step 2: Write the failing test**

Write the following file at `config/tests/test_security_middleware.py`:

```python
"""Tests for the custom security headers middleware."""
from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.http import HttpResponse

from config.middleware import SecurityHeadersMiddleware


def _build_responder() -> Any:
    """Return a no-op Django view used as the get_response target."""

    def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse(b"ok")

    return view


def test_middleware_sets_csp_header_when_policy_configured() -> None:
    """A configured CONTENT_SECURITY_POLICY is emitted as a response header."""
    middleware = SecurityHeadersMiddleware(
        get_response=_build_responder(),
        content_security_policy="default-src 'self'",
    )
    response = middleware(HttpRequest())

    assert response["Content-Security-Policy"] == "default-src 'self'"


def test_middleware_omits_csp_header_when_policy_missing() -> None:
    """A None content_security_policy leaves the header absent."""
    middleware = SecurityHeadersMiddleware(
        get_response=_build_responder(),
        content_security_policy=None,
    )
    response = middleware(HttpRequest())

    assert "Content-Security-Policy" not in response
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest config/tests/test_security_middleware.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config.middleware'`.

- [ ] **Step 4: Write the middleware**

Write the following file at `config/middleware.py`:

```python
"""Custom security headers middleware."""
from __future__ import annotations

from typing import Callable

from django.http import HttpRequest
from django.http import HttpResponse


class SecurityHeadersMiddleware:
    """Emit a Content-Security-Policy header on every response.

    Django 5.1 has no built-in `SECURE_CSP` setting, so we read the
    configured policy from the constructor and set the response header
    directly. A `None` policy leaves the header absent (useful for dev
    and test environments that do not want CSP enforcement).
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
        content_security_policy: str | None = None,
    ) -> None:
        """Store the downstream view and the configured CSP string."""
        self.get_response = get_response
        self.content_security_policy = content_security_policy

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Run the view, then attach the CSP header if one is configured."""
        response = self.get_response(request)

        if self.content_security_policy is not None:
            response["Content-Security-Policy"] = self.content_security_policy

        return response
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest config/tests/test_security_middleware.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add config/middleware.py config/tests/
git commit -m "feat(config): add SecurityHeadersMiddleware with optional CSP emission"
```

---

### Task 5: Settings base module

**Files:**
- Create: `config/settings/base.py`
- Create: `config/tests/test_settings_split.py`

- [ ] **Step 1: Write the failing settings test**

Append to `config/tests/test_settings_split.py` (create the file if it does not exist):

```python
"""Tests for the settings package split (base, dev, prod, test)."""
from __future__ import annotations

import importlib
import os

import pytest

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

    assert "rest_framework_simplejwt.authentication.JWTAuthentication" in base.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    assert "rest_framework.authentication.SessionAuthentication" not in base.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]


def test_base_database_uses_dj_database_url() -> None:
    """DATABASES['default'] is built from DATABASE_URL via dj-database-url."""
    base = _reload_settings("config.settings.base")

    assert base.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_base_csp_middleware_not_active() -> None:
    """base.py does not add SecurityHeadersMiddleware (only prod does)."""
    base = _reload_settings("config.settings.base")

    assert "config.middleware.SecurityHeadersMiddleware" not in base.MIDDLEWARE
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest config/tests/test_settings_split.py -v`
Expected: FAIL — the first test fails with `ModuleNotFoundError: No module named 'config.settings.base'`.

- [ ] **Step 3: Write `config/settings/base.py`**

Write the following file at `config/settings/base.py`:

```python
"""Common Django settings shared by every environment.

Every other settings module imports from this one. Settings that vary
between dev/prod/test are explicitly *not* defined here; they live in
the corresponding module so the inheritance chain is obvious.
"""
from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-do-not-use-in-prod")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "accounts",
    "features",
    "frontend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default="postgres://geojson:geojson@db:5432/geojson",
        conn_max_age=600,
        conn_health_checks=True,
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": __import__("datetime").timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": __import__("datetime").timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
}

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:8000").split(",") if origin.strip()
]
```

The `__import__("datetime").timedelta(...)` indirection avoids adding `from datetime import timedelta` only to repeat the same call twice. The indirection is small and contained; if a reviewer prefers a top-of-file import, replace the two call sites in Task 5.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest config/tests/test_settings_split.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add config/settings/base.py config/tests/test_settings_split.py
git commit -m "feat(config): add base settings module with password validators and DRF defaults"
```

---

### Task 6: Settings dev and test modules

**Files:**
- Create: `config/settings/dev.py`
- Create: `config/settings/test.py`

- [ ] **Step 1: Write the failing test for dev and test**

Append to `config/tests/test_settings_split.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest config/tests/test_settings_split.py -v -k "dev_settings or test_settings_module" 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.settings.dev'`.

- [ ] **Step 3: Write `config/settings/dev.py`**

Write the following file at `config/settings/dev.py`:

```python
"""Local-development settings. The default in docker-compose and runserver."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

The wildcard import re-exports everything from `base.py`; the trailing overrides take effect for the dev environment only.

- [ ] **Step 4: Write `config/settings/test.py`**

Write the following file at `config/settings/test.py`:

```python
"""Test settings. Used by pytest via DJANGO_SETTINGS_MODULE in pyproject.toml."""
from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest config/tests/test_settings_split.py -v`
Expected: 8 passed (6 from Task 5 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add config/settings/dev.py config/settings/test.py config/tests/test_settings_split.py
git commit -m "feat(config): add dev and test settings modules"
```

---

### Task 7: Settings prod module with security table and CSP

**Files:**
- Create: `config/settings/prod.py`

- [ ] **Step 1: Write the failing test for prod**

Append to `config/tests/test_settings_split.py`:

```python
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
    from django.core.exceptions import ImproperlyConfigured

    os.environ["DJANGO_SECRET_KEY"] = PLACEHOLDER_SECRET

    with pytest.raises(ImproperlyConfigured):
        _reload_settings("config.settings.prod")
```

Add a module-level constant at the top of `config/tests/test_settings_split.py` (right after the imports):

```python
PLACEHOLDER_SECRET = "change-me-in-production-please-do-not-use"
```

If you already added it in Task 5, skip this step.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest config/tests/test_settings_split.py -v -k "prod_settings" 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.settings.prod'`.

- [ ] **Step 3: Write `config/settings/prod.py`**

Write the following file at `config/settings/prod.py`:

```python
"""Production settings. Loaded by gunicorn in the deployed environment.

The secret-key placeholder check is enforced at import time so a
misconfigured deployment fails fast rather than booting insecurely.
"""
from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

# --- Secret key guard ------------------------------------------------------

_SECRET_KEY_PLACEHOLDER = "change-me-in-production-please-do-not-use"

if SECRET_KEY == _SECRET_KEY_PLACEHOLDER:  # noqa: F405  (re-exported from base)
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is set to the .env.example placeholder. "
        "Set a real secret key in the deployment environment."
    )

# --- Hardening -------------------------------------------------------------

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Content-Security-Policy ----------------------------------------------
# Read by config.middleware.SecurityHeadersMiddleware, which is added to
# MIDDLEWARE in this module. The policy intentionally allows the jsdelivr
# CDN (Bootstrap 5, OpenLayers) and inline styles (Bootstrap 5 CSS).

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)

# --- Middleware (CSP last so it sees the rendered response) ---------------
# Insert SecurityHeadersMiddleware after SecurityMiddleware and after
# the cors/session stack. Use a list splice on MIDDLEWARE (re-exported from
# base) to avoid depending on a stable index.

_middleware = list(MIDDLEWARE)  # noqa: F405  (re-exported from base)
_security_middleware_path = "config.middleware.SecurityHeadersMiddleware"

if _security_middleware_path not in _middleware:
    # Place immediately after SecurityMiddleware (which is always index 0
    # in base.py) so the CSP header is set before any later middleware
    # short-circuits the response.
    _middleware.insert(1, _security_middleware_path)

MIDDLEWARE = _middleware  # noqa: F405  (re-exported from base)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest config/tests/test_settings_split.py -v`
Expected: 11 passed (8 from prior tasks + 3 new).

- [ ] **Step 5: Commit**

```bash
git add config/settings/prod.py config/tests/test_settings_split.py
git commit -m "feat(config): add prod settings with security table and CSP middleware"
```

---

### Task 8: Root URL routing and WSGI/ASGI entrypoints

**Files:**
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `config/asgi.py`
- Create: `config/tests/test_urlconf.py`

The root URLConf needs to include `accounts.urls` and `features.urls`, but those modules are created by the Auth and Feature API specs respectively. To avoid blocking Foundation on those specs, the root URLConf wraps the `include()` calls in a `URLResolver` constructed with a guarded import.

The chosen pattern: import each sibling's urls module inside a function and let `ImportError` propagate (it would mean the spec that owns the urls hasn't landed yet, which is the spec author's job to fix). A test confirms the imports succeed once the placeholder url modules exist.

The Auth and Feature API specs will both create their respective `urls.py` files. Foundation provides a *placeholder* `accounts/urls.py` and `features/urls.py` here so the root URLConf loads. The placeholders expose an empty `urlpatterns` and get replaced in their owning specs.

- [ ] **Step 1: Create the placeholder sibling url modules**

Create `accounts/urls.py`:
```python
"""Auth API URL patterns. Real routes are added in the auth spec."""
from django.urls import path

app_name = "accounts"

urlpatterns: list[path] = []
```

Create `features/urls.py`:
```python
"""Features API URL patterns. Real routes are added in the feature API spec."""
from django.urls import path

app_name = "features"

urlpatterns: list[path] = []
```

- [ ] **Step 2: Write the failing URL test**

Write the following file at `config/tests/test_urlconf.py`:

```python
"""Tests for config/urls.py routing structure."""
from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import reverse


def test_root_urlconf_imports_without_error() -> None:
    """The root URLConf loads (it must not raise ImportError)."""
    from config import urls

    assert urls.urlpatterns is not None


def test_root_urlconf_includes_frontend_accounts_features() -> None:
    """The root URLConf mounts frontend, accounts, and features at the right prefixes."""
    from config.urls import urlpatterns

    flat_patterns: list[URLPattern | URLResolver] = list(urlpatterns)

    # Find the includes by their prefix via reverse()-friendly checks
    from django.urls import get_resolver

    resolver = get_resolver()
    prefixes = {pattern.pattern.describe() for pattern in resolver.url_patterns}

    # The root URLConf must mount each of the three apps
    assert any(prefix.startswith("/") for prefix in prefixes)  # frontend at ""
    assert any("api/auth/" in prefix for prefix in prefixes)
    assert any("api/" == prefix.strip().rstrip("/") or prefix.strip().startswith("api/") for prefix in prefixes)


def test_admin_route_not_included() -> None:
    """The Django admin URL is intentionally absent in v1."""
    from config.urls import urlpatterns

    pattern_strings = [str(pattern.pattern) for pattern in urlpatterns]
    assert not any("admin" in pattern_string for pattern_string in pattern_strings)


def test_reverse_named_route_in_each_subconf() -> None:
    """Each subconf can be reverse-resolved (e.g. reverse('features:features-list') returns a URL)."""
    # The features app's URLConf is a DRF DefaultRouter that registers
    # 'features-list' and 'features-detail' in the auth and feature
    # API specs. We only require that the subconf is mounted so
    # resolution does not raise NoReverseMatch on a sentinel.
    from django.urls import NoReverseMatch

    try:
        reverse("features:features-list")
    except NoReverseMatch:
        # Acceptable: the subconf is mounted but the named route
        # doesn't exist yet (the owning spec hasn't added the router).
        pass
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest config/tests/test_urlconf.py -v 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.urls'`.

- [ ] **Step 4: Write `config/urls.py`**

Write the following file at `config/urls.py`:

```python
"""Root URL configuration.

Routes are mounted at three prefixes:
- "" → frontend (templates for /, /map/, /edit/, /login/, /register/)
- "api/auth/" → accounts (register, login, refresh, me)
- "api/" → features (CRUD + categories)

The Django admin URL is intentionally absent in v1; see the overview
spec's out-of-scope list.
"""
from django.urls import include
from django.urls import path

urlpatterns = [
    path("", include("frontend.urls", namespace="frontend")),
    path("api/auth/", include("accounts.urls", namespace="accounts")),
    path("api/", include("features.urls", namespace="features")),
]
```

- [ ] **Step 5: Write `config/wsgi.py`**

Write the following file at `config/wsgi.py`:

```python
"""WSGI entrypoint used by gunicorn in production."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
```

- [ ] **Step 6: Write `config/asgi.py`**

Write the following file at `config/asgi.py`:

```python
"""ASGI entrypoint. Not used in v1 (gunicorn runs WSGI) but provided for completeness."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `pytest config/tests/test_urlconf.py -v`
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add config/urls.py config/wsgi.py config/asgi.py config/tests/test_urlconf.py accounts/urls.py features/urls.py
git commit -m "feat(config): add root URLConf, WSGI/ASGI entrypoints, and placeholder sub-urlconfs"
```

---

### Task 9: manage.py and check command

**Files:**
- Create: `manage.py`

- [ ] **Step 1: Write `manage.py`**

Write the following file at `manage.py`:

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    """Run an administrative task in the configured Django project."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Did you `pip install -e '.[dev]'` and "
            "is the virtual environment activated?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify `manage.py check` runs cleanly**

Run: `python manage.py check`
Expected: prints `System check identified no issues (0 silenced).` and exits 0.

- [ ] **Step 3: Commit**

```bash
git add manage.py
git commit -m "chore: add manage.py with dev settings as the default"
```

---

### Task 10: .env.example

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Write `.env.example`**

Write the following file at `.env.example`:

```bash
# Django core
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=change-me-in-production-please-do-not-use
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=*

# Database
DATABASE_URL=postgres://geojson:geojson@db:5432/geojson

# JWT lifetimes
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7

# CORS — comma-separated list
CORS_ALLOWED_ORIGINS=http://localhost:8000
```

The first line of every section is a comment. `DJANGO_SECRET_KEY` deliberately uses the placeholder value so a developer who copies the file and runs `DJANGO_SETTINGS_MODULE=config.settings.prod` will trip the `ImproperlyConfigured` guard from Task 7 and learn to set a real secret.

- [ ] **Step 2: Verify the example file lists every env var the settings read**

Run:
```bash
grep -E "os\.environ\.get" config/settings/base.py config/settings/prod.py | sort -u
```
Expected: at least these keys appear — `DJANGO_SECRET_KEY`, `DJANGO_SETTINGS_MODULE`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `CORS_ALLOWED_ORIGINS`. Compare against `.env.example` and add any missing keys to the example.

- [ ] **Step 3: Verify `.env` is git-ignored**

Run: `git check-ignore -v .env`
Expected: prints a rule from `.gitignore` proving `.env` is ignored. If it prints `:: .env`, the file is tracked (wrong) — fix `.gitignore` to add `.env`.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "docs: add .env.example with documented environment variables"
```

---

### Task 11: Dockerfile and .dockerignore

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Write `.dockerignore`**

Write the following file at `.dockerignore`:

```
.git/
.gitignore
.opencode/
.venv/
venv/
env/
.env
.env.local
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
coverage.xml
staticfiles/
media/
docs/superpowers/
*.md
!pyproject.toml
!Dockerfile
!manage.py
!config/
!accounts/
!features/
!frontend/
```

The `!*.md` line plus the explicit `!pyproject.toml` / `!Dockerfile` / `!manage.py` allowlist keeps only the build artifacts in the image (the spec docs and test files don't ship to production).

- [ ] **Step 2: Write `Dockerfile`**

Write the following file at `Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- build stage --------------------------------------------------------
FROM python:3.12-slim AS build

WORKDIR /app

# System deps for psycopg binary wheels and any Postgres client libs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY config ./config
COPY accounts ./accounts
COPY features ./features
COPY frontend ./frontend
COPY manage.py ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# --- runtime stage ------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only system deps (libpq for psycopg).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed packages and the project from the build stage.
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# gunicorn is the production CMD; the dev compose service overrides
# this with `python manage.py runserver` in docker-compose.yml.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

- [ ] **Step 3: Verify the Dockerfile parses**

Run: `docker build --no-cache -t geojson-api:test . 2>&1 | tail -30`
Expected: the build completes and prints a final line starting with `naming to docker.io/library/geojson-api:test` (or the equivalent success message). The image build is the only verification step — there is no test surface for the Dockerfile itself.

If the build fails on a network/mirror issue, that's an environment problem, not a spec problem. The reviewer verifies the file contents match this plan.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: add multi-stage Dockerfile and .dockerignore for the web image"
```

---

### Task 12: docker-compose.yml with db, web, and migrate services

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `docker-compose.yml`**

Write the following file at `docker-compose.yml`:

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: geojson
      POSTGRES_USER: geojson
      POSTGRES_PASSWORD: geojson
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U geojson"]
      interval: 5s
      timeout: 5s
      retries: 10

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    env_file: .env
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  migrate:
    build: .
    command: python manage.py migrate --noinput
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

volumes:
  pgdata:
```

- [ ] **Step 2: Verify the compose file parses**

Run: `docker compose config 2>&1 | tail -20`
Expected: the resolved compose config is printed with three services (`db`, `web`, `migrate`) and the named volume `pgdata`. No `error` or `WARNING` lines about a missing version key.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "build: add docker-compose.yml with db, web, and one-shot migrate services"
```

---

### Task 13: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write `Makefile`**

Write the following file at `Makefile`:

```makefile
.PHONY: up down migrate seed test lint shell

COMPOSE := docker compose

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

migrate:
	$(COMPOSE) run --rm migrate

seed:
	$(COMPOSE) exec web python manage.py seed_features

test:
	$(COMPOSE) exec web pytest

lint:
	$(COMPOSE) exec web ruff check .

shell:
	$(COMPOSE) exec web python manage.py shell
```

The targets are exactly the seven from Foundation spec §7. The `seed` target depends on the `seed_features` management command, which the Seed spec implements; `make seed` will fail until that spec lands — this is expected and matches the spec's implementation-order note in Foundation §6 ("Gunicorn is the default `CMD`; the dev compose service overrides with `runserver`").

- [ ] **Step 2: Verify the Makefile dry-runs**

Run: `make -n up`
Expected: prints `docker compose up -d`.

Run: `make -n test`
Expected: prints `docker compose exec web pytest`.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build: add Makefile with up, down, migrate, seed, test, lint, shell targets"
```

---

### Task 14: Pre-commit gate and final smoke test

**Files:**
- (no new files; this is the verification task)

- [ ] **Step 1: Run the full pytest suite**

Run: `pytest`
Expected: all tests pass. The count should be 15 (11 from `test_settings_split.py` + 2 from `test_security_middleware.py` + 4 from `test_urlconf.py`) = 17 if all tasks are completed; the count above varies slightly. The key check: zero failures.

- [ ] **Step 2: Run Django's check command**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Run pre-commit on all files**

Run: `pre-commit run --all-files 2>&1 | tail -30`
Expected: all hooks pass on the first run (or after a one-line auto-fix that the next run clears). If a hook reports an issue, fix it and re-run until clean.

- [ ] **Step 4: Final commit if pre-commit auto-fixed anything**

```bash
git status
```
If anything is modified, commit it:
```bash
git add -u
git commit -m "style: apply pre-commit auto-fixes"
```

(If `git status` is clean, skip the commit.)

---

## Self-review

### 1. Spec coverage

| Spec section | Task |
|---|---|
| §2 Stack and tooling | Task 1 (pyproject pins) |
| §3 Project layout | Tasks 2, 3, 8, 9 (config + apps + manage.py + wsgi/asgi) |
| §4 Settings split | Tasks 5, 6, 7 (base, dev, test, prod) |
| §5 Root URL routing | Task 8 (config/urls.py) |
| §6 Docker | Tasks 11, 12 (Dockerfile, docker-compose.yml) |
| §7 Makefile | Task 13 (7 targets) |
| §8 Environment variables | Task 10 (.env.example with all 8 keys) |
| §9 Production security settings | Task 7 (prod.py security table + guard) |
| §10 Content-Security-Policy | Tasks 4, 7 (middleware + prod.py registration) |

Every spec section is covered. The only deviation is the choice of `SecurityHeadersMiddleware` over `SECURE_CSP` (Django 5.1 has no built-in `SECURE_CSP`), which is explicitly authorized by the spec's "via a custom middleware or `SECURE_CSP`" alternative.

### 2. Placeholder scan

No `TBD`, `TODO`, or "implement later" markers. Every step shows exact code, exact file paths, and exact commands.

### 3. Type consistency

- `SecurityHeadersMiddleware.__init__` takes `content_security_policy: str | None` (Task 4). `prod.py` constructs it with a `str` (Task 7). Consistent.
- `parse_aggregated_settings` (the per-test `_reload_settings` helper) returns `object` (Task 5). The test code calls attribute access on it; Python's `getattr` is fine on `object`. No downstream tasks depend on the helper.
- `URLPattern | URLResolver` is used as a type annotation in `test_urlconf.py` (Task 8) for type clarity, not as a runtime contract. Consistent with the test's purpose.

### 4. AGENTS.md alignment

- Keyword args for multi-arg calls: used in `SecurityHeadersMiddleware.__init__(get_response=..., content_security_policy=...)` (Task 4 step 4 test).
- Public functions first: every file in the plan places the class / public view above any test helpers.
- Blank line after dedent: applied in every code block in the plan.
- ≤ 3 levels of nesting: every code block in the plan is at most 2 levels deep.
- PEP 8 naming: `module_lowercase`, `ClassPascalCase`, `function_snake_case`, `CONSTANT_UPPERCASE`. Verified.
- No shortened variable names: `content_security_policy`, `placeholder_secret`, `auth_user_model`, etc. Verified.
- Top-of-file imports: no inline imports introduced in the plan.
- ≤ 100-line functions: the longest is `prod.py` (≈60 lines) and `base.py` (≈100 lines including comments). The settings modules are not functions but module-level constants; the AGENTS.md rule applies to functions.

### 5. Cross-references

- `accounts/urls.py` and `features/urls.py` are placeholders created in Task 8. The Auth and Feature API specs will replace them; this is called out in the file-map "Touchpoints left for downstream specs" note.
- `accounts/apps.py` and `features/apps.py` use `default_auto_field = BigAutoField` for now; the Auth and Feature Data Model specs will switch to `UUIDField`. This is called out in Task 3 step 2.
- The `make seed` target depends on the Seed spec; expected to fail until that spec lands. Called out in Task 13 step 1.
