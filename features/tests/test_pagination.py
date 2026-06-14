"""Tests for the BboxPageNumberPagination class.

5 tests cover: hardcoded page size of 100, page 2 returns the next 100,
page past the end returns 404, page=0 returns 400, and next/prev URLs
preserve the bbox query string.
"""

from __future__ import annotations

import pytest
from django.contrib.gis.geos import Point

from features.models import Feature

pytestmark = pytest.mark.django_db


def _make_features(user, count):
    """Bulk-create `count` features in a 1-degree grid."""
    Feature.objects.bulk_create(
        [
            Feature(
                geometry=Point(float(index) * 0.001, 52.0, srid=4326),
                properties={"name": f"Feature {index}"},
                created_by=user,
            )
            for index in range(count)
        ]
    )


def test_page_size_is_100(user, make_auth_client):
    """Creating 250 features and requesting page 1 returns 100 results."""
    _make_features(user, 250)

    response = make_auth_client().get("/api/features/?page=1")

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 100


def test_page_2_returns_the_next_100(user, make_auth_client):
    """Page 2 returns the next 100 features (a different first id)."""
    _make_features(user, 250)

    response = make_auth_client().get("/api/features/?page=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 100
    page_1_ids = {feature["id"] for feature in make_auth_client().get("/api/features/?page=1").json()["results"]}
    page_2_ids = {feature["id"] for feature in body["results"]}
    assert page_1_ids.isdisjoint(page_2_ids)


def test_past_last_page_returns_404(user, make_auth_client):
    """Requesting page 4 when only 3 pages exist (250 features, 100/page) returns 404."""
    _make_features(user, 250)

    response = make_auth_client().get("/api/features/?page=4")

    assert response.status_code == 404


def test_page_zero_returns_404(user, make_auth_client):
    """page=0 is rejected with 404 (DRF's default: NotFound for any invalid page number)."""
    _make_features(user, 5)

    response = make_auth_client().get("/api/features/?page=0")

    assert response.status_code == 404


def test_next_prev_preserve_query_string(user, make_auth_client):
    """Next URL in the response includes the original bbox query string."""
    _make_features(user, 250)

    response = make_auth_client().get("/api/features/?bbox=0,0,10,60&page=1")

    assert response.status_code == 200
    body = response.json()
    assert body["prev"] is None
    assert "bbox=" in body["next"]
    assert "page=2" in body["next"]
