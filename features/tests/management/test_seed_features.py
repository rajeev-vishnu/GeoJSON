"""Tests for the seed_features management command: idempotency, curated rows, properties shape."""

from __future__ import annotations

from collections import Counter
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from accounts.models import User
from features.models import Feature

pytestmark = pytest.mark.django_db


def _run_seed(*args: str) -> None:
    """Run `python manage.py seed_features <args>` against the test database.

    Captures stdout to a StringIO so the tests can stay quiet; the
    command's text output is not under test here.
    """
    call_command("seed_features", *args, stdout=StringIO())


def test_seed_creates_all_geometry_types() -> None:
    """Running seed_features with the default flags produces at least one Feature of each GeoJSON geometry type."""
    _run_seed("--count=1000", "--seed=42")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ST_GeometryType(geometry) FROM features_feature",
        )
        geometry_type_rows = cursor.fetchall()

    geometry_types_in_seed = {row[0] for row in geometry_type_rows}

    expected_geometry_types = {
        "ST_Point",
        "ST_MultiPoint",
        "ST_LineString",
        "ST_MultiLineString",
        "ST_Polygon",
        "ST_MultiPolygon",
        "ST_GeometryCollection",
    }

    assert expected_geometry_types.issubset(geometry_types_in_seed), (
        f"Missing geometry types: {expected_geometry_types - geometry_types_in_seed}"
    )


def test_seed_curated_outline() -> None:
    """The curated 'Netherlands' MultiPolygon and the 'Caribbean Netherlands' GeometryCollection are present."""
    _run_seed("--count=1000", "--seed=42")

    netherlands_feature = Feature.objects.filter(properties__name="Netherlands").get()
    caribbean_feature = Feature.objects.filter(properties__name="Caribbean Netherlands").get()

    assert netherlands_feature.properties["name"] == "Netherlands"
    assert netherlands_feature.properties["category"] == "country"
    assert netherlands_feature.properties["color"] == "#21468B"
    assert netherlands_feature.geometry.geom_type == "MultiPolygon"

    assert caribbean_feature.properties["name"] == "Caribbean Netherlands"
    assert caribbean_feature.properties["category"] == "country"
    assert caribbean_feature.properties["color"] == "#21468B"
    assert caribbean_feature.geometry.geom_type == "GeometryCollection"


def test_seed_exactly_three_properties() -> None:
    """Every seeded Feature has exactly the three properties name, color, category — no extras, no missing keys."""
    _run_seed("--count=1000", "--seed=42")

    property_key_counts: Counter[str] = Counter()
    for feature in Feature.objects.all():
        property_key_counts[len(feature.properties)] += 1
        assert set(feature.properties.keys()) == {"name", "color", "category"}, (
            f"Feature {feature.pk} has unexpected properties: {sorted(feature.properties.keys())}"
        )

    assert property_key_counts[3] == Feature.objects.count()


def test_seed_is_idempotent() -> None:
    """Running seed_features twice with the same --seed keeps the total count and the curated outline."""
    _run_seed("--count=1000", "--seed=42")
    first_run_count = Feature.objects.count()
    assert first_run_count == 1002

    _run_seed("--count=1000", "--seed=42")
    second_run_count = Feature.objects.count()
    assert second_run_count == first_run_count

    assert Feature.objects.filter(properties__name="Netherlands").exists()
    assert Feature.objects.filter(properties__name="Caribbean Netherlands").exists()


def test_seed_keep_preserves_users() -> None:
    """Running seed_features with --keep does not delete any accounts_user rows."""
    User.objects.create_user(email="alice@example.com", password="correct-horse-battery-staple")
    User.objects.create_user(email="bob@example.com", password="correct-horse-battery-staple")
    user_emails_before = sorted(User.objects.values_list("email", flat=True))

    _run_seed("--count=1000", "--seed=42", "--keep")

    user_emails_after = sorted(User.objects.values_list("email", flat=True))

    assert user_emails_after == user_emails_before
