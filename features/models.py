"""Feature model with PostGIS geometry, open properties, and indexes."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.gis.db.models import GeometryField
from django.contrib.postgres.indexes import BTreeIndex, GistIndex
from django.db import models


class Feature(models.Model):
    """A single geographic feature with open properties.

    Stores any of the 7 standard GeoJSON geometry types (Point,
    MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon,
    GeometryCollection) in WGS84 (SRID 4326). The `properties`
    JSONField is intentionally open — see the Feature Data Model spec
    §2 for the rationale.

    The trigram GIN index on `properties->>'name'` is intentionally
    not in `Meta.indexes`; it is created by the initial migration via
    `RunSQL` because Django 5.1's `GinIndex(OpClass(F(...)))` renders
    invalid SQL (tickets #35262, #35311, #35902).
    """

    class Category(models.TextChoices):
        """Closed enum of category values used by seed and frontend dropdown.

        Values are lowercase snake_case on the wire ("city", "town",
        "road", "river", "canal", "rail", "park", "lake", "province",
        "nature_reserve", "country") and Title-Case for human-readable
        labels.

        The enum is a Python *convention* — it is NOT a database
        constraint, NOT a check on `properties.category`, and NOT a
        server-side validator. The frontend uses it to populate
        category chips via `/api/categories/`.
        """

        CITY = "city", "City"
        TOWN = "town", "Town"
        ROAD = "road", "Road"
        RIVER = "river", "River"
        CANAL = "canal", "Canal"
        RAIL = "rail", "Rail"
        PARK = "park", "Park"
        LAKE = "lake", "Lake"
        PROVINCE = "province", "Province"
        NATURE_RESERVE = "nature_reserve", "Nature reserve"
        COUNTRY = "country", "Country"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geometry = GeometryField(srid=4326, spatial_index=False)
    properties = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="features",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Indexes for bbox filter and ordering.

        The trigram GIN index for substring search is not in this
        list — see the class docstring for why it is created via
        `RunSQL` in the initial migration.
        """

        indexes = [
            GistIndex(fields=["geometry"]),
            BTreeIndex(fields=["updated_at", "id"]),
            BTreeIndex(fields=["created_at", "id"]),
        ]
