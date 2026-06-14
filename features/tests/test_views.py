"""End-to-end tests for the FeatureViewSet endpoints.

6 tests cover list auth, list response shape, retrieve audit
wrapper, create, partial update, and delete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient

from features.models import Feature

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def test_list_requires_auth(user):
    """Unauthenticated GET /api/features/ returns 401."""
    Feature.objects.create(geometry=Point(5.0, 52.0, srid=4326), properties={"name": "Foo"}, created_by=user)

    unauthenticated_client = APIClient()
    response = unauthenticated_client.get(LIST_URL)

    assert response.status_code == 401


def test_list_response_shape(user, make_auth_client):
    """GET /api/features/ returns {next, prev, results} with no `count` field."""
    Feature.objects.create(geometry=Point(5.0, 52.0, srid=4326), properties={"name": "Foo"}, created_by=user)

    response = make_auth_client().get(LIST_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"next", "prev", "results"}
    assert "count" not in body
    assert body["prev"] is None
    assert body["next"] is None
    assert len(body["results"]) == 1


def test_retrieve_returns_audit(user, make_auth_client):
    """GET /api/features/{id}/ includes `_audit` inside `properties` and renders `created_by` as email."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Foo", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = make_auth_client().get(f"/api/features/{feature.pk}/")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Feature"
    assert body["id"] == str(feature.pk)
    audit = body["properties"].get("_audit")
    assert audit is not None
    assert audit["created_by"] == "alice@example.com"
    assert "created_at" in audit
    assert "updated_at" in audit


def test_create(user, make_auth_client):
    """POST /api/features/ with a valid Point returns 201 and the GeoJSON shape."""
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {"name": "New", "color": "#00ff00", "category": "town"},
    }

    response = make_auth_client().post(LIST_URL, payload, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "Feature"
    assert body["geometry"] == {"type": "Point", "coordinates": [10.0, 20.0]}
    assert body["properties"]["name"] == "New"
    assert Feature.objects.filter(properties__name="New").exists()


def test_partial_update_merges_properties(user, make_auth_client):
    """PATCH /api/features/{id}/ merges `properties` with the existing dict (additive)."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Old", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = make_auth_client().patch(
        path=f"/api/features/{feature.pk}/",
        data={"properties": {"name": "New"}},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["properties"]["name"] == "New"
    assert body["properties"]["color"] == "#ff0000"
    assert body["properties"]["category"] == "city"
    feature.refresh_from_db()
    assert feature.properties == {
        "name": "New",
        "color": "#ff0000",
        "category": "city",
    }


def test_partial_update_null_deletes_key(user, make_auth_client):
    """PATCH with `{key: null}` removes that key from `properties`."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Foo", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = make_auth_client().patch(
        path=f"/api/features/{feature.pk}/",
        data={"properties": {"category": None}},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert "category" not in body["properties"]
    assert body["properties"]["name"] == "Foo"
    assert body["properties"]["color"] == "#ff0000"
    feature.refresh_from_db()
    assert "category" not in feature.properties


def test_delete(user, make_auth_client):
    """DELETE /api/features/{id}/ returns 204; a subsequent GET returns 404."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Foo"},
        created_by=user,
    )

    response = make_auth_client().delete(f"/api/features/{feature.pk}/")

    assert response.status_code == 204
    follow_up = make_auth_client().get(f"/api/features/{feature.pk}/")
    assert follow_up.status_code == 404
