"""Tests for the custom security headers middleware."""
from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse

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
