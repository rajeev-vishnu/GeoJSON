# GeoJSON API — Feature Data Model Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** [Foundation](./2026-06-12-geojson-foundation.md)
**Required by:** Feature API, Seed

## 1. Purpose

The `features.Feature` model: fields, indexes (GiST on geometry,
BTree on timestamps, trigram GIN on `properties->>'name'`), the
`Category` enum, the `TrigramExtension` migration, and the
features model test suite. No views, serializers, or pagination
here — those live in the
[Feature API spec](./2026-06-12-geojson-feature-api.md).

## 2. `features.Feature` model

Single model. Generic geometry. Open `properties` JSONField (no
typed columns).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `UUIDField` (PK, default `uuid4`) | Stable IDs. |
| `geometry` | `GeometryField(srid=4326)` | Accepts all 6 GeoJSON geometry types. GiST spatial index. |
| `properties` | `JSONField(default=dict)` | The only "data" beyond geometry. Fully open `dict[str, JsonValue]`. |
| `created_by` | `FK(User, on_delete=CASCADE)` | Audit trail only; no per-user ownership, so deletion takes the user's features with them. |
| `created_at` | `DateTimeField(auto_now_add)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

`Meta.indexes`:

- `GistIndex(fields=["geometry"])` — supports the bbox filter.
- `BTreeIndex(fields=["updated_at", "id"])` — supports the list
  endpoint's default sort (`-updated_at, id`) and
  `?ordering=updated_at|-updated_at`. The `-` prefix in a
  `BTreeIndex` field is decorative: Django ignores it, the index
  is on `updated_at` ascending, and PostgreSQL walks it backward
  for descending sorts. Including `id` in the index makes the full
  sort (`-updated_at, id`) an index-only scan with no in-memory
  tiebreak.
- `BTreeIndex(fields=["created_at", "id"])` — supports
  `?ordering=created_at|-created_at` with the same tiebreak
  guarantee.
- Trigram GIN index on `properties->>'name'`, declared in the
  model as

  ```python
  GinIndex(
      OpClass(F("properties__name"), name="gin_trgm_ops"),
      name="features_properties_name_trgm_idx",
  )
  ```

  Django renders this as
  `CREATE INDEX ... USING gin (("properties" ->> 'name') gin_trgm_ops);`.
  The `OpClass` wrapper is required: Django's `GinIndex` does not
  accept an `opclasses=` kwarg, so the operator class must be
  attached per expression via `OpClass(expr, name="gin_trgm_ops")`
  from `django.contrib.postgres.indexes`. Without the opclass the
  index exists but the planner will not use it for `ILIKE` queries
  and the search reverts to a Seq Scan. Supports the `?search=`
  substring filter (`properties->>'name' ILIKE '%query%'`,
  case-insensitive).

### Trigram extension migration

The `pg_trgm` PostgreSQL extension is installed by the initial
migration via `TrigramExtension()` from
`django.contrib.postgres.operations`, placed **before** the
`CreateModel` / `AddIndex` for `Feature` so the trigram opclass is
available at index-creation time. The `TrigramExtension()` operation
is idempotent (`CREATE EXTENSION IF NOT EXISTS pg_trgm`); the
`postgis/postgis:16-3.4` Docker image ships with `pg_trgm` already
installed, so the migration is a no-op in the standard environment
and a hard failure in any environment that lacks it (intentional —
we want to know, not silently fall back to a Seq Scan).

### No `Meta.ordering`

Default sort is set explicitly in
`FeatureViewSet.get_queryset()` as `order_by("-updated_at", "id")`
so the model has no hidden behavior. Tests and other call sites
must sort explicitly.

### No first-class `name` or `color` columns

Those are values inside `properties`, treated the same as any
other property. See [Overview
§19](./2026-06-12-geojson-api-design.md#19-decisions-and-trade-offs-summary)
for the rationale (matches RFC 7946, allows extensible schemas,
doesn't reject valid GeoJSON that lacks either key).

## 3. `Feature.Category` enum

The `Feature` model declares an inner
`Category(models.TextChoices)` class that defines the closed set of
seed-side and frontend-side category values. The enum is a Python
*convention* — it is **not** a database constraint, **not** a
check on `properties.category`, and **not** a server-side
validator. The `properties` JSONField is fully open; the API
accepts any string (or non-string, though the seed only ever uses
strings) for `properties.category` regardless of whether it
matches the enum.

```python
class Category(models.TextChoices):
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
```

The 11 enum values are lowercase snake_case strings on the wire
(e.g. `"category": "nature_reserve"`) and Title-Case
human-readable labels in the admin / Django shell / frontend
dropdown. The enum's purpose is to give the seed a fixed pool to
draw from, the frontend a fixed list to render in dropdowns and
filter chips, and the `/api/categories/` endpoint (see [Feature
API spec §3](./2026-06-12-geojson-feature-api.md#3-categories-endpoint))
a single source of truth that is imported directly from the model.

A user POSTing a feature with `properties.category: "submarine
cable"` is fine — the server stores it, returns it, and the
search filter still works on `properties->>'name'`. The `category`
value just won't appear in the frontend's category dropdown as a
quick option.

## 4. Tests

### `features/tests/test_models.py` (~4 tests)

- `test_feature_creation` — create a `Feature` with sensible
  defaults; assert `id` is a UUID, `geometry` is a `GEOSGeometry`
  in SRID 4326, `properties` defaults to `{}`, `created_at` and
  `updated_at` are populated.
- `test_default_values` — assert `is_active` is not on `Feature`
  (it lives on `User`); `properties` default is `{}`; the model
  has no `Meta.ordering`.
- `test_geometry_round_trip_all_types` — parametrize across the 7
  GeoJSON geometry types (Point, MultiPoint, LineString,
  MultiLineString, Polygon, MultiPolygon, GeometryCollection);
  save a `Feature` with each, retrieve it, assert the WKT
  round-trips exactly.
- `test_created_by_cascade` — delete the `User`; the `Feature`
  is deleted in the same transaction (`on_delete=CASCADE`); no
  orphan row remains.
- `test_indexes_exist` — query `pg_indexes` (or the Django
  introspection API) and assert the four expected indexes are
  present: `features_geometry_id` (GiST),
  `features_updated_at_id` (BTree),
  `features_created_at_id` (BTree), and
  `features_properties_name_trgm_idx` (GIN with
  `gin_trgm_ops`).
