"""Pytest fixtures shared by every features test module.

Defines:
- `auth_client` — a DRF `APIClient` with a valid JWT for the `user`.
- `make_feature` — a factory creating `Feature` rows with sensible defaults.
- `world_features` — a small fixture set spread across the world, for the
  `test_bbox_filter.py::test_world_fixture_filter` test.
- `netherlands_features` — a small fixture set spread across the
  Netherlands default bbox, for the
  `test_bbox_filter.py::test_netherlands_fixture_filter` test.

The `user` and `other_user` fixtures are defined in the **root
`conftest.py`** (not here) so they auto-discover for every test module
across the repo. Re-defining them in this file would shadow the root
fixture and break tests that compare two users.
"""

from __future__ import annotations

import pytest
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from features.models import Feature


@pytest.fixture
def make_auth_client(user):
    """Return a factory that builds an `APIClient` authenticated as the given user.

    The default is the `user` fixture; pass another user fixture (e.g.
    `other_user`) to authenticate as them.
    """

    def _factory(authenticated_user=None):
        resolved_user = authenticated_user if authenticated_user is not None else user
        refresh_token = RefreshToken.for_user(resolved_user)
        access_token = str(refresh_token.access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return client

    return _factory


@pytest.fixture
def make_feature(user):
    """Return a factory that creates `Feature` rows with sensible defaults.

    Defaults:
    - `geometry`: a `Point(5.0, 52.0)` (inside the Netherlands bbox).
    - `properties`: `{"name": "Foo", "color": "#ff0000", "category": "city"}`.
    - `created_by`: the `user` fixture.

    Override via keyword arguments:
    - `make_feature(geometry=GEOSGeometry("LINESTRING (...)", srid=4326))`
    - `make_feature(properties={"name": "Bar"})`
    - `make_feature(created_by=other_user)`
    """
    default_properties = {"name": "Foo", "color": "#ff0000", "category": "city"}

    def _factory(*, geometry=None, properties=None, created_by=None):
        resolved_geometry = geometry if geometry is not None else Point(5.0, 52.0, srid=4326)
        resolved_properties = properties if properties is not None else dict(default_properties)
        resolved_creator = created_by if created_by is not None else user
        return Feature.objects.create(
            geometry=resolved_geometry,
            properties=resolved_properties,
            created_by=resolved_creator,
        )

    return _factory


@pytest.fixture
def world_features(user):
    """Return a small feature set spread across the world for bbox filter tests."""
    return Feature.objects.bulk_create(
        [
            Feature(
                geometry=Point(139.6917, 35.6895, srid=4326),
                properties={"name": "Tokyo"},
                created_by=user,
            ),
            Feature(
                geometry=Point(-0.1276, 51.5074, srid=4326),
                properties={"name": "London"},
                created_by=user,
            ),
            Feature(
                geometry=Point(-74.0060, 40.7128, srid=4326),
                properties={"name": "New York"},
                created_by=user,
            ),
            Feature(
                geometry=Point(151.2093, -33.8688, srid=4326),
                properties={"name": "Sydney"},
                created_by=user,
            ),
            Feature(
                geometry=Point(18.4241, -33.9249, srid=4326),
                properties={"name": "Cape Town"},
                created_by=user,
            ),
            Feature(
                geometry=Point(-122.4194, 37.7749, srid=4326),
                properties={"name": "San Francisco"},
                created_by=user,
            ),
        ]
    )


@pytest.fixture
def netherlands_features(user):
    """Return a small feature set spread across the Netherlands default bbox.

    The default bbox `3.3,50.7,7.3,53.55` encloses the entire Netherlands.
    Used by `test_netherlands_fixture_filter` which also tests a small
    sub-bbox and a disjoint bbox.
    """
    return Feature.objects.bulk_create(
        [
            Feature(
                geometry=Point(4.8980, 52.3700, srid=4326),
                properties={"name": "Amsterdam"},
                created_by=user,
            ),
            Feature(
                geometry=Point(4.4777, 51.9244, srid=4326),
                properties={"name": "Rotterdam"},
                created_by=user,
            ),
            Feature(
                geometry=Point(5.1214, 52.0907, srid=4326),
                properties={"name": "Utrecht"},
                created_by=user,
            ),
            Feature(
                geometry=Point(5.6910, 50.8514, srid=4326),
                properties={"name": "Maastricht"},
                created_by=user,
            ),
        ]
    )
