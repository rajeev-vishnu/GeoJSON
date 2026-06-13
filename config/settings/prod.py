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
        "DJANGO_SECRET_KEY is set to the .env.example placeholder. Set a real secret key in the deployment environment."
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
# Insert SecurityHeadersMiddleware after SecurityMiddleware (index 0 in
# base.py) so the CSP header is set before any later middleware
# short-circuits the response.

_middleware = list(MIDDLEWARE)  # noqa: F405  (re-exported from base)
_security_middleware_path = "config.middleware.SecurityHeadersMiddleware"

if _security_middleware_path not in _middleware:
    _middleware.insert(1, _security_middleware_path)

MIDDLEWARE = _middleware  # noqa: F405  (re-exported from base)
