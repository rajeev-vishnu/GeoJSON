"""Tests for the bbox parser used by the seed command and the API filter."""

from __future__ import annotations

import pytest
from rest_framework.exceptions import ValidationError

from features.filters import parse_bbox

pytestmark = pytest.mark.django_db


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
