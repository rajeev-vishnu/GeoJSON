"""Tests for the bbox parser and apply_bbox() helper used by the API filter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import Point
from rest_framework.exceptions import ValidationError

from features.filters import apply_bbox, parse_bbox
from features.models import Feature

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from accounts.models import User


pytestmark = pytest.mark.django_db


def _point(longitude: float, latitude: float):
    """Build a 4326 Point geometry."""
    return Point(longitude, latitude, srid=4326)


def test_parse_bbox_accepts_valid_input() -> None:
    """A well-formed 'minx,miny,maxx,maxy' string returns the four floats in order."""
    assert parse_bbox("3.3,50.7,7.3,53.55") == (3.3, 50.7, 7.3, 53.55)


def test_parse_bbox_accepts_negative_coordinates() -> None:
    """Western and southern hemisphere coordinates parse correctly."""
    assert parse_bbox("-180.0,-90.0,180.0,90.0") == (-180.0, -90.0, 180.0, 90.0)


def test_parse_bbox_accepts_integer_floats() -> None:
    """Coordinates expressed as integer strings parse to floats."""
    assert parse_bbox("0,0,10,10") == (0.0, 0.0, 10.0, 10.0)


def test_parse_bbox_rejects_wrong_arity() -> None:
    """A string with fewer than 4 comma-separated values raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("1.0,2.0,3.0")


def test_parse_bbox_rejects_too_many_values() -> None:
    """A string with more than 4 comma-separated values raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("1.0,2.0,3.0,4.0,5.0")


def test_parse_bbox_rejects_non_numeric() -> None:
    """A non-numeric value raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("a,b,c,d")


def test_parse_bbox_rejects_longitude_out_of_range() -> None:
    """Minx or maxx outside [-180, 180] raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("200.0,0.0,210.0,10.0")


def test_parse_bbox_rejects_latitude_out_of_range() -> None:
    """Miny or maxy outside [-90, 90] raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("0.0,100.0,10.0,110.0")


def test_parse_bbox_rejects_swapped_longitude() -> None:
    """Minx > maxx raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("10.0,0.0,5.0,10.0")


def test_parse_bbox_rejects_swapped_latitude() -> None:
    """Miny > maxy raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("0.0,10.0,10.0,5.0")


def test_parse_bbox_rejects_empty_string() -> None:
    """An empty string raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("")


def test_parse_bbox_rejects_whitespace_only() -> None:
    """A whitespace-only string raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox(" , , , ")


def test_apply_bbox_returns_full_queryset_when_bbox_is_none(user: User) -> None:
    """When bbox is None, apply_bbox returns the queryset unchanged (no filter applied)."""
    Feature.objects.create(geometry=_point(5.0, 52.0), properties={"name": "Inside"}, created_by=user)
    Feature.objects.create(geometry=_point(-100.0, 40.0), properties={"name": "Outside"}, created_by=user)
    queryset: QuerySet[Feature] = Feature.objects.all()

    filtered_queryset = apply_bbox(queryset, raw_bbox=None)

    assert filtered_queryset.query == queryset.query
    assert filtered_queryset.count() == 2


def test_apply_bbox_filters_to_intersecting_features(user: User) -> None:
    """apply_bbox chains a filter(geometry__intersects=polygon) and keeps only inside features."""
    Feature.objects.create(geometry=_point(5.0, 52.0), properties={"name": "Inside"}, created_by=user)
    Feature.objects.create(geometry=_point(-100.0, 40.0), properties={"name": "Outside"}, created_by=user)

    filtered_queryset = apply_bbox(Feature.objects.all(), raw_bbox="0,45,10,55")

    assert filtered_queryset.count() == 1
    assert filtered_queryset.first().properties["name"] == "Inside"


def test_apply_bbox_returns_empty_when_no_intersections(user: User) -> None:
    """A bbox disjoint from all features returns an empty queryset."""
    Feature.objects.create(geometry=_point(5.0, 52.0), properties={"name": "Amsterdam"}, created_by=user)

    filtered_queryset = apply_bbox(Feature.objects.all(), raw_bbox="-180,-90,-100,-80")

    assert filtered_queryset.count() == 0


def test_apply_bbox_propagates_validation_error(user: User) -> None:
    """An invalid bbox string propagates DRF's ValidationError from parse_bbox()."""
    with pytest.raises(ValidationError):
        apply_bbox(Feature.objects.all(), raw_bbox="not-a-bbox")
