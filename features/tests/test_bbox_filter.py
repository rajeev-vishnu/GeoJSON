"""Tests for the bbox filter on the feature list endpoint.

6 tests:
- `test_world_fixture_filter` — filter the world fixture set by various bboxes.
- `test_netherlands_fixture_filter` — filter the Netherlands fixture
  set by the Netherlands bbox, a sub-bbox, and a disjoint bbox.
- `test_invalid_bbox_arity` — 3 values → 400.
- `test_invalid_bbox_out_of_range` — `minx=200` → 400.
- `test_invalid_bbox_min_greater_than_max` — `minx > maxx` → 400.
- `test_bbox_omitted_returns_all` — no `bbox` param returns the full set, still paged.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def test_world_fixture_filter(user, world_features, make_auth_client):
    """Filtering the world fixture set by various bboxes returns the expected counts/ids."""
    client = make_auth_client()

    united_kingdom_response = client.get(f"{LIST_URL}?bbox=-10,49,2,60")
    assert united_kingdom_response.status_code == 200
    united_kingdom_ids = {feature["id"] for feature in united_kingdom_response.json()["results"]}
    assert united_kingdom_ids == {
        str(feature.pk) for feature in world_features if feature.properties["name"] == "London"
    }

    southern_response = client.get(f"{LIST_URL}?bbox=-180,-90,180,0")
    assert southern_response.status_code == 200
    southern_ids = {feature["id"] for feature in southern_response.json()["results"]}
    assert southern_ids == {
        str(feature.pk) for feature in world_features if feature.properties["name"] in ("Sydney", "Cape Town")
    }

    antimeridian_response = client.get(f"{LIST_URL}?bbox=140,-90,180,90")
    assert antimeridian_response.status_code == 200
    antimeridian_ids = {feature["id"] for feature in antimeridian_response.json()["results"]}
    sydney_pk = str(next(feature.pk for feature in world_features if feature.properties["name"] == "Sydney"))
    assert sydney_pk in antimeridian_ids


def test_netherlands_fixture_filter(user, netherlands_features, make_auth_client):
    """Filtering the Netherlands fixture set: NL bbox returns all; sub-bbox returns subset; disjoint returns empty."""
    client = make_auth_client()
    all_ids = {str(feature.pk) for feature in netherlands_features}

    full_response = client.get(f"{LIST_URL}?bbox=3.3,50.7,7.3,53.55")
    assert full_response.status_code == 200
    full_ids = {feature["id"] for feature in full_response.json()["results"]}
    assert full_ids == all_ids

    sub_response = client.get(f"{LIST_URL}?bbox=4.5,52.0,5.5,52.5")
    assert sub_response.status_code == 200
    sub_ids = {feature["id"] for feature in sub_response.json()["results"]}
    sub_names = {
        netherlands_feature.properties["name"]
        for netherlands_feature in netherlands_features
        if str(netherlands_feature.pk) in sub_ids
    }
    assert sub_names == {"Amsterdam", "Utrecht"}

    disjoint_response = client.get(f"{LIST_URL}?bbox=-10,40,5,45")
    assert disjoint_response.status_code == 200
    assert disjoint_response.json()["results"] == []


def test_invalid_bbox_arity(user, make_auth_client):
    """A bbox with 3 values → 400."""
    response = make_auth_client().get(f"{LIST_URL}?bbox=1,2,3")

    assert response.status_code == 400


def test_invalid_bbox_out_of_range(user, make_auth_client):
    """A bbox with `minx=200` → 400."""
    response = make_auth_client().get(f"{LIST_URL}?bbox=200,0,210,10")

    assert response.status_code == 400


def test_invalid_bbox_min_greater_than_max(user, make_auth_client):
    """A bbox with `minx > maxx` → 400."""
    response = make_auth_client().get(f"{LIST_URL}?bbox=10,0,5,10")

    assert response.status_code == 400


def test_bbox_omitted_returns_all(user, make_feature, make_auth_client):
    """Omitting `?bbox=` returns the full unfiltered set, still paged."""
    for index in range(5):
        make_feature(properties={"name": f"Feature {index}"})

    response = make_auth_client().get(LIST_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"next", "prev", "results"}
    assert len(body["results"]) == 5
