# GeoJSON API — Seed Data Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** [Foundation](./2026-06-12-geojson-foundation.md), [Feature Data Model](./2026-06-12-geojson-feature-model.md)
**Required by:** CI

## 1. Purpose

`features/management/commands/seed_features.py` — a Django
management command that populates the database with a deterministic
synthetic dataset of vector features covering all 7 standard
GeoJSON geometry types. Idempotent: re-running with the same
`--seed` produces the same features (modulo UUIDs and timestamps).

## 2. Default region and flags

- **Default bbox: the Netherlands** (WGS84
  `3.3, 50.7, 7.3, 53.55`). The bbox includes the mainland, the
  Wadden Islands, the Zeeland delta, and a small slice of the North
  Sea; it does not include German or Belgian land. The exact bbox
  is a constant
  `DEFAULT_BBOX = (3.3, 50.7, 7.3, 53.55)` in the command module.
- **Default count: 1,000** features, distributed across all seven
  standard GeoJSON geometry types (see §3).
- **Default PRNG seed: `42`**, hard-coded as `DEFAULT_SEED = 42`.
  The command uses a single `random.Random(seed)` instance for all
  generation, so re-runs with the same `--seed` produce the exact
  same feature set byte-for-byte (modulo the assigned UUIDs and
  timestamps, which still vary by run). This is what makes
  `test_seed_features.py` deterministic.

### Flags

| Flag | Type | Default | Purpose |
| --- | --- | --- | --- |
| `--bbox=<minx>,<miny>,<maxx>,<maxy>` | 4 floats | `3.3,50.7,7.3,53.55` (Netherlands) | Generation region. Validated by the same `parse_bbox()` used by the API filter. |
| `--count=<int>` | positive int | `1000` | Total number of generated features (excluding the curated "Netherlands outline" feature; see §4). |
| `--seed=<int>` | int | `42` | PRNG seed for deterministic generation. |
| `--keep` | bool flag | `False` | When set, do **not** truncate `accounts_user`; only truncate and re-seed `Feature` rows. Default behavior truncates and re-seeds `Feature` rows and leaves `accounts_user` alone (i.e. `--keep` is on by default; the flag is retained for explicit clarity and for future re-seeding of `accounts_user`). |

## 3. Geometry-type distribution

The 1,000 generated features (plus the 1 curated outline) cover all
seven GeoJSON geometry types from RFC 7946 §3.1 — the six concrete
types and the heterogeneous `GeometryCollection`. The distribution
is deliberately skewed toward the most common real-world types
(Point, LineString, Polygon) but guarantees a meaningful number of
each of the multi-types so a reviewer can exercise the full
`GeometryField` surface:

| Type | Count | Why this many |
| --- | --- | --- |
| `Point` | 400 | Cities, POIs, addresses. The most common real-world feature. |
| `LineString` | 250 | Roads, rivers, canals, rail lines. |
| `Polygon` | 200 | Provinces, municipalities, parks, lakes. |
| `MultiPoint` | 50 | Train-station groups per city, lighthouse chains, distributed infrastructure. |
| `MultiLineString` | 50 | Highway networks split by province, river systems with branches. |
| `MultiPolygon` | 50 | Country outline with EEZ and Wadden Islands, multi-province landholdings, fragmented nature reserves. |
| `GeometryCollection` | 0 | Generated as part of the curated outline (see §4); no random `GeometryCollection` rows are produced. |

Total random features: 1,000. Total with the curated outline: 1,001.

## 4. Curated "Netherlands outline" feature

A single, hand-shaped `MultiPolygon` (with one polygon per major
land mass — mainland NL, the Wadden Islands as a `MultiPolygon` of
small islands, and Zeeland) is added at the end of the seed run
with `properties.name = "Netherlands"`,
`properties.color = "#21468B"` (the NL-flag blue), and
`properties.category = "country"`. This feature is **always** the
first one rendered on the map (rendered last in the GeoJSON
feature array, on top of the others) and gives the demo an
immediately recognizable shape. Coordinates are derived from a
low-resolution approximation of the Dutch land border (~50 vertices
per ring, hand-tuned to be recognizable) and are stored as a
Python literal in the command module — not generated randomly.

The outline feature's `GeometryCollection` element (used to attach
the Caribbean Netherlands as a separate collection, for
completeness) is implemented as a top-level `GeometryCollection`
row rather than nesting it inside the `MultiPolygon`, so the seed
contains exactly one row of each of the seven GeoJSON geometry
types. That `GeometryCollection` row has
`properties.name = "Caribbean Netherlands"`,
`properties.color = "#21468B"`, and
`properties.category = "country"`.

## 5. Properties and category pool

The open-properties model (see
[Feature Data Model spec §2](./2026-06-12-geojson-feature-model.md#2-featuresfeature-model))
means the server imposes no schema. The seed keeps things simple:
**every seeded feature has exactly three properties — `name`,
`color`, and `category`.** No other keys are seeded. The API still
accepts arbitrary keys on user-created features (the
[Feature API spec §6](./2026-06-12-geojson-feature-api.md#6-validation)
`validate_properties()` is unchanged), but the seed is uniform.

`category` is a closed-set enum on the seed side (see
[Feature Data Model spec §3](./2026-06-12-geojson-feature-model.md#3-featurecategory-enum),
`Feature.Category`). The 11 values map to the geometry types as
follows:

| `category` | Human label | Applies to geometry types |
| --- | --- | --- |
| `city` | City | `Point` |
| `town` | Town | `Point` |
| `road` | Road | `LineString`, `MultiLineString` |
| `river` | River | `LineString`, `MultiLineString` |
| `canal` | Canal | `LineString` |
| `rail` | Rail | `LineString`, `MultiLineString` |
| `park` | Park | `Polygon` |
| `lake` | Lake | `Polygon` |
| `province` | Province | `Polygon`, `MultiPolygon` |
| `nature_reserve` | Nature reserve | `MultiPolygon` |
| `country` | Country | `MultiPolygon` (curated), `GeometryCollection` (curated) |

For each randomly-generated feature, the seed:

1. Picks the geometry type (weighted by the distribution table).
2. Picks a `category` from the enum values that apply to that
   geometry type (uniform random across the applicable subset).
3. Picks `name` from a deterministic, onomastic pool scoped to
   the chosen `category` (provinces for `province`, Dutch cities
   for `city`, rivers for `river`, etc.). Names are unique within
   a category so the search dropdown has distinguishable results.
4. Picks `color` from a small palette (`#e41a1c`, `#377eb8`,
   `#4daf4a`, `#984ea3`, `#ff7f00`, `#21468B`).

This means a `Point` is always either `city` or `town`, a
`LineString` is always `road | river | canal | rail`, and so on.
The `country` category is reserved for the curated outline +
Caribbean `GeometryCollection` features and is never assigned to
random features.

## 6. Generation algorithm

For each of the 1,000 random features, in order:

1. Pick a type from the distribution table in §3, weighted by
   count.
2. Pick a center point `(cx, cy)` uniformly at random inside the
   bbox (clamped to keep the resulting geometry inside the bbox
   with a small safety margin of ~0.05° on every side).
3. Generate the coordinates deterministically from the same
   `random.Random(seed)` instance:
   - `Point`: 1 position = `(cx, cy)`.
   - `MultiPoint`: 3–8 positions, each a small random offset from
     `(cx, cy)`.
   - `LineString`: 2–10 positions along a roughly straight line,
     jittered.
   - `MultiLineString`: 2–4 LineStrings, each 2–8 positions.
   - `Polygon`: a single closed ring of 3–8 positions, returning
     to the start point (RFC 7946 §3.1.6 — a linear ring is a
     closed line with ≥ 4 positions).
   - `MultiPolygon`: 2–3 simple closed rings, each 3–8 positions.
4. Wrap the coordinates in a `Point`/`MultiPoint`/... object via
   `rest_framework_gis.geometry`, which validates the shape and
   produces a Django `GEOSGeometry` ready for storage in the
   `GeometryField`.
5. Construct the `properties` dict with exactly three keys:
   `name` (from the onomastic pool scoped to the chosen category),
   `color` (from the small palette), and `category` (one of the
   applicable enum values, picked uniformly at random).
6. Save the `Feature` row with `created_by=<first registered user
   or None>`. The seed is independent of the auth flow — features
   have a creator if any user has registered, otherwise
   `created_by=None`. (The `Feature` model allows `created_by` to
   be `NULL` only for seed data; the API requires a creator.)

After the 1,000 random features, the curated "Netherlands outline"
feature is appended (so it renders on top of the others in the
frontend's GeoJSON feature array ordering).

## 7. Idempotency

The command's default behavior is:

1. `Feature.objects.all().delete()` (truncates the table via the
   cascade rules; `created_by` FK is `CASCADE` so no orphan rows
   can be left).
2. Generate 1,000 features + 1 curated feature.
3. Bulk-insert with
   `Feature.objects.bulk_create(features, batch_size=500)`.

`bulk_create` skips signals (which is fine — `Feature` has none
beyond the default auto-now timestamps, which are populated by the
DB) and is fast for 1k rows. Re-running with the same `--seed`
produces the same features (modulo UUIDs and timestamps). With
`--keep`, the users table is not touched.

## 8. Tests

### `features/tests/management/test_seed_features.py` (~3 tests)

- `test_seed_creates_all_geometry_types` — run the command with
  the default `--count=1000 --seed=42`; assert the seeded dataset
  contains at least one feature of each of the seven GeoJSON
  geometry types.
- `test_seed_curated_outline` — assert the curated
  "Netherlands outline" feature is present with
  `name: "Netherlands"`, `category: "country"`, and a
  `MultiPolygon` geometry; assert the Caribbean `GeometryCollection`
  feature is present with `name: "Caribbean Netherlands"`.
- `test_seed_exactly_three_properties` — assert that every seeded
  feature has exactly the three properties `name`, `color`, and
  `category` (no extras, no missing keys).
- `test_seed_is_idempotent` — run the command twice with the same
  `--seed`; assert the second run produces the same feature count
  and the curated outline is still present.
- `test_seed_keep_preserves_users` — run the command with
  `--keep`; assert no `accounts_user` rows are deleted.
