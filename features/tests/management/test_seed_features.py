"""Tests for the seed_features management command: bundle loading, color map, curated rows."""

from __future__ import annotations

from collections import Counter
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection

from features.models import Feature

pytestmark = pytest.mark.django_db

FIXTURE_SEED_DATA_DIR = Path(__file__).parent.parent / "fixtures" / "seed_data"


def _run_seed() -> None:
    """Run `python manage.py seed_features` against the test database.

    Captures stdout to a StringIO so the tests can stay quiet; the
    command's text output is not under test here.
    """
    call_command("seed_features", stdout=StringIO())


@pytest.fixture
def fixture_seed_data(monkeypatch) -> None:
    """Swap the production `seed_data/` directory for the fixture bundle for one test."""
    import features.management.commands.seed_features as seed_module

    monkeypatch.setattr(seed_module, "_SEED_DATA_DIR_OVERRIDE", FIXTURE_SEED_DATA_DIR)


def test_seed_loads_features_from_bundle(fixture_seed_data) -> None:
    """Running seed_features creates one Feature per fixture-bundle entry."""
    _run_seed()

    assert Feature.objects.count() == 12
    assert Feature.objects.filter(properties__name="TestCity").exists()
    assert Feature.objects.filter(properties__name="TestTown").exists()
    assert Feature.objects.filter(properties__name="TestPark").exists()
    assert Feature.objects.filter(properties__name="TestLake").exists()
    assert Feature.objects.filter(properties__name="TestProvince").exists()
    assert Feature.objects.filter(properties__name="TestReserve").exists()
    assert Feature.objects.filter(properties__name="TestRoad").exists()
    assert Feature.objects.filter(properties__name="TestRiver").exists()
    assert Feature.objects.filter(properties__name="TestCanal").exists()
    assert Feature.objects.filter(properties__name="TestRail").exists()
    assert Feature.objects.filter(properties__name="TestCountry1").exists()
    assert Feature.objects.filter(properties__name="TestCountry2").exists()


def test_seed_assigns_category_color_from_map(fixture_seed_data) -> None:
    """Every Feature's `properties.color` matches the CATEGORY_COLORS map for its category."""
    from features.management.commands.seed_features import CATEGORY_COLORS

    _run_seed()

    for feature in Feature.objects.all():
        category = feature.properties["category"]
        assert feature.properties["color"] == CATEGORY_COLORS[category], (
            f"Feature {feature.pk} ({feature.properties['name']}, category={category}) "
            f"has color {feature.properties['color']!r}, expected {CATEGORY_COLORS[category]!r}"
        )


def test_seed_creates_all_geometry_types(fixture_seed_data) -> None:
    """The bundle covers at least one of each GeoJSON geometry type used by the seeder."""
    _run_seed()

    with connection.cursor() as cursor:
        cursor.execute("SELECT ST_GeometryType(geometry) FROM features_feature")
        geometry_type_rows = cursor.fetchall()

    geometry_types_in_seed = {row[0] for row in geometry_type_rows}

    expected_geometry_types = {
        "ST_Point",
        "ST_LineString",
        "ST_Polygon",
        "ST_MultiPolygon",
        "ST_GeometryCollection",
    }
    assert expected_geometry_types.issubset(geometry_types_in_seed), (
        f"Missing geometry types: {expected_geometry_types - geometry_types_in_seed}"
    )


def test_seed_exactly_three_properties(fixture_seed_data) -> None:
    """Every seeded Feature has exactly the three properties name, color, category."""
    _run_seed()

    property_key_counts: Counter[int] = Counter()
    for feature in Feature.objects.all():
        property_key_counts[len(feature.properties)] += 1
        assert set(feature.properties.keys()) == {"name", "color", "category"}, (
            f"Feature {feature.pk} has unexpected properties: {sorted(feature.properties.keys())}"
        )

    assert property_key_counts[3] == Feature.objects.count()


def test_seed_is_idempotent(fixture_seed_data) -> None:
    """Running seed_features twice produces the same total count and the same curated features."""
    _run_seed()
    first_run_count = Feature.objects.count()
    assert first_run_count == 12

    _run_seed()
    second_run_count = Feature.objects.count()
    assert second_run_count == first_run_count

    assert Feature.objects.filter(properties__name="TestCountry1").exists()
    assert Feature.objects.filter(properties__name="TestCountry2").exists()
