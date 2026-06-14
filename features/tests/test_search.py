"""Tests for the search filter on the feature list endpoint.

2 tests:
- `test_search_substring_match` — case-insensitive substring match on `properties.name`.
- `test_search_no_match` — unknown substring returns empty `results`.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def test_search_substring_match(user, make_feature, make_auth_client):
    """`?search=amster` returns features whose name contains 'amster' (case-insensitive)."""
    make_feature(properties={"name": "Amsterdam"})
    make_feature(properties={"name": "Rotterdam"})
    make_feature(properties={"name": "West-Amsterdam"})

    response = make_auth_client().get(f"{LIST_URL}?search=amster")

    assert response.status_code == 200
    results = response.json()["results"]
    returned_names = {feature["properties"]["name"] for feature in results}
    assert returned_names == {"Amsterdam", "West-Amsterdam"}


def test_search_no_match(user, make_feature, make_auth_client):
    """An unknown substring returns an empty `results` array."""
    make_feature(properties={"name": "Amsterdam"})
    make_feature(properties={"name": "Rotterdam"})

    response = make_auth_client().get(f"{LIST_URL}?search=zzzzz")

    assert response.status_code == 200
    assert response.json()["results"] == []
