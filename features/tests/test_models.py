"""Tests for the Feature model: fields, defaults, geometry round-trip, cascade, and indexes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection

from features.models import Feature

if TYPE_CHECKING:
    from accounts.models import User

pytestmark = pytest.mark.django_db


def test_feature_creation(user: User) -> None:
    """Creating a Feature with sensible defaults populates id, geometry, and audit fields."""
    feature = Feature.objects.create(
        geometry=GEOSGeometry("POINT (10 20)", srid=4326),
        created_by=user,
    )

    assert isinstance(feature.id, uuid.UUID)
    assert isinstance(feature.geometry, GEOSGeometry)
    assert feature.geometry.srid == 4326
    assert feature.properties == {}
    assert feature.created_at is not None
    assert feature.updated_at is not None


def test_default_values(user: User) -> None:
    """`is_active` is not on Feature, `properties` defaults to {}, no Meta.ordering."""
    feature = Feature.objects.create(
        geometry=GEOSGeometry("POINT (4.0 52.0)", srid=4326),
        created_by=user,
    )

    field_names = {field.name for field in Feature._meta.get_fields()}

    assert "is_active" not in field_names
    assert feature.properties == {}
    assert Feature._meta.ordering == []


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
def test_geometry_round_trip_all_types(wkt: str, user: User) -> None:
    """Save a Feature with each of the 7 GeoJSON geometry types; WKT round-trips exactly."""
    original_geometry = GEOSGeometry(wkt, srid=4326)
    canonical_wkt = original_geometry.wkt

    saved_feature = Feature.objects.create(
        geometry=original_geometry,
        created_by=user,
    )

    retrieved_feature = Feature.objects.get(pk=saved_feature.pk)

    assert retrieved_feature.geometry.wkt == canonical_wkt
    assert retrieved_feature.geometry.srid == 4326


def test_created_by_cascade(user: User) -> None:
    """Deleting the User deletes their Feature in the same transaction (CASCADE)."""
    feature = Feature.objects.create(
        geometry=GEOSGeometry("POINT (4.0 52.0)", srid=4326),
        created_by=user,
    )
    feature_pk = feature.pk

    user.delete()

    assert not Feature.objects.filter(pk=feature_pk).exists()


def test_indexes_exist(user: User) -> None:
    """All four expected indexes are present on the features_feature table.

    The test creates a Feature to ensure the table exists and
    migrations have run, then queries pg_indexes for the GiST, BTree,
    and trigram GIN indexes.
    """
    Feature.objects.create(
        geometry=GEOSGeometry("POINT (4.0 52.0)", srid=4326),
        created_by=user,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'features_feature'",
        )
        index_rows = cursor.fetchall()

    index_definitions = dict(index_rows)

    gist_geometry_indexes = [
        definition
        for definition in index_definitions.values()
        if "USING gist" in definition and "geometry" in definition
    ]
    assert len(gist_geometry_indexes) == 1, f"Expected one GiST geometry index; got: {gist_geometry_indexes}"

    btree_updated_at_indexes = [
        definition
        for definition in index_definitions.values()
        if "USING btree" in definition and "(updated_at, id)" in definition
    ]
    assert len(btree_updated_at_indexes) == 1, (
        f"Expected one BTree (updated_at, id) index; got: {btree_updated_at_indexes}"
    )

    btree_created_at_indexes = [
        definition
        for definition in index_definitions.values()
        if "USING btree" in definition and "(created_at, id)" in definition
    ]
    assert len(btree_created_at_indexes) == 1, (
        f"Expected one BTree (created_at, id) index; got: {btree_created_at_indexes}"
    )

    assert "features_props_name_trgm_idx" in index_definitions
    trigram_definition = index_definitions["features_props_name_trgm_idx"]
    assert "USING gin" in trigram_definition, f"Trigram index is not GIN: {trigram_definition}"
    assert "gin_trgm_ops" in trigram_definition, f"Trigram index missing gin_trgm_ops opclass: {trigram_definition}"
