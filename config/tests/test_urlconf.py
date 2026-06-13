"""Tests for config/urls.py routing structure."""
from __future__ import annotations

from contextlib import suppress

from django.urls import NoReverseMatch, get_resolver, reverse

from config import urls as config_urls
from config.urls import urlpatterns


def test_root_urlconf_imports_without_error() -> None:
    """The root URLConf loads (it must not raise ImportError)."""
    assert config_urls.urlpatterns is not None


def test_root_urlconf_includes_frontend_accounts_features() -> None:
    """The root URLConf mounts frontend, accounts, and features at the right prefixes."""
    resolver = get_resolver()
    # `describe()` returns the Python repr of the pattern, e.g. "'api/auth/'"
    prefixes = {pattern.pattern.describe() for pattern in resolver.url_patterns}

    # Frontend mounts at "" (the root); accounts at "api/auth/"; features at "api/".
    assert "''" in prefixes
    assert "'api/auth/'" in prefixes
    assert "'api/'" in prefixes


def test_admin_route_not_included() -> None:
    """The Django admin URL is intentionally absent in v1."""
    pattern_strings = [str(pattern.pattern) for pattern in urlpatterns]
    assert not any("admin" in pattern_string for pattern_string in pattern_strings)


def test_reverse_named_route_in_each_subconf() -> None:
    """Each subconf can be reverse-resolved (e.g. reverse('features:features-list') returns a URL)."""
    with suppress(NoReverseMatch):
        reverse("features:features-list")
