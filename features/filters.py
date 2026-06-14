"""Bbox parsing and filtering for the seed command and the API filter.

The seed command's `--bbox` flag and the API's `?bbox=` filter both
call `parse_bbox()` to validate user input. The Feature API spec §4
defines the validation rules: exactly 4 comma-separated floats with
`minx <= maxx`, `miny <= maxy`, longitude in `[-180, 180]`, latitude
in `[-90, 90]`. Bad input raises DRF's `ValidationError` so the seed
command can re-wrap it as a `CommandError` and the API view can
return a 400 response without additional translation.

`apply_bbox()` is a thin wrapper that chains
`filter(geometry__intersects=Polygon)` onto a queryset when the raw
`?bbox=` query string is present, and returns the queryset
unchanged when the param is missing. The view uses it from
`FeatureViewSet.get_queryset()`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.gis.geos import Polygon
from rest_framework.exceptions import ValidationError

from features.models import Feature

if TYPE_CHECKING:
    from django.db.models import QuerySet


def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """Parse `'minx,miny,maxx,maxy'` into a 4-tuple of floats.

    Raises:
        ValidationError: if the input is empty, has the wrong arity,
            contains non-numeric values, has coordinates outside the
            WGS84 valid range, or has swapped min/max values.

    """
    parts = [item.strip() for item in raw.split(",")]
    if len(parts) != 4:
        raise ValidationError("bbox must have exactly 4 comma-separated values")
    try:
        min_x, min_y, max_x, max_y = (float(part) for part in parts)
    except ValueError as exc:
        raise ValidationError("bbox values must be numeric") from exc

    if not -180.0 <= min_x <= 180.0 or not -180.0 <= max_x <= 180.0:
        raise ValidationError("bbox longitude must be in [-180, 180]")
    if not -90.0 <= min_y <= 90.0 or not -90.0 <= max_y <= 90.0:
        raise ValidationError("bbox latitude must be in [-90, 90]")
    if min_x > max_x:
        raise ValidationError("bbox minx must be <= maxx")
    if min_y > max_y:
        raise ValidationError("bbox miny must be <= maxy")

    return min_x, min_y, max_x, max_y


def apply_bbox(queryset: QuerySet[Feature], raw_bbox: str | None) -> QuerySet[Feature]:
    """Chain a `geometry__intersects` filter onto `queryset` if `raw_bbox` is set.

    When `raw_bbox` is `None` (the `?bbox=` query param is absent), the
    queryset is returned unchanged. When it is set, it is parsed via
    `parse_bbox()` (which raises DRF's `ValidationError` on bad input —
    the view lets that propagate to a 400 response) and the queryset is
    filtered to features whose geometry intersects a `Polygon` built
    from the parsed bounds.
    """
    if raw_bbox is None:
        return queryset

    min_x, min_y, max_x, max_y = parse_bbox(raw_bbox)
    polygon = Polygon.from_bbox((min_x, min_y, max_x, max_y))
    return queryset.filter(geometry__intersects=polygon)
