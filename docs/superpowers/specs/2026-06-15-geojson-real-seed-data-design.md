# Real-Coordinate Seed Data Spec

**Date:** 2026-06-15
**Status:** Approved for implementation
**Parent:** [Seed Data Spec](./2026-06-12-geojson-seed.md)
**Supersedes:** §2–§6 of the parent spec, with §4 (curated features) preserved
**Required by:** Frontend map page (so search lands at real locations)

## 1. Purpose

Replace the current "deterministic synthetic" seed (random points + random
names decoupled) with a bundle of **real geographic features**. After
running `python manage.py seed_features`, the map should look like a
human-curated dataset: cities at their actual coordinates, roads as their
actual paths, parks as their actual boundaries. Searching for a name
(e.g. "Bronkhorst") should pan/zoom to that feature's real location.

The end goal: **the system creates the data; a human could have**.

## 2. Why the change

The current seeder pairs a name picked from a pool with a coordinate
picked uniformly at random from the NL bbox. A search for "Bronkhorst"
hits the dropdown but `map.js` pans to a random point — often in the sea
or in a featureless part of the country. The data is unusable for
discovery.

The fix is to commit a real-data bundle (sourced from OpenStreetMap
once) and have the seeder load from that bundle instead of generating.
The expanded name pools (§5) total **269 features** across all
categories and geometry types.

## 3. Architecture

```
features/management/commands/
├── seed_features.py              # rewritten: load bundle → write DB
├── download_seed_data.py         # NEW: Overpass → bundle
└── seed_data/                    # NEW: committed bundle
    ├── city.geojson
    ├── town.geojson
    ├── road.geojson
    ├── river.geojson
    ├── canal.geojson
    ├── rail.geojson
    ├── park.geojson
    ├── lake.geojson
    ├── province.geojson
    ├── nature_reserve.geojson
    └── country.geojson           # curated (NL outline + Caribbean)
```

- **Bundle is committed** to the repo. `python manage.py seed_features`
  reads from disk — no network in dev, CI, or production seeding.
- **`download_seed_data.py` is run once by a developer** to (re)populate
  the bundle. It lives in the repo for reproducibility and future
  refreshes; it is **not** invoked by the seeder, the Makefile, or CI.
- **License**: OSM data is ODbL. Add `seed_data/README.md` attributing
  OpenStreetMap contributors (required by ODbL §4).

## 4. Bundle format

Each `seed_data/<category>.geojson` is a GeoJSON `FeatureCollection`.
Every Feature has:

| Field | Source |
| --- | --- |
| `geometry` | verbatim from Overpass (`out geom;`) |
| `properties.name` | the OSM `name` tag |
| `properties.color` | looked up from `CATEGORY_COLORS` in `seed_features.py` (see §7) |
| `properties.category` | the filename minus `.geojson` |

The `country.geojson` file is hand-curated (not from Overpass) and
contains two features: the `NETHERLANDS_OUTLINE_MULTIPOLYGON` and
`CARIBBEAN_NETHERLANDS_COLLECTION` from the current seeder, with
`category: "country"`.

## 5. Expanded name pools (269 total)

The current pools have 164 features; expand modestly to ~269 so the
search dropdown has rich results without bloating the bundle.

| Category | Count | Geometry | Overpass filter |
| --- | --- | --- | --- |
| `city` | 40 | Point | `place=city` |
| `town` | 40 | Point | `place=town` |
| `road` | 30 | LineString | `highway=motorway` or `highway=trunk` |
| `river` | 30 | LineString | `waterway=river` |
| `canal` | 20 | LineString | `waterway=canal` |
| `rail` | 20 | LineString | `railway=rail` |
| `park` | 30 | Polygon | `leisure=park` OR `boundary=protected_area` + `protect_class=2` |
| `lake` | 30 | Polygon | `natural=water` + `water=lake` |
| `province` | 12 | Polygon | `admin_level=4` |
| `nature_reserve` | 15 | MultiPolygon | `boundary=protected_area` + `protect_class=1/3/4` |
| `country` | 2 | MultiPolygon + GeometryCollection | (curated, not from Overpass) |

Names are pre-vetted against the public Nominatim endpoint
(`https://nominatim.openstreetmap.org/search?q=<name>&countrycodes=nl&limit=1`)
during pool selection. Any name that returns 0 results is swapped for a
known-good alternative before the download script runs. The download
script then re-verifies via Overpass (§8).

## 6. Download script (`download_seed_data.py`)

A Django management command. Invoked manually as:

```bash
python manage.py download_seed_data
```

### 6.1 Per-category flow

For each `(category, names)` in `NAME_POOLS`:

1. Issue a single Overpass query with one `nwr[...]` clause per name
   (batch — one HTTP round-trip per category, not per name). Set
   `out geom;` so geometry coords come back inline.
2. For each name in the pool, **expect exactly one match**. If the
   count is 0 or >1, raise `CommandError` listing the offending names.
3. Write all results to `seed_data/<category>.geojson` as a
   `FeatureCollection`, using a small helper that converts the
   Overpass JSON shape to GeoJSON (just `type: "Feature"`, `geometry`
   passthrough, `properties: {name, color, category}`).

### 6.2 Disambiguation

When a name is ambiguous (e.g. "Amsterdam" → city, metro station,
airport), the script picks the **highest-priority type** per the
category's filter (§5) and ignores the rest. Implemented as a single
ranked filter inside the loop:

```python
def select_canonical(results: list, expected_type: str) -> dict:
    for result in sorted(results, key=lambda r: TYPE_PRIORITY[r["type"]]):
        if result_matches_type(result, expected_type):
            return result
    raise CommandError(f"No match of type {expected_type} in {results}")
```

`TYPE_PRIORITY` orders OSM types so the most specific / largest wins
(relation > way > node).

### 6.3 Network resilience

- Endpoint: `https://overpass-api.de/api/interpreter`
- Timeout: 60 s per request
- Retries: 3 attempts, exponential backoff (2 s, 4 s, 8 s)
- On final failure: raise `CommandError` with the full response body

### 6.4 What the script does **not** do

- It does not write to the database. Bundle only.
- It does not invoke the seeder. Bundle is committed; seeder reads it.
- It is not run by CI. CI seeds from the committed bundle.

## 7. Seeder rewrite (`seed_features.py`)

### 7.1 Behavior

`handle()`:

1. `Feature.objects.all().delete()`
2. For each file in `SEED_DATA_FILES` (the 11 GeoJSON files), load it
   and create a `Feature` per item.
3. `bulk_create(features, batch_size=500)`.
4. Print: `seed_features: created N features from seed_data/`.

`_run_seed()` is no longer random. It just iterates the bundle.

### 7.2 CLI flags

| Flag | Status | Reason |
| --- | --- | --- |
| `--count` | **removed** | Replaced by bundle size |
| `--bbox` | **removed** | Data is fixed to NL |
| `--seed` | **removed** | Data is deterministic by virtue of the bundle |
| `--keep` | **removed** | Default behavior is already "truncate Feature, leave User"; flag was a no-op |

This is a breaking change to the seeder CLI. Update `Makefile`, docs,
and any scripts that invoke these flags. (None in the current repo
other than the Makefile target.)

### 7.3 Color map (single source of truth)

```python
CATEGORY_COLORS: Final[dict[str, str]] = {
    "city":           "#e41a1c",  # red
    "town":           "#fc8d62",  # salmon
    "road":           "#ff7f00",  # orange
    "river":          "#377eb8",  # blue
    "canal":          "#1b9e77",  # teal
    "rail":           "#999999",  # gray
    "park":           "#4daf4a",  # green
    "lake":           "#a6cee3",  # light blue
    "province":       "#984ea3",  # purple
    "nature_reserve": "#005500",  # dark green
    "country":        "#21468B",  # NL blue (curated)
}
```

Colors are written into the bundle at download time, so the seeder
doesn't have to look them up — but `CATEGORY_COLORS` is kept in
`seed_features.py` as documentation / the canonical mapping.

### 7.4 Curated features (preserved from parent spec §4)

`country.geojson` is hand-curated and contains the two features
already defined in the current seeder:

- `NETHERLANDS_OUTLINE_MULTIPOLYGON` — the NL mainland + Wadden Islands
  + Zeeland (MultiPolygon, ~35 ring vertices).
- `CARIBBEAN_NETHERLANDS_COLLECTION` — Bonaire, Sint Eustatius, Saba
  (GeometryCollection of 3 Points).

These continue to render on top of all other features (they're the
last two features written).

## 8. Failure modes

| Failure | Behavior |
| --- | --- |
| Overpass returns 0 results for a name | `CommandError` lists name + category. Dev fixes the pool, re-runs. |
| Overpass returns >1 result for a name | `CommandError` lists name + count. Dev adjusts `TYPE_PRIORITY` or pool. |
| Overpass request fails 3x | `CommandError` with full response body. Dev retries manually. |
| Bundle file missing at seed time | `CommandError` listing the missing file. Dev runs `download_seed_data` or restores from git. |
| Bundle file has malformed GeoJSON | `CommandError` from `json.load`. Dev fixes the file. |

The principle: **fail loudly, never silently skip**. A bundle with
gaps is worse than a failed seed.

## 9. Testing

### 9.1 Download script — `features/tests/management/test_download_seed_data.py`

Mock the `requests.post` call to Overpass. Cases:

- Single match per name → bundle is written, GeoJSON is valid, all
  features have a `geometry` and the expected `properties`.
- 0 matches → `CommandError` raised, no file written.
- >1 matches → `CommandError` raised with name and count.
- Overpass returns 500 → 3 retries, then `CommandError`.
- Verify `seed_data/<category>.geojson` is a valid GeoJSON
  `FeatureCollection` (round-trip through `json.load`).

### 9.2 Seeder — `features/tests/management/test_seed_features.py` (updated)

Replace the existing fixture-based tests with bundle-based tests:

- Run `seed_features` against a small fixture bundle (3-4 files in
  `features/tests/fixtures/seed_data/`).
- Verify: features created, count matches bundle, every feature has
  non-empty geometry, every feature has a category from the color map,
  curated features (country) are last.
- Verify CLI: `seed_features` accepts no flags, raises on unknown
  flags.

### 9.3 No changes needed

- **API tests**: surface is unchanged.
- **Frontend tests**: don't care about coordinates.
- **Migration**: none — data only.
- **E2E (Playwright)**: re-run after the change to confirm the map
  shows real features. No test changes required.

## 10. Files added / changed

**New:**
- `features/management/commands/download_seed_data.py`
- `features/management/commands/seed_data/*.geojson` (11 files)
- `features/management/commands/seed_data/README.md` (ODbL attribution)
- `features/tests/management/test_download_seed_data.py`
- `features/tests/fixtures/seed_data/*.geojson` (small test bundle)

**Changed:**
- `features/management/commands/seed_features.py` — rewritten to load
  bundle (CLI flags removed, color map added, generators removed).
- `features/tests/management/test_seed_features.py` — updated for
  bundle-based behavior.
- `Makefile` — update `seed` target comment if it references removed
  flags.

**Removed (from `seed_features.py`):**
- `DEFAULT_BBOX`, `DEFAULT_COUNT`, `DEFAULT_SEED`
- `BBOX_SAFETY_MARGIN`
- `GEOMETRY_TYPE_WEIGHTS`
- `_generate_point`, `_generate_line_string`, `_generate_polygon`, etc.
- `GEOMETRY_GENERATORS` table

**Preserved:**
- `NETHERLANDS_OUTLINE_MULTIPOLYGON`, `NETHERLANDS_OUTLINE_RING`,
  `WADDEN_ISLANDS_RING`, `ZEELAND_RING`
- `CARIBBEAN_NETHERLANDS_COLLECTION`
- `_build_curated_features` (refactored to read from
  `seed_data/country.geojson`)

## 11. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Overpass rate-limits or is down during dev download | 3-retry policy + manual retry. No CI dependency. |
| OSM data changes between bundle commits | Bundle is committed; refresh is a manual one-shot. Out of scope for v1. |
| Bundle is ODbL — must attribute | `seed_data/README.md` with the standard OSM attribution. |
| Picking 267 names that all resolve on Overpass | Pre-vet with Nominatim during pool authoring; download script re-verifies and fails loudly on misses. |
| `download_seed_data.py` accidentally invoked in CI | Make it a separate command, not a side effect of `seed_features`. CI uses the committed bundle. |

## 12. Out of scope

- Auto-refreshing the bundle from OSM (cron, scheduled job, etc.).
- Supporting multiple regions (only the Netherlands).
- Switching to a different data source (Natural Earth, CBS, etc.) —
  OSM is sufficient.
- Real-time geocoding of user-input names (separate feature; the
  frontend already does client-side name search against the bundle).
