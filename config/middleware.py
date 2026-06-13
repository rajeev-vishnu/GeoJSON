"""Custom security headers middleware."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


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
