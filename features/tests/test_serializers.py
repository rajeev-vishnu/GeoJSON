"""Tests for the FeatureSerializer and FeatureListItemSerializer.

4 tests:
- `test_geometry_round_trip_all_types` — parametrize across the 7 GeoJSON
  geometry types; serialize then deserialize then assert equality.
- `test_properties_must_be_dict` — non-dict `properties` rejected with 400.
- `test_properties_rejects_non_json_values` — value with a non-JSON-
  serializable object rejected with 400.
- `test_read_only_fields` — `id`, `created_at`, `updated_at`,
  `created_by` cannot be set by client on POST.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import GEOSGeometry

from features.models import Feature
from features.serializers import FeatureSerializer

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "wkt",
    [
        "POINT (10 20)",
        "MULTIPOINT ((10 20), (30 40))",
        "LINESTRING (10 20, 30 40)",
        "MULTILINESTRING ((10 20, 30 40), (50 60, 70 80))",
        "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        "MULTIPOLYGON (((0 0, 10 0, 10 10, 0 10, 0 0)), ((20 20, 30 20, 30 30, 20 30, 20 20)))",
        "GEOMETRYCOLLECTION (POINT (10 20), LINESTRING (30 40, 50 60))",
    ],
)
def test_geometry_round_trip_all_types(wkt, user):
    """Serialize a feature of each geometry type, deserialize, assert equality."""
    geometry = GEOSGeometry(wkt, srid=4326)
    feature = Feature.objects.create(
        geometry=geometry,
        properties={"name": "Foo", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    body = FeatureSerializer(feature).data
    rebuilt = FeatureSerializer(data=body)
    assert rebuilt.is_valid(), rebuilt.errors
    new_feature = rebuilt.save(created_by=user)

    assert new_feature.geometry.wkt == geometry.wkt
    assert new_feature.geometry.srid == 4326
    assert new_feature.properties == {"name": "Foo", "color": "#ff0000", "category": "city"}


def test_properties_must_be_dict(user):
    """A list passed as `properties` is rejected with 400 and a field-level error."""
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": [1, 2, 3],
    }
    serializer = FeatureSerializer(data=payload)

    assert not serializer.is_valid()
    assert "properties" in serializer.errors


def test_properties_rejects_non_json_values(user):
    """A value with a non-JSON-serializable object is rejected with 400."""
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {"name": "Foo", "weird": object()},
    }
    serializer = FeatureSerializer(data=payload)

    assert not serializer.is_valid()
    assert "properties" in serializer.errors


def test_read_only_fields(user):
    """`id`, `created_at`, `updated_at`, `created_by` cannot be set by client on POST."""
    payload = {
        "type": "Feature",
        "id": str(uuid.uuid4()),
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {"name": "Foo"},
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "created_by": str(user.pk),
    }
    serializer = FeatureSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    new_feature = serializer.save(created_by=user)

    assert new_feature.id != uuid.UUID(payload["id"])
    assert new_feature.created_by.pk == user.pk


def test_name_must_be_non_empty_string_when_present(make_feature):
    """A non-empty `str` is required when the `name` key is present in `properties`."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"name": "", "color": "#ff0000"},
        },
    )
    assert not serializer.is_valid()
    assert "name" in serializer.errors["properties"]


def test_name_valid_when_string(make_feature):
    """A non-empty string `name` is accepted."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"name": "Bar", "color": "#ff0000"},
        },
    )
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize(
    "bad_color",
    ["red", "#fff", "#ff00000", "#zzzzzz", "#ff000", "rgb(255,0,0)", 123, None, ""],
)
def test_color_must_be_hex_string(make_feature, bad_color):
    """`color` must match `#RRGGBB`; any other shape rejected with a `color` field error."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"color": bad_color},
        },
    )
    assert not serializer.is_valid(), f"expected invalid for color={bad_color!r}"
    assert "color" in serializer.errors["properties"], (
        f"expected color field error in properties errors for {bad_color!r}, got {serializer.errors}"
    )


def test_color_accepts_uppercase_hex(make_feature):
    """`#RRGGBB` regex is case-insensitive; `#AABBCC` accepted."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"color": "#AABBCC"},
        },
    )
    assert serializer.is_valid(), serializer.errors


def test_category_must_be_in_enum(make_feature):
    """`category` must be one of `Feature.Category` values, else 400 with `category` field error."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"category": "citty"},
        },
    )
    assert not serializer.is_valid()
    assert "category" in serializer.errors["properties"]


def test_category_null_is_accepted(make_feature):
    """`category: null` is accepted — clears the existing category."""
    feature = make_feature(properties={"name": "Foo", "color": "#ff0000", "category": "city"})

    serializer = FeatureSerializer(
        instance=feature,
        data={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]},
            "properties": {"category": None},
        },
    )
    assert serializer.is_valid(), serializer.errors
