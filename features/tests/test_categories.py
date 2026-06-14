"""Tests for the categories endpoint at GET /api/categories/.

2 tests:
- `test_categories_returns_enum_values_in_declaration_order`
- `test_categories_requires_auth`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.django_db


CATEGORIES_URL = "/api/categories/"


def test_categories_returns_enum_values_in_declaration_order(user):
    """GET /api/categories/ returns the 11 enum values in declaration order."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")

    response = client.get(CATEGORIES_URL)

    assert response.status_code == 200
    assert response.json() == [
        "city",
        "town",
        "road",
        "river",
        "canal",
        "rail",
        "park",
        "lake",
        "province",
        "nature_reserve",
        "country",
    ]


def test_categories_requires_auth():
    """GET /api/categories/ without a JWT returns 401."""
    response = APIClient().get(CATEGORIES_URL)

    assert response.status_code == 401
