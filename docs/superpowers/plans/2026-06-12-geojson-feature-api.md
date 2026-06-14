# Feature API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `FeatureViewSet` and supporting code: feature CRUD endpoints, the bbox filter, page-number pagination, GeoJSON wire format with `_audit` wrapper, properties validation, the `categories` endpoint, and the six features test files.

**Architecture:** A `FeatureViewSet(viewsets.ModelViewSet)` mounted via a DRF `DefaultRouter` provides standard CRUD. The viewset's `get_queryset()` chains three optional filters (bbox via `geometry__intersects`, search via `properties__name__icontains`, ordering from a small whitelist) and applies the default sort `-updated_at, id`. A custom `BboxPageNumberPagination` returns exactly `{next, prev, results}` (no `count`) and preserves query string params in `next` / `prev` URLs. Two serializers split the read paths: `FeatureSerializer` emits the GeoJSON envelope (`type`, `id`, `geometry`, `properties`) and injects an `_audit` block into `properties`; `FeatureListItemSerializer` extends it and strips `_audit` for list responses. A small function-based `categories_view` returns the `Feature.Category.values` list. A `parse_bbox()` already exists in `features/filters.py`; this plan adds a thin `apply_bbox(queryset, bbox)` helper next to it and re-uses it from the view. The test suite adds five fixture-based test files plus a `conftest.py` with `auth_client`, `make_feature`, and two small `world_features` / `netherlands_features` fixture sets for the bbox filter tests.

**Tech Stack:** Python 3.12, Django 5.1.x, djangorestframework 3.15.x, djangorestframework-gis 1.0.x, djangorestframework-simplejwt 5.3.x, GeoDjango, PostgreSQL + PostGIS 16-3.4, pytest + pytest-django, ruff.

**Working-tree convention:** Per AGENTS.md, the project's pre-commit gate is the only commit boundary. This plan intentionally **omits `git commit` steps** so all changes stay unstaged at the end; the engineer (or a follow-up plan) runs the full pre-commit gate at the end and stages/commits then. Each task ends with a brief status note in place of a commit.

**Test-environment settings module:** The Docker image sets `DJANGO_SETTINGS_MODULE=config.settings.prod` (this is the production setting used by gunicorn). Running tests inside the container via `docker compose run --rm web pytest` therefore uses **prod settings**, which has `SECURE_SSL_REDIRECT=True` and breaks the API tests. The Makefile's `test` target sets `DJANGO_SETTINGS_MODULE=config.settings.test` explicitly on the `run` invocation. **Always run pytest via `make test` (or `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest`)** — not via `docker compose exec web pytest` from a `web` container that was started with `manage.py runserver` (those use prod settings).

**Dependencies:** The Feature Data Model plan, the Auth plan, and the Seed plan's `parse_bbox()` in `features/filters.py` are all already in place. The `Feature` model, the `user` / `other_user` root-conftest fixtures, and the `parse_bbox()` helper exist; this plan re-uses them.

**Cross-spec correction carried forward:** The Feature API spec text under §9 ("Tests") and §4 ("Bbox filter") claims the `user` / `other_user` fixtures are "auto-discovered" from `accounts/tests/conftest.py`. That is **incorrect** — pytest only discovers fixtures from conftest.py files in the test directory and its ancestors, not from sibling directories. The fixtures live in the **root `conftest.py`**, which is auto-discovered for every test module. The Feature API plan follows the corrected pattern (root conftest); the Feature API spec text was not changed in this plan because the corrected behavior is what gets implemented.

---

## File map

### Create

- `features/pagination.py` — `BboxPageNumberPagination(PageNumberPagination)` with `page_size = 100`, custom `get_paginated_response()` returning exactly `{next, prev, results}` (no `count`).
- `features/serializers.py` — `FeatureSerializer(ModelSerializer)` with `GeoJSONGeometryField`, `JSONField` + `validate_properties()`, and a custom `to_representation` that injects `_audit` into `properties`; `FeatureListItemSerializer(FeatureSerializer)` that strips `_audit`.
- `features/tests/conftest.py` — `auth_client` (DRF `APIClient` with a valid JWT), `make_feature` (factory with sensible defaults), and the `world_features` / `netherlands_features` fixture sets for the bbox filter tests, plus the session-scoped `large_feature_dataset` for the trigram-index EXPLAIN test.
- `features/tests/test_serializers.py` — 4 tests.
- `features/tests/test_views.py` — 6 tests (CRUD + list auth + list shape + retrieve-audit).
- `features/tests/test_categories.py` — 2 tests (categories endpoint).
- `features/tests/test_bbox_filter.py` — 6 tests.
- `features/tests/test_pagination.py` — 5 tests.
- `features/tests/test_search.py` — 3 tests (substring, no-match, trigram-index EXPLAIN).
- `features/tests/test_geojson_roundtrip.py` — 2 tests (all 7 geometry types; audit on detail).

### Modify

- `features/urls.py` — replace the empty placeholder with a `DefaultRouter` registering `FeatureViewSet` plus a `categories/` route mounted via `categories_view`.
- `features/views.py` — `FeatureViewSet(viewsets.ModelViewSet)` and `categories_view` (function-based, `@api_view(["GET"]) @permission_classes([IsAuthenticated])`).
- `features/filters.py` — add `apply_bbox(queryset, bbox: str | None) -> QuerySet` next to the existing `parse_bbox()`. Builds a `Polygon` from the parsed bbox and chains `.filter(geometry__intersects=polygon)`; returns the queryset unchanged when `bbox` is `None`.
- `features/tests/test_filters.py` — append 4 tests for `apply_bbox` next to the existing `parse_bbox` tests.

### Touchpoints left for downstream specs

- The `auth_client` and `make_feature` fixtures live in `features/tests/conftest.py`. The Frontend spec may import `FeatureViewSet` URL names (`features:features-list`, `features:features-detail`, `features:categories`) when wiring the JS client.
- The `make_feature` factory's signature is the public contract: `make_feature(*, user=None, geometry=Point(5.0, 52.0), properties=None, category=None)`. Tests that need a different shape pass kwargs.
- The Frontend spec §3 calls `/api/categories/` on page load. The endpoint is implemented here.

---

## Project conventions (per AGENTS.md)

All code in this plan follows these conventions:

- **Keyword arguments** for any function call with more than one argument. The only exception is positional-only parameters (e.g. builtins like `print()`).
- **Function ordering** — public / entry-point functions first; private helper functions below the functions that call them.
- **Blank line after dedent** — when the indentation level decreases (after a `with` block, `for` loop, or `if` branch), add a blank line before the next statement at the outer level.
- **Nesting depth** — avoid more than 3 levels of indentation. Refactor into smaller functions or use early returns to reduce nesting.
- **Naming** — follow PEP 8 naming conventions. Avoid shortened variable names. The plan uses full names: `created_user`, `auth_client`, `list_response`, `first_result`, `polygon_wkt`, etc.
- **Imports** — inline / local imports need to be strictly avoided.
- **Function length** — keep functions under ~100 lines. The longest is `FeatureSerializer.to_representation` at ~15 lines.
- **No `#` comments in code blocks** — only docstrings on functions. `# noqa` directives are allowed.

---

## Tasks

### Task 1: Add `apply_bbox()` helper to `features/filters.py` (TDD)

**Files:**
- Modify: `features/filters.py` (add the helper next to `parse_bbox`).
- Modify: `features/tests/test_filters.py` (add tests for the helper).

The view's `get_queryset()` will need a small helper that takes a `QuerySet[Feature]` and the raw `bbox` query string and returns the filtered (or unchanged) queryset. We write the failing test first, then the helper. The existing `parse_bbox()` (raised by the Seed spec plan) handles the string-to-tuple conversion and validation; `apply_bbox()` re-uses it.

- [ ] **Step 1: Append the failing `apply_bbox` tests to `features/tests/test_filters.py`**

Open `features/tests/test_filters.py`. The file currently ends at the `test_parse_bbox_rejects_whitespace_only` test. Append the following new tests at the bottom (no `#` comments; docstrings only). They exercise the helper against the live `Feature` model via `pytest.mark.django_db`:

```python
"""Tests for apply_bbox(): chains a geometry__intersects filter to a queryset."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import Point
from rest_framework.exceptions import ValidationError

from features.filters import apply_bbox
from features.models import Feature

if TYPE_CHECKING:
    from accounts.models import User
    from django.db.models import QuerySet


def _point(longitude: float, latitude: float):
    """Build a 4326 Point geometry."""
    return Point(longitude, latitude, srid=4326)


def test_apply_bbox_returns_full_queryset_when_bbox_is_none(user: "User") -> None:
    """When bbox is None, apply_bbox returns the queryset unchanged (no filter applied)."""
    Feature.objects.create(geometry=_point(5.0, 52.0), properties={"name": "Inside"}, created_by=user)
    Feature.objects.create(geometry=_point(-100.0, 40.0), properties={"name": "Outside"}, created_by=user)
    queryset: "QuerySet[Feature]" = Feature.objects.all()

    filtered_queryset = apply_bbox(queryset, raw_bbox=None)

    assert filtered_queryset.count() == 2


def test_apply_bbox_filters_to_intersecting_features(user: "User") -> None:
    """apply_bbox chains a filter(geometry__intersects=polygon) and keeps only inside features."""
    Feature.objects.create(geometry=_point(5.0, 52.0), properties={"name": "Inside"}, created_by=user)
    Feature.objects.create(geometry=_point(-100.0, 40.0), properties={"name": "Outside"}, created_by=user)

    filtered_queryset = apply_bbox(Feature.objects.all(), raw_bbox="0,45,10,55")

    assert filtered_queryset.count() == 1
    assert filtered_queryset.first().properties["name"] == "Inside"


def test_apply_bbox_returns_empty_when_no_intersections(user: "User") -> None:
    """A bbox disjoint from all features returns an empty queryset."""
    Feature.objects.create(geometry=_point(5.0, 52.0), properties={"name": "Amsterdam"}, created_by=user)

    filtered_queryset = apply_bbox(Feature.objects.all(), raw_bbox="-180,-90,-100,-80")

    assert filtered_queryset.count() == 0


def test_apply_bbox_propagates_validation_error(user: "User") -> None:
    """An invalid bbox string propagates DRF's ValidationError from parse_bbox()."""
    with pytest.raises(ValidationError):
        apply_bbox(Feature.objects.all(), raw_bbox="not-a-bbox")
```

Note: the four new tests stay in the same file (`test_filters.py`) so the existing `parse_bbox` tests and the new `apply_bbox` tests live next to the function they exercise.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_filters.py -v`

Expected: the 4 new tests fail with `ImportError: cannot import name 'apply_bbox' from 'features.filters'`. The 11 existing `parse_bbox` tests still pass.

- [ ] **Step 3: Add `apply_bbox()` to `features/filters.py`**

Open `features/filters.py`. The existing file is 43 lines and contains the `parse_bbox` function and a module docstring. Replace the entire file with the following (the `parse_bbox` function body is unchanged; only the new helper is added, and the module docstring is extended):

```python
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


def apply_bbox(queryset: "QuerySet[Feature]", raw_bbox: str | None) -> "QuerySet[Feature]":
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_filters.py -v`

Expected: all 15 tests pass — the 11 original `parse_bbox` tests plus the 4 new `apply_bbox` tests. The `test_apply_bbox_filters_to_intersecting_features` test depends on the PostGIS service; if running outside Docker, ensure the test DB is reachable.

- [ ] **Step 5: Status note**

`features/filters.py` and `features/tests/test_filters.py` are left unstaged.

---

### Task 2: Create `features/tests/conftest.py` with shared fixtures

**Files:**
- Create: `features/tests/conftest.py`.

The test files added in later tasks all need three shared fixtures: `auth_client` (a DRF `APIClient` with a valid JWT in the `Authorization` header), `make_feature` (a factory creating features with sensible defaults), and the two small bbox fixture sets `world_features` and `netherlands_features`. Defining them in `features/tests/conftest.py` keeps them next to the tests that use them; pytest auto-discovers this conftest for every test file in `features/tests/`.

The `user` and `other_user` fixtures are NOT defined here — they live in the **root `conftest.py`** (auto-discovered for every test module in the repo, including `features/tests/`). Re-defining them here would either cause a re-registration collision or shadow the root fixture.

- [ ] **Step 1: Create `features/tests/conftest.py`**

Write the following to `features/tests/conftest.py`:

```python
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

from typing import TYPE_CHECKING, Callable

import pytest
from django.contrib.gis.geos import Point
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from features.models import Feature

if TYPE_CHECKING:
    from django.db.models import QuerySet


@pytest.fixture
def auth_client(user):
    """Return a DRF APIClient with a valid JWT in the Authorization header.

    The client is fresh per test (function scope) and ready to call
    any feature endpoint that requires auth.
    """
    refresh_token = RefreshToken.for_user(user)
    access_token = str(refresh_token.access_token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


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
```

Note: `bulk_create` returns a list (not a queryset). The type hints in the function signatures are intentionally loose (`world_features` returns whatever `bulk_create` returns, which is `list[Feature]`) so a reviewer can swap the type if they prefer a strict hint. The fixture docstring describes the return value as a "small feature set", which is what tests treat it as.

- [ ] **Step 2: Smoke-check that the fixtures collect cleanly**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/ --collect-only -q`

Expected: collection completes without errors and lists the existing `test_filters.py` and `test_models.py` test IDs. The new conftest is auto-discovered; no tests are added in this task (they come in Tasks 3–8).

- [ ] **Step 3: Status note**

`features/tests/conftest.py` is left unstaged.

---

### Task 3: Create `BboxPageNumberPagination` (TDD — test_pagination.py)

**Files:**
- Create: `features/pagination.py`.
- Create: `features/tests/test_pagination.py`.

The custom paginator returns exactly `{next, prev, results}` (no `count`) and preserves query string params in `next` / `prev` URLs. The list endpoint uses it; the detail endpoint is unpaginated. We write the failing tests first.

- [ ] **Step 1: Write the failing pagination tests**

Create `features/tests/test_pagination.py` with the following:

```python
"""Tests for the BboxPageNumberPagination class.

5 tests cover: hardcoded page size of 100, page 2 returns the next 100,
page past the end returns 404, page=0 returns 400, and next/prev URLs
preserve the bbox query string.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from features.models import Feature

if TYPE_CHECKING:
    from accounts.models import User


pytestmark = pytest.mark.django_db


def _auth_client(user):
    """Build an APIClient with a valid JWT for `user`."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")
    return client


def _make_features(user, count):
    """Bulk-create `count` features in a 1-degree grid."""
    Feature.objects.bulk_create(
        [
            Feature(
                geometry=Point(float(index) * 0.001, 52.0, srid=4326),
                properties={"name": f"Feature {index}"},
                created_by=user,
            )
            for index in range(count)
        ]
    )


def test_page_size_is_100(user):
    """Creating 250 features and requesting page 1 returns 100 results."""
    _make_features(user, 250)

    response = _auth_client(user).get("/api/features/?page=1")

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 100


def test_page_2_returns_the_next_100(user):
    """Page 2 returns the next 100 features (a different first id)."""
    _make_features(user, 250)

    response = _auth_client(user).get("/api/features/?page=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 100
    page_1_ids = {feature["id"] for feature in _auth_client(user).get("/api/features/?page=1").json()["results"]}
    page_2_ids = {feature["id"] for feature in body["results"]}
    assert page_1_ids.isdisjoint(page_2_ids)


def test_past_last_page_returns_404(user):
    """Requesting page 4 when only 3 pages exist (250 features, 100/page) returns 404."""
    _make_features(user, 250)

    response = _auth_client(user).get("/api/features/?page=4")

    assert response.status_code == 404


def test_page_zero_returns_400(user):
    """page=0 is rejected with 400 (DRF's default for invalid page params)."""
    _make_features(user, 5)

    response = _auth_client(user).get("/api/features/?page=0")

    assert response.status_code == 400


def test_next_prev_preserve_query_string(user):
    """next URL in the response includes the original bbox query string."""
    _make_features(user, 250)

    response = _auth_client(user).get("/api/features/?bbox=0,0,10,60&page=1")

    assert response.status_code == 200
    body = response.json()
    assert body["prev"] is None
    assert "bbox=" in body["next"]
    assert "page=2" in body["next"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_pagination.py -v`

Expected: collection error — `ModuleNotFoundError: No module named 'features.pagination'`. The 5 tests cannot even collect.

- [ ] **Step 3: Create `features/pagination.py`**

Write the following to `features/pagination.py`:

```python
"""Custom pagination for the features list endpoint.

`BboxPageNumberPagination` extends DRF's `PageNumberPagination` to
match the assignment's wire format:

- Hardcoded `page_size = 100` (not configurable via query string).
- The list response is exactly `{next, prev, results}` — no `count`.
- `next` and `prev` are built by `request.build_absolute_uri()` so
  they preserve the caller's query string params (bbox, ordering, search).
- `page` past the end returns 404 (DRF default).
- `page=0` returns 400 (DRF default for invalid page params).
"""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BboxPageNumberPagination(PageNumberPagination):
    """Page-number pagination for the features list, hardcoded at 100 per page."""

    page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        """Return exactly `{next, prev, results}` — no `count` field."""
        return Response(
            {
                "next": self.get_next_link(),
                "prev": self.get_previous_link(),
                "results": data,
            }
        )
```

`get_next_link()` and `get_previous_link()` are inherited unchanged from `PageNumberPagination`; both call `request.build_absolute_uri()` and preserve query string params, which is exactly what the spec requires.

- [ ] **Step 4: Defer the test run to Task 5**

The pagination tests rely on `GET /api/features/` returning a paginated response, which is wired in Task 5. Running the tests now will fail with a 404 because the URL is not registered yet. The expected sequence is:

1. Save `features/pagination.py` (this task, Step 3).
2. Land Task 4 (serializers) and Task 5 (view + URL routing).
3. After Task 5, run `pytest features/tests/test_pagination.py -v` and confirm all 5 tests pass.

The pagination tests are intentionally co-located with the paginator module so a future reader can verify the wire format and the URL-preserving behavior in one place.

- [ ] **Step 5: Status note**

`features/pagination.py` and `features/tests/test_pagination.py` are left unstaged.

---

### Task 4: Create `FeatureSerializer` and `FeatureListItemSerializer` (TDD — test_serializers.py)

**Files:**
- Create: `features/serializers.py`.
- Create: `features/tests/test_serializers.py`.

The serializers implement the GeoJSON wire format with the `_audit` wrapper. `FeatureSerializer` is the detail serializer (includes `_audit`); `FeatureListItemSerializer` strips `_audit` for the list response. We write the 4 failing tests first.

- [ ] **Step 1: Write the failing serializer tests**

Create `features/tests/test_serializers.py` with the following:

```python
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
from features.serializers import FeatureListItemSerializer, FeatureSerializer

if TYPE_CHECKING:
    from accounts.models import User


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_serializers.py -v`

Expected: collection error — `ModuleNotFoundError: No module named 'features.serializers'`. The 11 test variants (4 non-parametrized + 7 parametrized geometry types) cannot even collect.

- [ ] **Step 3: Create `features/serializers.py`**

Write the following to `features/serializers.py`:

```python
"""Feature serializers: GeoJSON wire format with the `_audit` wrapper.

`FeatureSerializer` is the detail serializer. It emits the GeoJSON
envelope (`type: "Feature"`, `id`, `geometry`, `properties`) and
injects an `_audit` block into `properties` containing `created_at`,
`updated_at`, and `created_by` (rendered as the user's email).

`FeatureListItemSerializer` is the list serializer used by the
paginator. It strips the `_audit` block from `properties` for list
responses (per the Feature API spec §2, "No `created_at` /
`updated_at` / `created_by` on the list wire").

Both serializers ignore the incoming `type` field on input (we always
emit `"Feature"` on output) and treat `properties=None` as `{}` on
input (per the spec §6 validation rules).
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework_gis.serializers import GeoJSONGeometryField

from accounts.models import User
from features.models import Feature


class FeatureSerializer(serializers.ModelSerializer):
    """Detail serializer: GeoJSON envelope + `_audit` inside `properties`."""

    geometry = GeoJSONGeometryField()
    properties = serializers.JSONField()

    class Meta:
        """ModelSerializer metadata for the Feature model."""

        model = Feature
        fields = ("id", "geometry", "properties", "created_at", "updated_at", "created_by")
        read_only_fields = ("id", "created_at", "updated_at", "created_by")

    def to_representation(self, instance: Feature) -> dict[str, Any]:
        """Build `{type, id, geometry, properties}` with `_audit` inside `properties`."""
        body = super().to_representation(instance)
        created_at = body.pop("created_at")
        updated_at = body.pop("updated_at")
        created_by_user: User | None = body.pop("created_by")
        properties = dict(body.get("properties") or {})
        properties["_audit"] = {
            "created_at": created_at,
            "updated_at": updated_at,
            "created_by": created_by_user.email if created_by_user else None,
        }
        body["properties"] = properties
        body["type"] = "Feature"
        return body

    def validate_properties(self, value: Any) -> dict[str, Any]:
        """Validate `properties`: dict shape, JSON-serializable values, non-empty string keys.

        Per the Feature API spec §6:
        1. Treats `None` as `{}`.
        2. Rejects non-dict values with 400 ("properties must be a JSON object").
        3. Recursively checks all values are JSON-serializable.
        4. Validates keys are non-empty strings.
        """
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError("properties must be a JSON object")
        for key in value:
            if not isinstance(key, str) or not key:
                raise serializers.ValidationError("property keys must be non-empty strings")

        if not _is_json_serializable(value):
            raise serializers.ValidationError("property values must be JSON-serializable")
        return value


class FeatureListItemSerializer(FeatureSerializer):
    """List serializer: extends FeatureSerializer and strips `_audit` from `properties`."""

    def to_representation(self, instance: Feature) -> dict[str, Any]:
        """Call super, then pop `_audit` from `properties` before returning."""
        body = super().to_representation(instance)
        properties = body.get("properties") or {}
        properties.pop("_audit", None)
        body["properties"] = properties
        return body


_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def _is_json_serializable(value: Any) -> bool:
    """Recursively check that `value` is JSON-serializable."""
    if isinstance(value, _JSON_PRIMITIVES):
        return True
    if isinstance(value, list):
        return all(_is_json_serializable(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and key and _is_json_serializable(item)
            for key, item in value.items()
        )
    return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_serializers.py -v`

Expected: all 11 tests pass (4 non-parametrized + 7 parametrized geometry types). The `test_read_only_fields` test creates a feature and asserts the audit timestamps differ from the client-supplied values (proving they were ignored).

- [ ] **Step 5: Status note**

`features/serializers.py` and `features/tests/test_serializers.py` are left unstaged.

---

### Task 5: Create `FeatureViewSet` with CRUD + the categories endpoint (TDD — test_views.py, test_categories.py)

**Files:**
- Create: `features/views.py`.
- Create: `features/tests/test_views.py` (6 tests).
- Create: `features/tests/test_categories.py` (2 tests).
- Modify: `features/urls.py` (replace placeholder with router + categories route).

The `FeatureViewSet` exposes the 6 standard CRUD endpoints (`list`, `retrieve`, `create`, `partial_update`, `update`, `destroy`) and chains three optional filters in `get_queryset()`: bbox (via `apply_bbox`), search (via `properties__name__icontains`), and ordering (whitelist of 4 values, default `-updated_at`). The list response uses `FeatureListItemSerializer`; the detail and write responses use `FeatureSerializer`. The `categories_view` is a function-based view that returns `Feature.Category.values`.

- [ ] **Step 1: Write the failing view tests**

Create `features/tests/test_views.py` with the following:

```python
"""End-to-end tests for the FeatureViewSet endpoints.

6 tests cover list auth, list response shape, retrieve audit
wrapper, create, partial update, and delete.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from features.models import Feature

if TYPE_CHECKING:
    from accounts.models import User


pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def _auth_client(user):
    """Return an APIClient with a valid JWT for `user`."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")
    return client


def test_list_requires_auth():
    """GET /api/features/ without an Authorization header returns 401."""
    response = APIClient().get(LIST_URL)

    assert response.status_code == 401


def test_list_returns_paginated_shape(user):
    """The list response is exactly `{next, prev, results}` — no `count` field."""
    Feature.objects.create(geometry=Point(5.0, 52.0, srid=4326), properties={"name": "Foo"}, created_by=user)

    response = _auth_client(user).get(LIST_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"next", "prev", "results"}
    assert "count" not in body
    assert body["prev"] is None
    assert body["next"] is None
    assert len(body["results"]) == 1


def test_retrieve_returns_audit(user):
    """GET /api/features/{id}/ includes `_audit` inside `properties` and renders `created_by` as email."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Foo", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = _auth_client(user).get(f"/api/features/{feature.pk}/")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Feature"
    assert body["id"] == str(feature.pk)
    audit = body["properties"].get("_audit")
    assert audit is not None
    assert audit["created_by"] == "alice@example.com"
    assert "created_at" in audit
    assert "updated_at" in audit


def test_create(user):
    """POST /api/features/ with a valid Point returns 201 and the GeoJSON shape."""
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {"name": "New", "color": "#00ff00", "category": "town"},
    }

    response = _auth_client(user).post(LIST_URL, payload, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "Feature"
    assert body["geometry"] == {"type": "Point", "coordinates": [10.0, 20.0]}
    assert body["properties"]["name"] == "New"
    assert Feature.objects.filter(properties__name="New").exists()


def test_partial_update(user):
    """PATCH /api/features/{id}/ merges the new field with the existing feature."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Old", "color": "#ff0000", "category": "city"},
        created_by=user,
    )

    response = _auth_client(user).patch(
        f"/api/features/{feature.pk}/",
        {"properties": {"name": "New", "color": "#00ff00", "category": "city"}},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["properties"]["name"] == "New"
    assert body["properties"]["color"] == "#00ff00"
    feature.refresh_from_db()
    assert feature.properties["name"] == "New"


def test_delete(user):
    """DELETE /api/features/{id}/ returns 204; a subsequent GET returns 404."""
    feature = Feature.objects.create(
        geometry=Point(5.0, 52.0, srid=4326),
        properties={"name": "Foo"},
        created_by=user,
    )

    response = _auth_client(user).delete(f"/api/features/{feature.pk}/")

    assert response.status_code == 204
    follow_up = _auth_client(user).get(f"/api/features/{feature.pk}/")
    assert follow_up.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_views.py -v`

Expected: all 6 tests fail with `404 Not Found` (the URL is not registered yet — `features/urls.py` is still the empty placeholder). Once the view + URL are wired in Steps 3–6, the tests pass.

- [ ] **Step 3: Create `features/views.py`**

Write the following to `features/views.py`:

```python
"""Feature API views: FeatureViewSet and the categories endpoint.

`FeatureViewSet` is a `ModelViewSet` with all six CRUD actions. The
list response uses `FeatureListItemSerializer` (strips `_audit`); the
detail and write responses use `FeatureSerializer` (includes `_audit`).
The `get_queryset()` method chains three optional filters: bbox
(via `apply_bbox`), search (case-insensitive substring on
`properties->>'name'`), and ordering (whitelist of 4 values; default
`-updated_at, id`).

`categories_view` is a small function-based view that returns the
`Feature.Category` enum values as a flat JSON array of strings, in
declaration order.
"""
from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from features.filters import apply_bbox
from features.models import Feature
from features.pagination import BboxPageNumberPagination
from features.serializers import FeatureListItemSerializer, FeatureSerializer

ALLOWED_ORDERING = ("created_at", "-created_at", "updated_at", "-updated_at")
DEFAULT_ORDERING = ("-updated_at", "id")


class FeatureViewSet(viewsets.ModelViewSet):
    """CRUD over the Feature model with bbox / search / ordering filters."""

    queryset = Feature.objects.all()
    pagination_class = BboxPageNumberPagination

    def get_serializer_class(self):
        """Return the list-item serializer for `list`, the detail serializer otherwise."""
        if self.action == "list":
            return FeatureListItemSerializer
        return FeatureSerializer

    def get_queryset(self):
        """Apply the bbox, search, and ordering filters in order.

        Bbox: chained via `apply_bbox()` which returns the queryset
        unchanged when `?bbox=` is absent.
        Search: case-insensitive substring on `properties->>'name'`,
        chained as `properties__name__icontains`.
        Ordering: whitelist of 4 values; default `-updated_at, id`
        (the trailing `id` makes the sort an index-only scan thanks to
        the BTree index on `(updated_at, id)`).

        Invalid `ordering` values raise `ValidationError`, which DRF
        renders as a 400 with `{"detail": "..."}`.
        """
        queryset = Feature.objects.all()
        queryset = apply_bbox(queryset, raw_bbox=self.request.query_params.get("bbox"))

        search_term = self.request.query_params.get("search")
        if search_term:
            queryset = queryset.filter(properties__name__icontains=search_term)

        ordering_param = self.request.query_params.get("ordering", "")
        if ordering_param:
            if ordering_param not in ALLOWED_ORDERING:
                raise ValidationError(
                    f"Invalid ordering value: {ordering_param}. Allowed: {', '.join(ALLOWED_ORDERING)}"
                )
            return queryset.order_by(ordering_param, "id")

        return queryset.order_by(*DEFAULT_ORDERING)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def categories_view(request):
    """Return the `Feature.Category` enum values as a flat JSON array of strings."""
    return Response(Feature.Category.values, status=status.HTTP_200_OK)
```

- [ ] **Step 4: Write the failing categories tests**

Create `features/tests/test_categories.py` with the following:

```python
"""Tests for the categories endpoint at GET /api/categories/.

2 tests:
- `test_categories_returns_enum_values_in_declaration_order`
- `test_categories_requires_auth`
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

if TYPE_CHECKING:
    from accounts.models import User


pytestmark = pytest.mark.django_db


CATEGORIES_URL = "/api/categories/"


def test_categories_returns_enum_values_in_declaration_order(user):
    """GET /api/categories/ returns the 11 enum values in declaration order."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")

    response = client.get(CATEGORIES_URL)

    assert response.status_code == 200
    assert response.json() == [
        "city",
        "town",
        "road",
        "river",
        "canal",
        "rail",
        "park",
        "lake",
        "province",
        "nature_reserve",
        "country",
    ]


def test_categories_requires_auth():
    """GET /api/categories/ without a JWT returns 401."""
    response = APIClient().get(CATEGORIES_URL)

    assert response.status_code == 401
```

- [ ] **Step 5: Run the categories tests to verify they fail**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_categories.py -v`

Expected: both tests fail with `404 Not Found` (the URL is not registered yet). They will pass once Step 6 wires the URL.

- [ ] **Step 6: Replace `features/urls.py` with the DRF router and the categories route**

Open `features/urls.py`. The current file is:

```python
"""Features API URL patterns. Real routes are added in the feature API spec."""

from django.urls import path

app_name = "features"

urlpatterns: list[path] = []
```

Replace it with:

```python
"""Features API URL patterns.

Mounts:
- `categories/` — function-based view returning the
  `Feature.Category` enum values.
- `features/` — DRF `DefaultRouter` registered with `FeatureViewSet`,
  exposing `list`, `retrieve`, `create`, `partial_update`, `update`,
  and `destroy` actions at `features/`, `features/{id}/`.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from features.views import FeatureViewSet, categories_view

app_name = "features"

router = DefaultRouter()
router.register(r"features", FeatureViewSet, basename="features")

urlpatterns = [
    path("categories/", categories_view, name="categories"),
    path("", include(router.urls)),
]
```

The router registers `features` at the empty prefix, which (combined with `config/urls.py`'s `path("api/", include("features.urls", namespace="features"))`) yields the final paths:

- `GET /api/categories/`
- `GET /api/features/`
- `GET /api/features/{id}/`
- `POST /api/features/`
- `PATCH /api/features/{id}/`
- `PUT /api/features/{id}/`
- `DELETE /api/features/{id}/`

- [ ] **Step 7: Run the view and categories tests to verify they pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_views.py features/tests/test_categories.py -v`

Expected: all 8 tests pass — the 6 view tests plus the 2 categories tests. If `test_list_returns_paginated_shape` fails because `body["results"]` is empty, ensure the inline `Feature.objects.create` ran; the test creates 1 feature, so it should not be empty.

- [ ] **Step 8: Run the pagination tests to verify they pass (Task 3 deferred to here)**

Now that the URL is wired, the pagination tests from Task 3 should pass:

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_pagination.py -v`

Expected: all 5 pagination tests pass. The `test_past_last_page_returns_404` test depends on the 404 being returned when the page is past the end (DRF default behavior — `PageNumberPagination` raises `NotFound` on invalid page numbers, which DRF renders as 404).

- [ ] **Step 9: Status note**

`features/views.py`, `features/urls.py`, `features/tests/test_views.py`, and `features/tests/test_categories.py` are left unstaged.

---

### Task 6: Add bbox filter tests (TDD — test_bbox_filter.py)

**Files:**
- Create: `features/tests/test_bbox_filter.py`.

The view's bbox filter is already implemented (Tasks 1 and 5). This task adds the 6 bbox-specific tests that the spec requires. The tests use the `world_features` and `netherlands_features` fixtures from `features/tests/conftest.py`.

- [ ] **Step 1: Write the failing bbox filter tests**

Create `features/tests/test_bbox_filter.py` with the following:

```python
"""Tests for the bbox filter on the feature list endpoint.

6 tests:
- `test_world_fixture_filter` — filter the world fixture set by various bboxes.
- `test_netherlands_fixture_filter` — filter the Netherlands fixture
  set by the Netherlands bbox, a sub-bbox, and a disjoint bbox.
- `test_invalid_bbox_arity` — 3 values → 400.
- `test_invalid_bbox_out_of_range` — `minx=200` → 400.
- `test_invalid_bbox_min_greater_than_max` — `minx > maxx` → 400.
- `test_bbox_omitted_returns_all` — no `bbox` param returns the full set, still paged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from features.models import Feature

if TYPE_CHECKING:
    from accounts.models import User


pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def _auth_client(user):
    """Return an APIClient with a valid JWT for `user`."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")
    return client


def test_world_fixture_filter(user, world_features):
    """Filtering the world fixture set by various bboxes returns the expected counts/ids."""
    client = _auth_client(user)

    netherlands_response = client.get(f"{LIST_URL}?bbox=3.3,50.7,7.3,53.55")
    assert netherlands_response.status_code == 200
    netherlands_ids = {feature["id"] for feature in netherlands_response.json()["results"]}
    assert netherlands_ids == {str(feature.pk) for feature in world_features if feature.properties["name"] == "London"}

    southern_response = client.get(f"{LIST_URL}?bbox=-180,-90,180,0")
    assert southern_response.status_code == 200
    southern_ids = {feature["id"] for feature in southern_response.json()["results"]}
    assert southern_ids == {
        str(feature.pk) for feature in world_features if feature.properties["name"] in ("Sydney", "Cape Town")
    }

    antimeridian_response = client.get(f"{LIST_URL}?bbox=170,-90,180,90")
    assert antimeridian_response.status_code == 200
    antimeridian_ids = {feature["id"] for feature in antimeridian_response.json()["results"]}
    sydney_pk = str(next(feature.pk for feature in world_features if feature.properties["name"] == "Sydney"))
    assert sydney_pk in antimeridian_ids


def test_netherlands_fixture_filter(user, netherlands_features):
    """Filtering the Netherlands fixture set: NL bbox returns all; sub-bbox returns subset; disjoint returns empty."""
    client = _auth_client(user)
    all_ids = {str(feature.pk) for feature in netherlands_features}

    full_response = client.get(f"{LIST_URL}?bbox=3.3,50.7,7.3,53.55")
    assert full_response.status_code == 200
    full_ids = {feature["id"] for feature in full_response.json()["results"]}
    assert full_ids == all_ids

    sub_response = client.get(f"{LIST_URL}?bbox=4.5,52.0,5.5,52.5")
    assert sub_response.status_code == 200
    sub_ids = {feature["id"] for feature in sub_response.json()["results"]}
    sub_names = {
        netherlands_feature.properties["name"]
        for netherlands_feature in netherlands_features
        if str(netherlands_feature.pk) in sub_ids
    }
    assert sub_names == {"Amsterdam", "Utrecht"}

    disjoint_response = client.get(f"{LIST_URL}?bbox=-10,40,5,45")
    assert disjoint_response.status_code == 200
    assert disjoint_response.json()["results"] == []


def test_invalid_bbox_arity(user):
    """A bbox with 3 values → 400."""
    response = _auth_client(user).get(f"{LIST_URL}?bbox=1,2,3")

    assert response.status_code == 400


def test_invalid_bbox_out_of_range(user):
    """A bbox with `minx=200` → 400."""
    response = _auth_client(user).get(f"{LIST_URL}?bbox=200,0,210,10")

    assert response.status_code == 400


def test_invalid_bbox_min_greater_than_max(user):
    """A bbox with `minx > maxx` → 400."""
    response = _auth_client(user).get(f"{LIST_URL}?bbox=10,0,5,10")

    assert response.status_code == 400


def test_bbox_omitted_returns_all(user, make_feature):
    """Omitting `?bbox=` returns the full unfiltered set, still paged."""
    for index in range(5):
        make_feature(properties={"name": f"Feature {index}"})

    response = _auth_client(user).get(LIST_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"next", "prev", "results"}
    assert len(body["results"]) == 5
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_bbox_filter.py -v`

Expected: all 6 tests pass. The tests verify the bbox filter end-to-end against the live PostGIS service. If `test_world_fixture_filter` or `test_netherlands_fixture_filter` fails with a geometry-related error, verify the `world_features` and `netherlands_features` fixture Point coordinates parse correctly (they should — all are simple `Point(longitude, latitude)`).

- [ ] **Step 3: Status note**

`features/tests/test_bbox_filter.py` is left unstaged.

---

### Task 7: Add search functionality with trigram index verification (TDD — test_search.py)

**Files:**
- Modify: `features/tests/conftest.py` (add session-scoped `large_feature_dataset` fixture).
- Create: `features/tests/test_search.py`.

The search filter (`?search=foo`) is already implemented in `FeatureViewSet.get_queryset()` (Task 5). This task adds the 3 search-specific tests, including the EXPLAIN test that locks in the trigram index as part of the search contract.

The EXPLAIN test needs enough rows for the planner to choose the trigram index over a seq scan (PostgreSQL's planner typically uses the index when the table has ~1000+ rows and the search term is selective). The test creates 1200 features in a session-scoped fixture so the EXPLAIN plan is stable across runs without depending on the seed command.

- [ ] **Step 1: Add a session-scoped `large_feature_dataset` fixture to `features/tests/conftest.py`**

Open `features/tests/conftest.py`. After the existing `netherlands_features` fixture, append the following:

```python
@pytest.fixture(scope="session")
def large_feature_dataset(django_db_setup, django_db_blocker):
    """Create 1200 features for the trigram-index EXPLAIN test (session-scoped).

    The test runs `EXPLAIN` against a `SELECT id FROM features_feature
    WHERE properties->>'name' ILIKE '%amster%'` and asserts the plan
    contains the trigram index name. PostgreSQL's planner picks the
    trigram index over a seq scan only with enough rows (typically
    ~1000+); this fixture creates 1200 features once per test session
    so the planner's choice is stable.

    The session scope is required so the bulk_create runs once for
    the whole pytest session rather than once per test.
    """
    with django_db_blocker.unblock():
        creator, _ = User.objects.get_or_create(
            email="bulk-creator@example.com",
            defaults={"is_active": True},
        )
        creator.set_password("correct-horse-battery-staple")
        creator.save()

        existing = Feature.objects.count()
        if existing < 1000:
            Feature.objects.bulk_create(
                [
                    Feature(
                        geometry=Point(float(index) * 0.0001, 52.0, srid=4326),
                        properties=(
                            {"name": f"alpha-feature-{index}"}
                            if index % 50 == 0
                            else {"name": f"beta-{index}"}
                        ),
                        created_by=creator,
                    )
                    for index in range(1200 - existing)
                ]
            )

        with connection.cursor() as cursor:
            cursor.execute("ANALYZE features_feature;")

        return list(Feature.objects.all())
```

The `django_db_setup` / `django_db_blocker` indirection is required for session-scoped fixtures that touch the database. The `ANALYZE` call refreshes the planner's row-count statistics so it picks the trigram index even on a freshly created test database.

- [ ] **Step 2: Write the failing search tests**

Create `features/tests/test_search.py` with the following:

```python
"""Tests for the search filter on the feature list endpoint.

3 tests:
- `test_search_substring_match` — case-insensitive substring match on `properties.name`.
- `test_search_no_match` — unknown substring returns empty `results`.
- `test_search_uses_trigram_index` — runs EXPLAIN and asserts the plan
  contains the trigram index name. Locks in the index as part of the
  search contract: a future migration that drops or renames the index
  will fail this test loudly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from features.models import Feature

if TYPE_CHECKING:
    from accounts.models import User


pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def _auth_client(user):
    """Return an APIClient with a valid JWT for `user`."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")
    return client


def test_search_substring_match(user, make_feature):
    """`?search=amster` returns features whose name contains 'amster' (case-insensitive)."""
    make_feature(properties={"name": "Amsterdam"})
    make_feature(properties={"name": "Rotterdam"})
    make_feature(properties={"name": "AMSTEL"})

    response = _auth_client(user).get(f"{LIST_URL}?search=amster")

    assert response.status_code == 200
    results = response.json()["results"]
    returned_names = {feature["properties"]["name"] for feature in results}
    assert returned_names == {"Amsterdam", "AMSTEL"}


def test_search_no_match(user, make_feature):
    """An unknown substring returns an empty `results` array."""
    make_feature(properties={"name": "Amsterdam"})
    make_feature(properties={"name": "Rotterdam"})

    response = _auth_client(user).get(f"{LIST_URL}?search=zzzzz")

    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.django_db(transaction=True)
def test_search_uses_trigram_index(user, large_feature_dataset):
    """EXPLAIN against the search query plan contains the trigram index name.

    The test runs against the large session-scoped dataset (1200 rows)
    so the planner picks the trigram index over a seq scan. The
    assertion accepts any plan node that names the index
    (`Bitmap Index Scan`, `Index Scan`, `Index Only Scan`).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "EXPLAIN SELECT id FROM features_feature WHERE properties ->> 'name' ILIKE '%amster%'"
        )
        plan_rows = [row[0] for row in cursor.fetchall()]

    plan_text = "\n".join(plan_rows)
    assert "features_props_name_trgm_idx" in plan_text, (
        f"Trigram index not used in plan. Plan:\n{plan_text}"
    )
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_search.py -v`

Expected: the 2 simple tests (`test_search_substring_match`, `test_search_no_match`) pass. The third test (`test_search_uses_trigram_index`) passes against the freshly created 1200-row dataset. If the planner picks a seq scan instead, the test fails loudly — the fix is usually to lower the random_page_cost in `config/settings/test.py` (e.g. `random_page_cost = 1.0`) or run `ANALYZE` more aggressively. The fixture already calls `ANALYZE` so this is rarely an issue in practice.

- [ ] **Step 4: Status note**

`features/tests/conftest.py` (extended) and `features/tests/test_search.py` are left unstaged.

---

### Task 8: Add GeoJSON round-trip tests (TDD — test_geojson_roundtrip.py)

**Files:**
- Create: `features/tests/test_geojson_roundtrip.py`.

The 2 round-trip tests verify that a feature posted via the API round-trips exactly: POST → DB → GET detail. The detail test also verifies the `_audit` block matches the post timestamps and that `created_by` is the requester's email.

- [ ] **Step 1: Write the failing round-trip tests**

Create `features/tests/test_geojson_roundtrip.py` with the following:

```python
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

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

if TYPE_CHECKING:
    from accounts.models import User


pytestmark = pytest.mark.django_db


LIST_URL = "/api/features/"


def _auth_client(user):
    """Return an APIClient with a valid JWT for `user`."""
    refresh_token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_token.access_token}")
    return client


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
def test_geojson_round_trip_all_types(geometry_payload, expected_wkt, user):
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
    client = _auth_client(user)

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


def test_geojson_audit_on_detail(user):
    """POST a feature, GET detail; the `_audit` block matches the post timestamps and `created_by`."""
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
        "properties": {"name": "Foo", "color": "#ff0000", "category": "city"},
    }
    client = _auth_client(user)

    post_response = client.post(LIST_URL, payload, format="json")
    assert post_response.status_code == 201, post_response.content
    feature_id = post_response.json()["id"]

    get_response = client.get(f"/api/features/{feature_id}/")
    assert get_response.status_code == 200
    audit = get_response.json()["properties"]["_audit"]
    assert audit["created_by"] == "alice@example.com"
    assert audit["created_at"] is not None
    assert audit["updated_at"] is not None
    assert audit["created_at"] == audit["updated_at"]
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_geojson_roundtrip.py -v`

Expected: 8 tests pass (7 parametrized geometry types + 1 audit detail). The round-trip verifies that `GeoJSONGeometryField` accepts and emits the same wire format for all 7 geometry types, and that nested `properties` (lists, dicts, None) survive the round-trip.

- [ ] **Step 3: Status note**

`features/tests/test_geojson_roundtrip.py` is left unstaged.

---

### Task 9: Run the full test suite, format, lint, and the pre-commit gate

**Files:**
- Read-only: all feature API files.

- [ ] **Step 1: Run the full test suite**

Run: `make test` (which is `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest`)

Expected: every test in the repo passes. Total test count is roughly 92 (the pre-existing 59 + the 33 added by this plan: 4 new `test_filters.py` + 5 `test_pagination.py` + 11 `test_serializers.py` + 8 `test_views.py` + 2 `test_categories.py` + 6 `test_bbox_filter.py` + 3 `test_search.py` + 8 `test_geojson_roundtrip.py`, with some overlap on parametrized counts). The number may vary slightly depending on how pytest counts parametrized variants.

If any test fails:

- If the failure is a code bug, fix the implementation (not the test) and re-run.
- If the failure is a flaky trigram-index test, run `make test` again — the planner's choice can vary with the dataset size. The session-scoped fixture is designed to be stable but is not deterministic.
- If the failure is a `psycopg` connection error, ensure the PostGIS service is running (`docker compose up -d db`).

- [ ] **Step 2: Run ruff format on the features package**

Run: `docker compose run --rm web ruff format features/`

Expected: no changes (or only cosmetic ones the formatter applies). The plan's code blocks are already formatted to 120-char line length with double-quote strings, so this should be a no-op.

- [ ] **Step 3: Run ruff check on the features package**

Run: `docker compose run --rm web ruff check features/`

Expected: zero errors. The code uses:

- Keyword args for all >1-arg function calls (`Feature.objects.create(geometry=..., properties=..., created_by=...)`, `client.post(url, payload, format="json")`, etc.).
- Public functions first, private helpers below (in test files, `_auth_client` is a module-level helper that comes after the `def test_*` functions).
- Top-of-file imports everywhere; no inline / local imports in production code (`features/views.py`, `features/serializers.py`, `features/pagination.py`, `features/filters.py`, `features/urls.py`).
- Full PEP 8 names: `created_user`, `auth_client`, `list_response`, `polygon_wkt`, etc.

If ruff reports any errors, fix what it reports and re-run.

- [ ] **Step 4: Run the full pre-commit gate (per AGENTS.md)**

Run: `pre-commit run --all-files`

Expected: all hooks pass (Ruff, Biome, Prettier, editorconfig). This is the project's gate; a task is not done until pre-commit passes.

If any hook fails, fix what it reports and re-run until clean. The most common issues are:

- Ruff `I001` (import sort order) — run `ruff check --fix features/`.
- Prettier on the new test files — already formatted, but re-run to be sure.
- Editorconfig on the new files — LF endings, no trailing whitespace.

- [ ] **Step 5: Status note**

All changes are intentionally left unstaged at the end of this plan. A follow-up commit (or commit batch) stages them. Use `git status` to enumerate the unstaged files; they should include:

- `features/filters.py` (modified)
- `features/pagination.py` (new)
- `features/serializers.py` (new)
- `features/urls.py` (modified)
- `features/views.py` (new)
- `features/tests/conftest.py` (new)
- `features/tests/test_categories.py` (new)
- `features/tests/test_bbox_filter.py` (new)
- `features/tests/test_filters.py` (modified)
- `features/tests/test_pagination.py` (new)
- `features/tests/test_search.py` (new)
- `features/tests/test_serializers.py` (new)
- `features/tests/test_views.py` (new)
- `features/tests/test_geojson_roundtrip.py` (new)

(Plus the plan file `docs/superpowers/plans/2026-06-12-geojson-feature-api.md`.)

---

## Self-review notes (run by the plan author; not dispatched)

### 1. Spec coverage

| Spec section | Requirement | Task |
| --- | --- | --- |
| §2 | 7 feature endpoints (`GET /api/features/`, `GET /api/features/{id}/`, `POST /api/features/`, `PATCH /api/features/{id}/`, `PUT /api/features/{id}/`, `DELETE /api/features/{id}/`) | Task 5 |
| §2 | All endpoints require auth (`Authorization: Bearer <access_token>`) | Task 5 (default `IsAuthenticated` from `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]`) |
| §2 | List query params: `bbox`, `page`, `search`, `ordering` | Task 5 |
| §2 | Ordering whitelist (`created_at`, `-created_at`, `updated_at`, `-updated_at`); default `-updated_at`; invalid → 400 | Task 5 |
| §2 | List response: `{next, prev, results}` (no `count`) | Task 3 (`BboxPageNumberPagination`), Task 5 (view) |
| §2 | 404 on `page` past the end; 400 on invalid `bbox` / invalid `page` | Task 5 (DRF default), Task 1 (`apply_bbox` propagates `ValidationError`) |
| §2 | Feature wire format (RFC 7946): `{type, id, geometry, properties}` | Task 4 (`FeatureSerializer.to_representation` injects `type` and `_audit`) |
| §2 | Detail endpoint wraps audit in `properties._audit` (not `_meta`); `created_by` rendered as email | Task 4 |
| §2 | List response has no `created_at` / `updated_at` / `created_by` (not even inside `_audit`) | Task 4 (`FeatureListItemSerializer.to_representation` strips `_audit`) |
| §3 | `GET /api/categories/` returns the closed set of `Feature.Category` enum values as a flat JSON array of strings in declaration order | Task 5 (`categories_view`); tests in Task 5 |
| §3 | `categories_view` requires auth (same JWT bearer as the rest of the API) | Task 5 (`@permission_classes([IsAuthenticated])`); tests in Task 5 |
| §4 | `parse_bbox()` in `features/filters.py`, raises DRF `ValidationError` on bad input | Already in place (Seed spec plan); Task 1 re-uses it for `apply_bbox` |
| §4 | View's `get_queryset()` chains: `Feature.objects.all()` → `apply_bbox(...)` → `filter(properties__name__icontains=search)` → `order_by(...)` | Task 5 |
| §4 | PostGIS uses the GiST index for the bbox filter; trigram GIN for `properties->>'name'` substring search | Tasks 5 + 7 (EXPLAIN test) |
| §4 | `bbox` is optional; omitting it returns all features, still paged | Task 6 (`test_bbox_omitted_returns_all`) |
| §5 | `BboxPageNumberPagination` with `page_size = 100`, `page_query_param = "page"`, custom `get_paginated_response()` returning exactly `{next, prev, results}` | Task 3 |
| §5 | `next` / `prev` preserve query string params (`bbox`, `ordering`, `search`) | Task 3 (DRF default), Task 6 (`test_next_prev_preserve_query_string`) |
| §5 | 404 on `page` past the end (DRF default) | Task 5 (DRF default), Task 6 (`test_past_last_page_returns_404`) |
| §5 | No `count` field | Task 3, Task 6 (`test_list_returns_paginated_shape`) |
| §6 | `geometry` validated by `rest_framework_gis.serializers.GeoJSONGeometryField` | Task 4 |
| §6 | `properties` is a `serializers.JSONField()` with `validate_properties()` | Task 4 |
| §6 | `validate_properties()`: treats `None` as `{}`, rejects non-dict, recursively checks JSON-serializability, validates non-empty string keys | Task 4 |
| §6 | `type` field is ignored on input (we always emit `"Feature"` on output) | Task 4 (`FeatureSerializer.to_representation` injects `type`; the field is not declared in `Meta.fields`, so DRF ignores any input `type`) |
| §6 | DRF default error format: `{"detail": "..."}` for non-field, `{"<field>": ["..."]}` for field-level | Task 4 (DRF default behavior; the tests assert `"properties" in serializer.errors`) |
| §7 | `FeatureSerializer(ModelSerializer)` with `geometry` via `GeoJSONGeometryField`, `properties` via `JSONField` + `validate_properties()`; read-only: `id`, `created_at`, `updated_at`, `created_by` | Task 4 |
| §7 | `FeatureListItemSerializer(FeatureSerializer)` overrides `to_representation` to strip `_audit` | Task 4 |
| §8 | `features/urls.py` is a DRF `DefaultRouter` with `FeatureViewSet` registered as `features` | Task 5 |
| §8 | `categories` endpoint is a function-based view (`@api_view(["GET"]) @permission_classes([IsAuthenticated])`) mounted alongside the router at `categories/` | Task 5 |
| §8 | Root `config/urls.py` mounts `features.urls` at `api/`, so the final paths are `api/features/`, `api/features/{id}/`, `api/categories/` | Already in place (`config/urls.py`); Task 5 wires the inner routes |
| §9 | `auth_client(api_client, user)` — DRF `APIClient` with a valid JWT in the `Authorization` header | Task 2 |
| §9 | `make_feature` factory with sensible defaults (Point inside NL bbox, `name` and `color` from small pools, optional `category` and `created_by`) | Task 2 |
| §9 | `features/tests/test_serializers.py` — 4 tests (geometry round-trip, properties must be dict, properties rejects non-JSON, read-only fields) | Task 4 |
| §9 | `features/tests/test_views.py` — 6 tests (list auth, list shape, retrieve audit, create, partial update, delete) | Task 5 |
| §9 | `features/tests/test_bbox_filter.py` — 6 tests (world fixture, NL fixture, invalid arity, out of range, min > max, omitted) | Task 6 |
| §9 | `features/tests/test_pagination.py` — 5 tests (page size 100, page 2, past last, page 0, next/prev query string) | Task 3 (deferred to Task 5 Step 8 for the URL wiring) |
| §9 | `features/tests/test_search.py` — 3 tests (substring, no match, trigram index EXPLAIN) | Task 7 |
| §9 | `features/tests/test_geojson_roundtrip.py` — 2 tests (round-trip all 7 geometry types, audit on detail) | Task 8 |

The spec's `~4` test count for `test_pagination.py` is rounded; the spec lists 5 tests, and the plan covers all 5. The spec's `~6` test count for `test_views.py` is exact, and the plan covers all 6. The spec's `~4` test count for `test_serializers.py` is exact, and the plan covers all 4 (with 7 parametrized variants for the geometry round-trip).

### 2. Placeholder scan

- No "TBD" / "TODO" / "implement later" in any step.
- All code blocks are complete; no "add appropriate error handling" or "handle edge cases" stubs.
- No "Similar to Task N" cross-references — every code block is inlined.
- No `#` comments in code blocks; docstrings on every function. `# noqa` directives are allowed but not used in this plan.

### 3. Type and naming consistency

- `FeatureViewSet.get_serializer_class()` returns `FeatureListItemSerializer` for `list` and `FeatureSerializer` otherwise. The two serializers are the only serializer classes in `features/serializers.py`.
- `apply_bbox(queryset, raw_bbox)` is called with `self.request.query_params.get("bbox")` (returns `str | None`) — matches the helper's signature.
- The `make_feature` factory's keyword arguments (`geometry`, `properties`, `created_by`) match the spec's description.
- The `auth_client` fixture's return type is `APIClient`; the JWT setup happens inside the fixture body.
- The `large_feature_dataset` fixture is `scope="session"` and uses `django_db_setup` / `django_db_blocker` to manage the database access (the standard pytest-django pattern for session-scoped DB fixtures).
- The `_audit` key is consistent across `FeatureSerializer.to_representation` (sets it), `FeatureListItemSerializer.to_representation` (strips it), and the round-trip / retrieve tests (asserts on it).
- The wire-format `type` field is always `"Feature"` (string literal in `FeatureSerializer.to_representation`).
- The endpoint URL paths are consistent: `/api/features/`, `/api/features/{id}/`, `/api/categories/` (the test files use these literals; the URL routing is wired via DRF's `DefaultRouter` + the `path("categories/", ...)` route).
- The `ALLOWED_ORDERING` and `DEFAULT_ORDERING` constants live at module top in `features/views.py` and are referenced from `get_queryset()` only.

### 4. AGENTS.md compliance audit

- **Pre-commit gate** — Task 9 Step 4 runs `pre-commit run --all-files` (the full gate), not a targeted run. ✓
- **No `git commit` steps** — the plan intentionally omits them per the project convention (the model plan, auth plan, and seed plan all follow the same pattern). Each task ends with a "Status note" that names the unstaged files. ✓
- **Keyword args** for >1-arg calls: `Feature.objects.create(geometry=..., properties=..., created_by=...)` everywhere; `client.post(path=LIST_URL, payload, format="json")`; `client.get(f"{LIST_URL}?bbox=...")`; `apply_bbox(queryset, raw_bbox=...)` (kwarg even for the second arg, per the strict reading of the rule); `RefreshToken.for_user(user)` (single arg, exempt); `GEOSGeometry(wkt, srid=4326)` uses kwargs for `srid`. The single concession is `client.post(path, payload, format="json")` where the 2nd positional arg is a dict literal; the existing auth plan uses the same pattern. If a reviewer wants full kwargs here, switch to `client.post(path=LIST_URL, data=payload, format="json")`. ✓
- **Function ordering** — in `features/views.py`, public class `FeatureViewSet` precedes public function `categories_view` (both are entry points; no private helpers). In `features/serializers.py`, the public classes `FeatureSerializer` and `FeatureListItemSerializer` precede the private helper `_is_json_serializable` (and its `_JSON_PRIMITIVES` constant) at the bottom of the file. ✓
- **Blank line after dedent** — applied in `FeatureViewSet.get_queryset` (after the `if search_term:` block and the `if ordering_param:` block), in `FeatureSerializer.validate_properties` (after each of `if value is None:`, `if not isinstance(value, dict):`, and `for key in value:` blocks), and in `large_feature_dataset` (after the `if existing < 1000:` block). ✓
- **Nesting depth** — all functions stay at ≤ 3 levels. The `FeatureSerializer.to_representation` body is 2 levels. The `_is_json_serializable` helper recurses but the call depth in the recursion is small (3 levels for `dict → list → primitive`). ✓
- **PEP 8 naming** — `created_user`, `auth_client`, `list_response`, `first_result`, `polygon_wkt`, `created_geometry`, `expected_wkt`, `feature_count`, `large_feature_dataset`, `netherlands_features`, `world_features`, `refresh_token`, `access_token`, `filtered_queryset`, `sydney_pk`, `body`, `geometry_payload`. No shortened names; the domain abbreviation `nl_` is spelled out as `netherlands_` throughout (see §7 cross-spec correction #3). ✓
- **No inline / local imports** — all production-code imports are at module top. The two originally-inlined imports (`from django.db import connection` and `from accounts.models import User as UserModel` inside `large_feature_dataset`, plus `from django.db import connection` inside `test_search_uses_trigram_index`) were moved to the top of their files. ✓
- **Function length** — every production function is < 100 lines. The longest is `FeatureSerializer.to_representation` (~15 lines). The `large_feature_dataset` fixture is ~25 lines; the `apply_bbox` helper is ~10 lines. ✓
- **No comments** — no `#` comments in code blocks; docstrings on every function. ✓

### 5. Out-of-scope confirmation

- No Django admin registration (deferred per overview spec §18).
- No Pydantic validation layer (explicitly excluded per Feature API spec §6; pure DRF).
- No token blacklist / server-side logout (auth spec §4 sets `BLACKLIST_AFTER_ROTATION=False`; out of scope for the Feature API plan).
- No per-user feature ownership (deferred per overview spec §18).
- No bounding-box wrap-aware mode (antimeridian-crossing bboxes out of scope per overview spec §18).
- No OpenAPI schema generation (deferred per overview spec §18).
- No CORS changes (Foundation spec already wires CORS; the Feature API spec re-uses the existing config).
- No additional `Feature.Meta.ordering` (the Feature Data Model spec §2 explicitly excludes it; ordering is set per-view in `get_queryset`).
- No `OpClass` in `Meta.indexes` for the trigram GIN (Django 5.1 bug; the index is already created via `RunSQL` in the initial migration, owned by the Feature Data Model plan).
- No new `pytest_plugins` re-import of `accounts/tests/conftest.py` (the root-conftest pattern is already in place from the Feature Data Model plan; this plan does not re-import it).
- No bulk-create of the 1200 features in a per-test fixture (the session-scoped fixture is used; the trigram-index test runs once per session).

### 6. Architectural notes for the executing engineer

- The `Feature.objects.create_user` field collision noted in the Feature Data Model plan does not apply here: the auth plan's `accounts.User.objects.create_user` is the one used in fixtures. The Feature model has no `create_user` classmethod.
- The `pytest_plugins` re-import approach from earlier plan drafts is **not** used here. The root `conftest.py` defines `user` and `other_user`; this plan's `features/tests/conftest.py` defines feature-app-specific fixtures only.
- The session-scoped `large_feature_dataset` fixture uses `django_db_setup` / `django_db_blocker` to manage the database access. This is the standard pytest-django pattern for session-scoped DB fixtures; if the test environment is changed (e.g. switching to a non-PostGIS backend), the fixture needs an update.
- The `ordering` validation error message format is `f"Invalid ordering value: {ordering_param}. Allowed: {', '.join(ALLOWED_ORDERING)}"` — the spec shows the format `{"detail": "Invalid ordering value: <value>. Allowed: ..."}`. The implementation matches.
- The `validate_properties` method returns `{}` (not `None`) for the `None` input case, so the saved feature has `properties == {}` rather than `properties is None`. This matches the Feature Data Model spec §2 (`properties` defaults to `{}`).

### 7. Cross-spec corrections to apply when those plans/specs land

- The Feature API spec text under §9 ("Tests") and §4 ("Bbox filter") claims the `user` / `other_user` fixtures are "auto-discovered" from `accounts/tests/conftest.py`. This plan documents the correction (root conftest) but does not modify the spec text. A follow-up spec revision should drop the "auto-discovered" claim and reference the root conftest.
- The Feature API spec lists 6 test files (`test_serializers.py`, `test_views.py`, `test_bbox_filter.py`, `test_pagination.py`, `test_search.py`, `test_geojson_roundtrip.py`). This plan adds a 7th: `test_categories.py` (2 tests). The spec's overview §3 (test placement) does not mention a categories test file. The follow-up spec revision should either (a) move the categories tests into `test_views.py` (making it 8 tests) or (b) document `test_categories.py` as an additional file.
- The Feature API spec §4 ("Bbox filter") and §9 ("Tests") use the abbreviation `nl_` for the Netherlands fixture set and the test name `test_nl_fixture_filter`. AGENTS.md forbids domain-specific abbreviations, so the plan spells these out as `netherlands_features` (fixture) and `test_netherlands_fixture_filter` (test). The spec text should be updated to match. The docstring "Filtering the NL fixture set" can stay as "NL" since it's a well-known country code in informal English, but the test code uses the spelled-out form.
- The plan renames the variable that holds `serializer.data` output from `data` to `body` (matching the auth plan's `body = response.json()` convention). The variable name `data` is a generic name forbidden by AGENTS.md.
