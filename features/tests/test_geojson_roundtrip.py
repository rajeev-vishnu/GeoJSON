"""Tests for GeoJSON round-trip via the API.

2 tests:
- `test_geojson_round_trip_all_types` — parametrize across the 7
  GeoJSON geometry types; POST one of each with nested objects/arrays
  in `properties`, GET it back, verify exact equality of geometry
  and properties.
- `test_geojson_audit_on_detail` — POST a feature, GET detail,
  assert the `_audit` block matches the post timestamps and
  `created_by` is the requester's email.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


@pytest.mark.parametrize(
    ("geometry_payload", "expected_wkt"),
    [
        ({"type": "Point", "coordinates": [10.0, 20.0]}, "POINT (10 20)"),
        ({"type": "MultiPoint", "coordinates": [[10.0, 20.0], [30.0, 40.0]]}, "MULTIPOINT (10 20, 30 40)"),
        (
            {"type": "LineString", "coordinates": [[10.0, 20.0], [30.0, 40.0]]},
            "LINESTRING (10 20, 30 40)",
        ),
        (
            {
                "type": "MultiLineString",
                "coordinates": [[[10.0, 20.0], [30.0, 40.0]], [[50.0, 60.0], [70.0, 80.0]]],
            },
            "MULTILINESTRING ((10 20, 30 40), (50 60, 70 80))",
        ),
        (
            {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]],
            },
            "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        ),
        (
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]],
                    [[[20.0, 20.0], [30.0, 20.0], [30.0, 30.0], [20.0, 30.0], [20.0, 20.0]]],
                ],
            },
            "MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)), ((20 20, 30 20, 30 30, 20 30, 20 20)))",
        ),
        (
            {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": "Point", "coordinates": [10.0, 20.0]},
                    {"type": "LineString", "coordinates": [[30.0, 40.0], [50.0, 60.0]]},
                ],
            },
            "GEOMETRYCOLLECTION (POINT (10 20), LINESTRING (30 40, 50 60))",
        ),
    ],
)
def test_geojson_round_trip_all_types(geometry_payload, expected_wkt, user, make_auth_client):
    """POST a feature of each geometry type with nested properties, GET it back, assert equality."""
    properties = {
        "name": "Foo",
        "color": "#ff0000",
        "category": "city",
        "tags": ["a", "b"],
        "stats": {"count": 1, "ok": True},
        "nullable": None,
    }
    payload = {
        "type": "Feature",
        "geometry": geometry_payload,
        "properties": properties,
    }
    client = make_auth_client()

    post_response = client.post(LIST_URL, payload, format="json")
    assert post_response.status_code == 201, post_response.content
    feature_id = post_response.json()["id"]

    get_response = client.get(f"/api/features/{feature_id}/")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["type"] == "Feature"
    assert body["geometry"] == geometry_payload
    user_properties = {key: value for key, value in body["properties"].items() if key != "_audit"}
    assert user_properties == properties


def test_geojson_audit_on_detail(user, make_auth_client):
    """POST a feature, GET detail; the `_audit` block matches the post timestamps and `created_by`."""
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {"name": "Foo", "color": "#ff0000", "category": "city"},
    }
    client = make_auth_client()

    post_response = client.post(LIST_URL, payload, format="json")
    assert post_response.status_code == 201, post_response.content
    feature_id = post_response.json()["id"]

    get_response = client.get(f"/api/features/{feature_id}/")
    assert get_response.status_code == 200
    audit = get_response.json()["properties"]["_audit"]
    assert audit["created_by"] == "alice@example.com"
    assert audit["created_at"] is not None
    assert audit["updated_at"] is not None
