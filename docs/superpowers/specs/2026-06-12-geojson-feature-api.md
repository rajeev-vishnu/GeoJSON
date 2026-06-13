# GeoJSON API — Feature API Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** [Foundation](./2026-06-12-geojson-foundation.md), [Auth](./2026-06-12-geojson-auth.md), [Feature Data Model](./2026-06-12-geojson-feature-model.md)
**Required by:** Frontend, Seed, CI

## 1. Purpose

The `FeatureViewSet` and supporting code: feature CRUD endpoints, the
bbox filter, page-number pagination, GeoJSON wire format, properties
validation, and the categories endpoint. Co-located with the six
features test files.

## 2. Feature endpoints

Base path: `/api/`. Auth: `Authorization: Bearer <access_token>` header
(see [Auth spec §4](./2026-06-12-geojson-auth.md#4-auth-endpoints) for
JWT lifetimes and error semantics).

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/features/` | required | List, paged, bbox-filterable, searchable. |
| `GET` | `/api/features/{id}/` | required | Retrieve one. |
| `POST` | `/api/features/` | required | Create. |
| `PATCH` | `/api/features/{id}/` | required | Partial update. |
| `PUT` | `/api/features/{id}/` | required | Full update. |
| `DELETE` | `/api/features/{id}/` | required | Delete. |
| `GET` | `/api/categories/` | required | List of `Feature.Category` enum values. See below. |

### List query parameters

- `bbox` (optional): `minx,miny,maxx,maxy` in WGS84.
- `page` (optional, default `1`): page number.
- `search` (optional): case-insensitive substring on
  `properties->>'name'`.
- `ordering` (optional): one of `created_at`, `-created_at`,
  `updated_at`, `-updated_at`. Default `-updated_at`. Any other
  value returns
  `400 {"detail": "Invalid ordering value: <value>. Allowed: ..."}`.

### List response shape (200)

```json
{
  "next": "http://host/api/features/?bbox=-10,40,5,55&page=2",
  "prev": null,
  "results": [ <Feature>, <Feature>, ... ]
}
```

`next` is `null` on the last page. `prev` is `null` on the first
page. 100 features per request, hardcoded as `PAGE_SIZE = 100` in
`features/pagination.py`. 404 on `page` past the last page. 400 on
invalid `bbox` (wrong arity, out-of-range values, min > max). 400 on
invalid `page` (non-integer, < 1).

### Feature wire format (RFC 7946)

```json
{
  "type": "Feature",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "geometry": { "type": "Point", "coordinates": [10.0, 20.0] },
  "properties": {
    "name": "Foo",
    "color": "#ff0000",
    "category": "city"
  }
}
```

No `created_at` / `updated_at` / `created_by` on the list wire (the
assignment example shows plain Features). The detail endpoint
includes them in a wrapper key `_audit` inside `properties`
(foreign-member pattern from RFC 7946). The wrapper is named `_audit`
rather than `_meta` to avoid colliding with the common framework
meaning of `_meta` (type / defaults metadata) in JS and Python
toolchains:

```json
{
  "type": "Feature",
  "id": "...",
  "geometry": {...},
  "properties": {
    "name": "Foo",
    "color": "#ff0000",
    "category": "city",
    "_audit": {
      "created_at": "2026-06-12T10:30:00Z",
      "updated_at": "2026-06-12T10:30:00Z",
      "created_by": "alice@example.com"
    }
  }
}
```

`created_by` is rendered as the user's email (not the UUID) so the
audit trail is human-readable in API responses. With
`on_delete=CASCADE`, deleting a user also deletes their features in
the same transaction, so the lookup in the detail response is never
against a missing user and the field is always populated for
surviving features.

## 3. Categories endpoint

`GET /api/categories/` returns the closed set of
[`Feature.Category`](./2026-06-12-geojson-feature-model.md#3-featurecategory-enum)
enum values as a flat JSON array of strings. The endpoint requires
auth (same JWT bearer as the rest of the API). The response body is
the values list in declaration order:

```json
[
  "city", "town", "road", "river", "canal", "rail",
  "park", "lake", "province", "nature_reserve", "country"
]
```

The endpoint is implemented as a small DRF view in
`features/views.py` that does `Feature.Category.values` and wraps
the result. The [Frontend spec](./2026-06-12-geojson-frontend.md)
calls it on page load to populate the category badge filter chips
and the map panel's category dropdown. If the enum ever changes, the
frontend updates on next page load — no hard-coded list to keep in
sync.

## 4. Bbox filter

`features/filters.py` exposes:

```python
def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """Parse 'minx,miny,maxx,maxy'. Raises ValidationError on bad input."""
```

Validation rules:

- Exactly 4 comma-separated floats.
- `minx`, `maxx` in `[-180, 180]`.
- `miny`, `maxy` in `[-90, 90]`.
- `minx <= maxx`, `miny <= maxy`.

The view's `get_queryset()` chains:

1. `queryset = Feature.objects.all()`.
2. `.filter(geometry__intersects=polygon)` (skipped when no `bbox`).
3. `.filter(properties__name__icontains=search)` (skipped when no
   `search`).
4. `.order_by("-updated_at", "id")` — the default sort;
   `?ordering=...` overrides this.

PostGIS uses the GiST index on `geometry` for the bbox filter. The
substring search uses the trigram GIN index on `properties->>'name'`
(declared in the [Feature Data Model spec §2](./2026-06-12-geojson-feature-model.md#2-featuresfeature-model));
at <10k features the index is optional but included so `EXPLAIN`
shows an Index Scan and the search path is the same in tests and
production.

The bbox param is optional. Omitting it returns all features, still
paged.

## 5. Pagination

`features/pagination.py` defines
`BboxPageNumberPagination(PageNumberPagination)`:

- `page_size = 100` (hardcoded, not configurable via query string).
- `page_query_param = "page"`.
- Custom `get_paginated_response()` returns exactly
  `{ next, prev, results }`.
- `next` and `prev` are built by `request.build_absolute_uri()` so
  they preserve query string params (`bbox`, `ordering`, `search`).
- 404 on `page` past the last page (DRF default).
- No `count` field in the response (matches the assignment example
  exactly).

## 6. Validation

Pure DRF. No Pydantic.

- `geometry` is validated by
  `rest_framework_gis.serializers.GeoJSONGeometryField`, which
  accepts all 6 standard GeoJSON geometry types and rejects
  malformed coordinates.
- `properties` is a `serializers.JSONField()` with a
  `validate_properties()` method that:
  1. Treats `None` as `{}`.
  2. Rejects non-dict values with a 400
     ("properties must be a JSON object").
  3. Recursively checks all values are JSON-serializable
     (`str | int | float | bool | None | list | dict`).
  4. Validates keys are non-empty strings.
- `type` field is ignored on input (we always emit `"Feature"` on
  output).
- The 400 response uses DRF's default error format:
  `{"detail": "..."}` for non-field errors and
  `{"<field>": ["..."]}` for field-level errors.

## 7. Serializers

In `features/serializers.py`:

- `FeatureSerializer(ModelSerializer)` — `geometry` via
  `GeoJSONGeometryField`, `properties` via `JSONField` with
  `validate_properties()`. Read-only: `id`, `created_at`,
  `updated_at`, `created_by`.
- `FeatureListItemSerializer(FeatureSerializer)` — overrides
  `to_representation` to strip `_audit` for list responses. Used by
  the paginator.

## 8. URL routing

`features/urls.py` is a DRF `DefaultRouter` with `FeatureViewSet`
registered as `features`. The `categories` endpoint is a small
function-based view (`@api_view(["GET"]) @permission_classes([IsAuthenticated])`)
mounted alongside the router at `categories/`.

The root `config/urls.py` mounts `features.urls` at `api/`, so the
final paths are `api/features/`, `api/features/{id}/`, and
`api/categories/`.

## 9. Tests

`features/tests/conftest.py`:

- `auth_client(api_client, user)` — DRF `APIClient` with a valid JWT
  in the `Authorization` header.
- `make_feature` — factory creating features with sensible defaults
  (Point geometry inside the Netherlands bbox, `name` and `color`
  from small pools, optional `category` and `created_by`).

The `user` fixture is auto-discovered from
[`accounts.tests.conftest`](./2026-06-12-geojson-auth.md#7-tests).

### `features/tests/test_serializers.py` (~4 tests)

- `test_geometry_round_trip_all_types` — parametrize across the 7
  GeoJSON geometry types; serialize → deserialize → assert equality.
- `test_properties_must_be_dict` — non-dict `properties` rejected
  with 400.
- `test_properties_rejects_non_json_values` — value with a
  non-JSON-serializable object rejected with 400.
- `test_read_only_fields` — `id`, `created_at`, `updated_at`,
  `created_by` cannot be set by client on POST.

### `features/tests/test_views.py` (~6 tests)

- `test_list_requires_auth` — no JWT → 401.
- `test_list_returns_paginated_shape` — assert exactly
  `{next, prev, results}` and no `count`.
- `test_retrieve_returns_audit` — GET detail includes `_audit`
  inside `properties`.
- `test_create` — POST a valid Point feature returns 201 and the
  GeoJSON shape.
- `test_partial_update` — PATCH a single field returns 200 with
  the merged feature.
- `test_delete` — DELETE returns 204; subsequent GET returns 404.

### `features/tests/test_bbox_filter.py` (~6 tests)

- `test_world_fixture_filter` — uses an existing fixture set
  spread across the world; filter by various bboxes (NL bbox,
  southern hemisphere bbox, antimeridian-adjacent bbox); assert
  counts and IDs.
- `test_nl_fixture_filter` — uses a second fixture set spread
  across the Netherlands default bbox; filter by NL bbox (returns
  all), by a small sub-bbox (returns subset), and by a disjoint
  bbox (returns empty).
- `test_invalid_bbox_arity` — 3 values → 400.
- `test_invalid_bbox_out_of_range` — `minx=200` → 400.
- `test_invalid_bbox_min_greater_than_max` — `minx > maxx` → 400.
- `test_bbox_omitted_returns_all` — no `bbox` param returns full
  unfiltered set, still paged.

### `features/tests/test_pagination.py` (~4 tests)

- `test_page_size_is_100` — create 250 features, request page 1,
  assert 100 results.
- `test_page_2` — page 2 returns the next 100.
- `test_past_last_page` — page past the end returns 404.
- `test_page_zero` — `page=0` returns 400.
- `test_next_prev_preserve_query_string` — request with `?bbox=...`
  returns `next` / `prev` URLs that include `bbox=...`.

### `features/tests/test_search.py` (~3 tests)

- `test_search_substring_match` — features with varied
  `properties.name`; `?search=foo` returns only those whose name
  contains `foo` (case-insensitive).
- `test_search_no_match` — unknown substring returns empty `results`.
- `test_search_uses_trigram_index` — runs `EXPLAIN` against
  `SELECT id FROM features WHERE properties->>'name' ILIKE '%foo%'`
  and asserts the plan contains
  `Bitmap Index Scan on features_props_name_trgm_idx` (or
  `Index Scan` / `Index Only Scan` — any plan node that names the
  trigram index). The test runs against the seeded dataset, so the
  planner has enough rows to choose the index. This locks in the
  index as part of the search contract: a future migration that
  drops or renames the index will fail this test loudly instead of
  silently regressing search to a Seq Scan.

### `features/tests/test_geojson_roundtrip.py` (~2 tests)

- `test_geojson_round_trip_all_types` — parametrized across all
  7 GeoJSON geometry types: POST one feature of each type with
  nested objects/arrays in `properties`, GET it back, verify
  exact equality of geometry and properties.
- `test_geojson_audit_on_detail` — POST a feature, GET detail,
  assert the `_audit` block matches the post timestamps and
  `created_by` is the requester's email.
