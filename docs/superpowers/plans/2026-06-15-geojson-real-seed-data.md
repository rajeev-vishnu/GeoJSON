# Real-Coordinate Seed Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the random-coordinate seeder with a real-coordinate seeder. `python manage.py seed_features` loads 269 real Dutch geographic features (cities, towns, roads, rivers, canals, rails, parks, lakes, provinces, nature reserves, plus 2 curated country features) from a committed `seed_data/*.geojson` bundle sourced from OpenStreetMap, so search lands at the actual location of any feature.

**Architecture:** The seeder becomes "load bundle, write DB" — no random generation. A new `download_seed_data` management command (run manually, not by CI) queries the Overpass API for each name in expanded `NAME_POOLS`, picks the canonical match by type, and writes the result to per-category GeoJSON files in `features/management/commands/seed_data/`. Curated country features (NL outline + Caribbean) are hand-curated in `country.geojson` and committed alongside. All bundle files are committed to the repo and licensed under ODbL (OpenStreetMap attribution in `seed_data/README.md`).

**Tech Stack:** Django 5.1 management commands, GeoJSON (RFC 7946), Overpass API (OpenStreetMap), Django GEOS, Python `urllib.request` (stdlib only, no new deps), pytest-django.

**Note:** Per the user's instruction, this plan omits commit steps. The implementer will accumulate changes locally and commit at logical boundaries.

---

## File Structure

**New / modified command files**

| File | Responsibility |
| --- | --- |
| `features/management/commands/seed_features.py` | Rewritten: loads `seed_data/*.geojson`, deletes existing `Feature` rows, bulk-creates. Exposes a single CLI (no flags). |
| `features/management/commands/download_seed_data.py` | NEW: Overpass client + per-category query + canonical-result picker + bundle writer. |
| `features/management/commands/seed_data/city.geojson` | NEW: 40 real `place=city` features. |
| `features/management/commands/seed_data/town.geojson` | NEW: 40 real `place=town` features. |
| `features/management/commands/seed_data/road.geojson` | NEW: 30 real highway features. |
| `features/management/commands/seed_data/river.geojson` | NEW: 30 real river features. |
| `features/management/commands/seed_data/canal.geojson` | NEW: 20 real canal features. |
| `features/management/commands/seed_data/rail.geojson` | NEW: 20 real rail features. |
| `features/management/commands/seed_data/park.geojson` | NEW: 30 real park features. |
| `features/management/commands/seed_data/lake.geojson` | NEW: 30 real lake features. |
| `features/management/commands/seed_data/province.geojson` | NEW: 12 real province polygons. |
| `features/management/commands/seed_data/nature_reserve.geojson` | NEW: 15 real nature-reserve multipolygons. |
| `features/management/commands/seed_data/country.geojson` | NEW: 2 hand-curated features (NL outline + Caribbean). |
| `features/management/commands/seed_data/README.md` | NEW: ODbL attribution. |

**New / modified test files**

| File | Responsibility |
| --- | --- |
| `features/tests/management/test_seed_features.py` | Rewritten: bundle-based tests (no flag-based tests). |
| `features/tests/management/test_download_seed_data.py` | NEW: mocked-Overpass tests for the download command. |
| `features/tests/fixtures/seed_data/*.geojson` | NEW: small fixture bundle for the seeder tests. |

**Removed (from `seed_features.py`):**
- `DEFAULT_BBOX`, `DEFAULT_COUNT`, `DEFAULT_SEED`, `BBOX_SAFETY_MARGIN`
- `GEOMETRY_TYPE_WEIGHTS`, `GEOMETRY_GENERATORS` and the `_generate_*` helpers
- `COLOR_PALETTE` (replaced by `CATEGORY_COLORS`)
- `--count`, `--bbox`, `--seed`, `--keep` CLI flags
- The 6-vertex random circle/jitter code path

**Preserved (in `seed_features.py`):**
- `NETHERLANDS_OUTLINE_RING`, `WADDEN_ISLANDS_RING`, `ZEELAND_RING`, `NETHERLANDS_OUTLINE_MULTIPOLYGON`, `CARIBBEAN_NETHERLANDS_COLLECTION` (used to author `country.geojson` once)
- `_first_registered_user_id`

---

## Task 0: Wipe existing `Feature` rows from the web database

**Files:** none (one-time cleanup via Django shell)

The web database currently holds the random-coordinate features
seeded by the old seeder. The new seeding workflow writes fresh,
real-coordinate data on top, so this task wipes the existing
`Feature` rows first to guarantee the database is in a known-empty
state before we begin.

Note: the new `seed_features` command in Task 3 wipes `Feature` rows
on every run, so this task is a one-time belt-and-braces that also
serves as a clean visual confirmation. **`accounts_user` rows are
intentionally left alone** — the seeder doesn't touch them and the
new workflow does not require a fresh user table.

- [ ] **Step 1: Confirm the database is reachable**

Run: `docker compose exec web python -c "import django; django.setup(); from django.db import connection; connection.ensure_connection(); print('ok')"`

Expected: `ok`

- [ ] **Step 2: Snapshot the current feature count**

Run:
```bash
docker compose exec web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from features.models import Feature
print('features:', Feature.objects.count())
"
```

Expected: a thousand-ish number (e.g. `features: 1002`).

- [ ] **Step 3: Wipe all `Feature` rows**

Run:
```bash
docker compose exec web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from features.models import Feature
feature_count = Feature.objects.count()
Feature.objects.all().delete()
print(f'wiped {feature_count} features')
"
```

Expected: `wiped N features` (where N matches the snapshot from Step 2).

- [ ] **Step 4: Verify the `Feature` table is empty**

Run:
```bash
docker compose exec web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from features.models import Feature
assert Feature.objects.count() == 0, Feature.objects.count()
print('feature table is empty')
"
```

Expected: `feature table is empty`.

---

## Task 1: Expand `NAME_POOLS` to 269 entries and add `CATEGORY_COLORS` + `SEED_DATA_FILES`

**Files:**
- Modify: `features/management/commands/seed_features.py` (top of file, before the geometry generators)

The current `NAME_POOLS` has 164 entries; the new pools have 269. Also add the `CATEGORY_COLORS` map (single source of truth) and the `SEED_DATA_FILES` mapping (category → bundle filename).

- [ ] **Step 1: Read the current top of `seed_features.py` to plan the edit**

Open `features/management/commands/seed_features.py`. The current `NAME_POOLS` ends at line 250 (just before the `"""Onomastic name pools, one per category."""` docstring). The `COLOR_PALETTE` constant is at lines 50-61.

- [ ] **Step 2: Replace `COLOR_PALETTE` with `CATEGORY_COLORS`**

In `seed_features.py`, replace the entire `COLOR_PALETTE` block (lines 50-61) with:

```python
CATEGORY_COLORS: Final[dict[str, str]] = {
    "city": "#e41a1c",
    "town": "#fc8d62",
    "road": "#ff7f00",
    "river": "#377eb8",
    "canal": "#1b9e77",
    "rail": "#999999",
    "park": "#4daf4a",
    "lake": "#a6cee3",
    "province": "#984ea3",
    "nature_reserve": "#005500",
    "country": "#21468B",
}
"""The single source of truth for category → color, applied to every Feature at seed time.

`country` is reserved for the curated outline and Caribbean
collection; the seeder still writes the color here for symmetry,
but the geometry comes from `seed_data/country.geojson`.
"""
```

- [ ] **Step 3: Replace `NAME_POOLS` with the expanded 269-entry version**

Replace the entire `NAME_POOLS` block (lines 87-250) with the following. The structure is the same; only the contents change.

```python
NAME_POOLS: Final[dict[str, tuple[str, ...]]] = {
    "city": (
        "Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven",
        "Groningen", "Maastricht", "Arnhem", "Haarlem", "Delft",
        "Leiden", "Nijmegen", "Tilburg", "Almere", "Breda",
        "Apeldoorn", "Enschede", "Amersfoort", "Zwolle", "Deventer",
        "Leeuwarden", "Dordrecht", "Zoetermeer", "'s-Hertogenbosch", "Heerlen",
        "Venlo", "Hilversum", "Ede", "Helmond", "Roosendaal",
        "Spijkenisse", "Gouda", "Zaandam", "Lelystad", "Alphen aan den Rijn",
        "Hoorn", "Vlissingen", "Schiedam", "Bergen op Zoom", "Kampen",
    ),
    "town": (
        "Lisse", "Valkenburg", "Edam", "Marken", "Volendam",
        "Giethoorn", "Urk", "Hindeloopen", "Naarden", "Willemstad",
        "Bergen", "Monnickendam", "Schoorl", "Woudrichem", "Heusden",
        "Hattem", "Stavoren", "Sloten", "Thorn", "Bronkhorst",
        "De Rijp", "Marken", "Oudeschild", "Den Burg", "Hollum",
        "West-Terschelling", "Nes", "Buren", "Sluis", "Veere",
        "Domburg", "Zoutelande", "Cadzand", "Hulst", "Axel",
        "Kerkrade", "Vaals", "Mechelen", "Epen", "Valkenburg aan de Geul",
    ),
    "road": (
        "A1", "A2", "A4", "A6", "A7",
        "A9", "A10", "A12", "A15", "A16",
        "A20", "A27", "A28", "A29", "A30",
        "A31", "A32", "A35", "A37", "A38",
        "A58", "A59", "A65", "A67", "A73",
        "A76", "A77", "A79", "A200", "N7",
    ),
    "river": (
        "Rijn", "Maas", "IJssel", "Waal", "Lek",
        "Merwede", "Nederrijn", "Zwarte Water", "Vecht", "Dommel",
        "Mark", "Roer", "Geleenbeek", "Geul", "Jeker",
        "Swalm", "Beek", "Schelde", "Hollandse IJssel", "Oude Rijn",
        "Amstel", "Bergsche Maas", "Dieze", "Dintel", "Grensmaas",
        "Hollands Diep", "Linge", "Niers", "Spaarne", "Gelderse IJssel",
    ),
    "canal": (
        "Noordhollandsch Kanaal", "Amsterdam-Rijnkanaal", "Maas-Waalkanaal", "Julianakanaal", "Noordzeekanaal",
        "Kanaal door Zuid-Beveland", "Kanaal door Walcheren", "Markkanaal", "Twentekanaal", "Zuid-Willemsvaart",
        "Eemskanaal", "Van Starkenborghkanaal", "Prinses Margrietkanaal", "Kanaal door Voorne", "Calandkanaal",
        "Beerkanaal", "Noord-Willemskanaal", "Kreekrak", "Noordhollands Kanaal", "Leidse Vaart",
    ),
    "rail": (
        "HSL-Zuid", "Staatslijn A", "Staatslijn B", "Staatslijn C", "Staatslijn D",
        "Staatslijn E", "Staatslijn F", "Staatslijn G", "Staatslijn H", "Staatslijn K",
        "Staatslijn J", "IJssellijn", "Brabantroute", "Hanzelijn", "MerwedeLingelijn",
        "Schiphollijn", "Westtak", "Oosttak", "Noordtak", "Zuidtak",
    ),
    "park": (
        "Veluwe", "Hoge Veluwe", "Utrechtse Heuvelrug", "Sallandse Heuvelrug", "Drents-Friese Wold",
        "Weerribben-Wieden", "Oostvaardersplassen", "Kennemerduinen", "Duinen van Texel", "Amsterdamse Bos",
        "Nationaal Park Zuid-Kennemerland", "Duinen van Schiermonnikoog", "Lauwersmeer", "Alde Feanen", "De Weerribben",
        "De Wieden", "Drentsche Aa", "Dwingelderveld", "Holterberg", "Landgoederen Oldenzaal",
        "Sint Jansberg", "Mookerheide", "Hatertse Vennen", "Land van Maas en Waal", "Plasmolen",
        "Norgerholt", "Boomkwekerij-regio Boskoop", "Flevopolder", "Schollevaar", "Bos en Waal",
    ),
    "lake": (
        "IJsselmeer", "Markermeer", "Veluwemeer", "Drontermeer", "Zwarte Meer",
        "Gooimeer", "Eemmeer", "Nuldernauw", "Wolderwijd", "Ketelmeer",
        "Lauwersmeer", "Veerse Meer", "Grevelingen", "Haringvliet", "Volkerak",
        "Zoommeer", "Markiezaatsmeer", "Braassemermeer", "Westeinderplassen", "Loosdrechtse Plassen",
        "Vinkeveense Plassen", "Reeuwijkse Plassen", "Nieuwkoopse Plassen", "Kaag", "Bergsche Plassen",
        "Kralingse Plas", "Schildmeer", "Leekstermeer", "Paterswoldse Meer", "Foxholstermeer",
    ),
    "province": (
        "Groningen", "Friesland", "Drenthe", "Overijssel", "Flevoland",
        "Gelderland", "Utrecht", "Noord-Holland", "Zuid-Holland", "Zeeland",
        "Noord-Brabant", "Limburg",
    ),
    "nature_reserve": (
        "Waddenzee", "Schiermonnikoog", "Vlieland", "Terschelling", "Ameland",
        "Schouwen-Duiveland", "Goeree-Overflakkee", "Voornes Duin", "Biesbosch", "Weerribben-Wieden",
        "Fochteloërveen", "Dwingelderveld", "Drents-Friese Wold", "De Maasduinen", "Schoorlse Duinen",
    ),
}
"""Onomastic name pools, one per category. Names are unique within a category.

Total: 40+40+30+30+20+20+30+30+12+15 = 267 random features, plus
2 curated `country` features = 269 total.

The `country` category is intentionally NOT in this table — the
curated NL outline and Caribbean collection live in
`seed_data/country.geojson`, not in a name pool.
"""
```

- [ ] **Step 4: Add `SEED_DATA_FILES` constant after `NAME_POOLS`**

Immediately after the `NAME_POOLS` block (and its docstring), add:

```python
SEED_DATA_FILES: Final[dict[str, str]] = {
    "city": "city.geojson",
    "town": "town.geojson",
    "road": "road.geojson",
    "river": "river.geojson",
    "canal": "canal.geojson",
    "rail": "rail.geojson",
    "park": "park.geojson",
    "lake": "lake.geojson",
    "province": "province.geojson",
    "nature_reserve": "nature_reserve.geojson",
    "country": "country.geojson",
}
"""Maps each category to the filename under `seed_data/` that holds its real features.

Curated `country.geojson` is hand-authored; the other 10 files are
produced by `python manage.py download_seed_data` from Overpass.
"""
```

- [ ] **Step 5: Verify the file still imports cleanly**

Run: `docker compose exec web python -c "from features.management.commands.seed_features import NAME_POOLS, CATEGORY_COLORS, SEED_DATA_FILES; print(sum(len(v) for k, v in NAME_POOLS.items()), len(CATEGORY_COLORS), len(SEED_DATA_FILES))"`

Expected output: `267 11 11`

---

## Task 2: Add the bundle loader (`_load_bundle`) with tests

**Files:**
- Modify: `features/management/commands/seed_features.py`
- Test: `features/tests/management/test_seed_features.py` (new test, add at the end)

The loader reads every `seed_data/<file>.geojson` in `SEED_DATA_FILES` and returns a list of `(category, geojson_feature_dict)` pairs. It uses `json.load` (stdlib), not a third-party GeoJSON lib, so we control the shape.

- [ ] **Step 1: Add the `_load_bundle` function**

In `seed_features.py`, just below the existing `SEED_DATA_FILES` definition, add:

```python
def _load_bundle(seed_data_dir: Path) -> list[tuple[str, dict]]:
    """Read every `seed_data/<file>.geojson` in `SEED_DATA_FILES` and return (category, feature) pairs.

    Each file is a GeoJSON `FeatureCollection`. This function returns
    a flat list of `(category, feature_dict)` tuples — the caller is
    responsible for constructing `Feature` model instances.

    `seed_data_dir` is the path to the directory containing the
    GeoJSON files; it defaults to the `seed_data/` directory next to
    this module. Pass an explicit path in tests.
    """
    features: list[tuple[str, dict]] = []
    for category, filename in SEED_DATA_FILES.items():
        file_path = seed_data_dir / filename
        with file_path.open(encoding="utf-8") as handle:
            collection = json.load(handle)
        if collection.get("type") != "FeatureCollection":
            raise CommandError(
                f"seed_data/{filename}: expected GeoJSON FeatureCollection, got {collection.get('type')!r}"
            )
        for feature in collection.get("features", []):
            features.append((category, feature))
    return features
```

- [ ] **Step 2: Add the `Path` and `json` imports**

In `seed_features.py`, add `import json` (alphabetical with the other stdlib imports) and `from pathlib import Path` to the imports at the top of the file. The current imports block:

```python
from __future__ import annotations

import math
import random
from typing import Final

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import (
    GEOSGeometry,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from django.core.management.base import BaseCommand, CommandError

from features.filters import parse_bbox
from features.models import Feature
```

becomes:

```python
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Final

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import (
    GEOSGeometry,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from django.core.management.base import BaseCommand, CommandError

from features.filters import parse_bbox
from features.models import Feature
```

- [ ] **Step 3: Write the failing test**

Append to `features/tests/management/test_seed_features.py`:

```python
def test_load_bundle_reads_geojson_files(tmp_path) -> None:
    """_load_bundle reads every file in SEED_DATA_FILES and returns (category, feature) pairs."""
    from features.management.commands.seed_features import SEED_DATA_FILES, _load_bundle

    (tmp_path / "city.geojson").write_text(
        '{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [4.9, 52.37]}, "properties": {"name": "Amsterdam"}}]}',
        encoding="utf-8",
    )
    (tmp_path / "town.geojson").write_text(
        '{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [6.18, 52.08]}, "properties": {"name": "Bronkhorst"}}]}',
        encoding="utf-8",
    )

    bundle = _load_bundle(tmp_path)

    assert len(bundle) == 2
    assert bundle[0][0] == "city"
    assert bundle[0][1]["properties"]["name"] == "Amsterdam"
    assert bundle[1][0] == "town"
    assert bundle[1][1]["properties"]["name"] == "Bronkhorst"
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `docker compose exec web pytest features/tests/management/test_seed_features.py::test_load_bundle_reads_geojson_files -v`

Expected: PASS

- [ ] **Step 5: Add a test for malformed input**

Append:

```python
def test_load_bundle_raises_on_wrong_type(tmp_path) -> None:
    """_load_bundle raises CommandError when a file is not a FeatureCollection."""
    from django.core.management.base import CommandError

    from features.management.commands.seed_features import _load_bundle

    for filename in ["city.geojson", "town.geojson", "road.geojson", "river.geojson", "canal.geojson", "rail.geojson", "park.geojson", "lake.geojson", "province.geojson", "nature_reserve.geojson", "country.geojson"]:
        (tmp_path / filename).write_text("{}", encoding="utf-8")

    with pytest.raises(CommandError, match="FeatureCollection"):
        _load_bundle(tmp_path)
```

Run: `docker compose exec web pytest features/tests/management/test_seed_features.py::test_load_bundle_raises_on_wrong_type -v`

Expected: PASS

---

## Task 3: Rewrite `Command.handle()` to load the bundle

**Files:**
- Modify: `features/management/commands/seed_features.py` (the `Command` class)

The new `handle()` reads the bundle, deletes all existing `Feature` rows, creates one `Feature` per bundle entry, and prints the total. CLI flags (`--count`, `--bbox`, `--seed`, `--keep`) are removed.

- [ ] **Step 1: Replace the `add_arguments` and `handle` methods**

In `seed_features.py`, the `Command` class is at the bottom. Replace the entire `add_arguments` and `handle` block with:

```python
    def add_arguments(self, parser: object) -> None:
        """Declare no flags. The seeder is now a "load and write" command.

        Previously the seeder accepted `--count`, `--bbox`, `--seed`,
        and `--keep`. All four were removed when the seeder was
        rewritten to load from `seed_data/*.geojson` instead of
        generating random features. See the Real-Coordinate Seed Data
        spec §7.2.
        """
        return None

    def handle(self, *args: object, **options: object) -> None:
        """Delete all `Feature` rows, load `seed_data/*.geojson`, and bulk-create new Features."""
        seed_data_dir = Path(__file__).parent / "seed_data"

        Feature.objects.all().delete()

        bundle = _load_bundle(seed_data_dir)
        seed_creator_id = _first_registered_user_id()

        features_to_create = [
            Feature(
                geometry=GEOSGeometry(json.dumps(feature["geometry"])),
                properties={
                    "name": feature["properties"]["name"],
                    "color": CATEGORY_COLORS[category],
                    "category": category,
                },
                created_by_id=seed_creator_id,
            )
            for category, feature in bundle
        ]
        Feature.objects.bulk_create(features_to_create, batch_size=500)

        self.stdout.write(
            f"seed_features: created {len(features_to_create)} features from {seed_data_dir}"
        )
```

- [ ] **Step 2: Remove the now-unused random-generation code**

Delete the following from `seed_features.py`:

- `DEFAULT_BBOX`, `DEFAULT_COUNT`, `DEFAULT_SEED`, `BBOX_SAFETY_MARGIN` constants and their docstrings
- `GEOMETRY_TYPE_WEIGHTS` constant and its docstring
- `_generate_point`, `_generate_multi_point`, `_generate_line_string`, `_generate_multi_line_string`, `_generate_polygon`, `_generate_multi_polygon` functions
- `GEOMETRY_GENERATORS` table and its docstring
- `_run_seed` function
- `import random` (no longer used) — keep `import math` if the curated code uses it (it doesn't, so also remove)

After cleanup, the file should contain roughly: imports, `CATEGORY_TO_GEOMETRY_TYPES`, `NAME_POOLS`, `SEED_DATA_FILES`, `CATEGORY_COLORS`, the curated NL outline + Caribbean constants, `_build_curated_features`, `_load_bundle`, `_first_registered_user_id`, and the `Command` class.

- [ ] **Step 3: Verify the file still imports**

Run: `docker compose exec web python -c "from features.management.commands import seed_features; print('ok')"`

Expected: `ok`

---

## Task 4: Create the curated `seed_data/country.geojson`

**Files:**
- Create: `features/management/commands/seed_data/country.geojson`
- Create: `features/management/commands/seed_data/README.md`

The two curated features (NL outline + Caribbean collection) are written to `country.geojson` in the same shape the bundle uses elsewhere.

- [ ] **Step 1: Create the `seed_data/` directory**

Run: `mkdir features/management/commands/seed_data`

- [ ] **Step 2: Generate `country.geojson` from the existing curated constants**

Run this one-liner (it reuses the constants already in `seed_features.py`):

```bash
docker compose exec web python -c "
import json
from features.management.commands.seed_features import NETHERLANDS_OUTLINE_MULTIPOLYGON, CARIBBEAN_NETHERLANDS_COLLECTION
collection = {
    'type': 'FeatureCollection',
    'features': [
        {
            'type': 'Feature',
            'geometry': json.loads(NETHERLANDS_OUTLINE_MULTIPOLYGON.geojson),
            'properties': {'name': 'Netherlands', 'color': '#21468B', 'category': 'country'},
        },
        {
            'type': 'Feature',
            'geometry': json.loads(CARIBBEAN_NETHERLANDS_COLLECTION.geojson),
            'properties': {'name': 'Caribbean Netherlands', 'color': '#21468B', 'category': 'country'},
        },
    ],
}
with open('features/management/commands/seed_data/country.geojson', 'w', encoding='utf-8') as f:
    json.dump(collection, f, ensure_ascii=False, indent=2)
print('wrote country.geojson')
"
```

Expected: `wrote country.geojson`

- [ ] **Step 3: Verify the file is valid GeoJSON**

Run: `docker compose exec web python -c "import json; d = json.load(open('features/management/commands/seed_data/country.geojson')); assert d['type'] == 'FeatureCollection'; assert len(d['features']) == 2; print('valid')"`

Expected: `valid`

- [ ] **Step 4: Create `seed_data/README.md` with ODbL attribution**

Write to `features/management/commands/seed_data/README.md`:

```markdown
# Seed Data Attribution

The GeoJSON files in this directory are derived from
[OpenStreetMap](https://www.openstreetmap.org/) data, which is
licensed under the [Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/).

By using this data, you agree to the ODbL terms, including §4.3
("Attribution"): any derived dataset or product that uses this data
must credit OpenStreetMap contributors visibly. Acceptable wording
is contained in the ODbL; the short form is:

> Map data © OpenStreetMap contributors, ODbL 1.0.

`country.geojson` is hand-curated from public-domain boundary data
and is not subject to ODbL; the other ten files are produced by
`python manage.py download_seed_data` from the Overpass API and
inherit ODbL.
```

---

## Task 5: Create test fixture bundle

**Files:**
- Create: 11 GeoJSON files under `features/tests/fixtures/seed_data/` (1 feature per category except `country` which has 2)

The seeder tests need a small bundle to load. One feature per category is enough.

- [ ] **Step 1: Create the fixture directory**

Run: `mkdir features/tests/fixtures/seed_data`

- [ ] **Step 2: Write the 11 fixture files**

For each category, write a tiny `FeatureCollection` with one (or two for `country`) feature. The names should be obviously fake so we can spot them in test output if they leak.

Write to `features/tests/fixtures/seed_data/city.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
      "properties": {"name": "TestCity"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/town.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [6.18, 52.08]},
      "properties": {"name": "TestTown"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/road.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "LineString", "coordinates": [[4.0, 52.0], [4.5, 52.5], [5.0, 53.0]]},
      "properties": {"name": "TestRoad"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/river.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "LineString", "coordinates": [[4.0, 51.5], [4.5, 52.0]]},
      "properties": {"name": "TestRiver"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/canal.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "LineString", "coordinates": [[4.0, 52.0], [5.0, 52.0]]},
      "properties": {"name": "TestCanal"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/rail.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "LineString", "coordinates": [[4.0, 52.0], [4.5, 52.5]]},
      "properties": {"name": "TestRail"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/park.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.5, 52.0], [4.5, 52.5], [4.0, 52.5], [4.0, 52.0]]]},
      "properties": {"name": "TestPark"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/lake.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[5.0, 52.0], [5.2, 52.0], [5.2, 52.2], [5.0, 52.2], [5.0, 52.0]]]},
      "properties": {"name": "TestLake"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/province.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [5.0, 52.0], [5.0, 53.0], [4.0, 53.0], [4.0, 52.0]]]},
      "properties": {"name": "TestProvince"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/nature_reserve.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "MultiPolygon", "coordinates": [[[[5.0, 53.0], [5.1, 53.0], [5.1, 53.1], [5.0, 53.1], [5.0, 53.0]]], [[[5.2, 53.0], [5.3, 53.0], [5.3, 53.1], [5.2, 53.1], [5.2, 53.0]]]]},
      "properties": {"name": "TestReserve"}
    }
  ]
}
```

Write to `features/tests/fixtures/seed_data/country.geojson`:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "MultiPolygon", "coordinates": [[[[3.5, 51.5], [4.0, 51.5], [4.0, 52.0], [3.5, 52.0], [3.5, 51.5]]]]},
      "properties": {"name": "TestCountry1", "color": "#21468B", "category": "country"}
    },
    {
      "type": "Feature",
      "geometry": {"type": "GeometryCollection", "geometries": [{"type": "Point", "coordinates": [-68.25, 12.10]}]},
      "properties": {"name": "TestCountry2", "color": "#21468B", "category": "country"}
    }
  ]
}
```

- [ ] **Step 3: Verify the bundle round-trips**

Run: `docker compose exec web python -c "
import json
from pathlib import Path
p = Path('features/tests/fixtures/seed_data')
for f in sorted(p.glob('*.geojson')):
    d = json.load(f.open())
    assert d['type'] == 'FeatureCollection'
    print(f.name, len(d['features']))
"`

Expected output (one line per file):
```
canal.geojson 1
city.geojson 1
country.geojson 2
lake.geojson 1
nature_reserve.geojson 1
park.geojson 1
province.geojson 1
rail.geojson 1
river.geojson 1
road.geojson 1
town.geojson 1
```

---

## Task 6: Rewrite `test_seed_features.py` for the bundle-based seeder

**Files:**
- Replace: `features/tests/management/test_seed_features.py`

The existing tests reference `--count=1000`, `--seed=42`, and `--keep`, all of which are removed. The new tests load the fixture bundle, run `seed_features`, and assert the data is in the DB.

- [ ] **Step 1: Replace the test file with the new content**

Overwrite `features/tests/management/test_seed_features.py` with:

```python
"""Tests for the seed_features management command: bundle loading, color map, curated rows."""

from __future__ import annotations

from collections import Counter
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection

from features.models import Feature

pytestmark = pytest.mark.django_db

FIXTURE_SEED_DATA_DIR = Path(__file__).parent.parent / "fixtures" / "seed_data"


def _run_seed_with_fixture_bundle() -> None:
    """Run `python manage.py seed_features` after pointing SEED_DATA_FILES at the fixture bundle.

    The seeder resolves `seed_data/` relative to its own source file
    (`Path(__file__).parent / "seed_data"`). For tests we monkey-patch
    that resolution by writing the fixture files into the production
    `seed_data/` directory, running the command, then restoring it.

    A simpler approach for now: copy the fixture files into the
    real `seed_data/` directory before each test, and rely on the
    conftest cleanup. See conftest fixture below.
    """
    call_command("seed_features", stdout=StringIO())


@pytest.fixture
def fixture_seed_data(monkeypatch) -> None:
    """Swap the production `seed_data/` directory for the fixture bundle for one test."""
    import features.management.commands.seed_features as seed_module

    monkeypatch.setattr(seed_module, "_SEED_DATA_DIR_OVERRIDE", FIXTURE_SEED_DATA_DIR)


def test_seed_loads_features_from_bundle(fixture_seed_data) -> None:
    """Running seed_features creates one Feature per fixture-bundle entry."""
    _run_seed_with_fixture_bundle()

    assert Feature.objects.count() == 12
    assert Feature.objects.filter(properties__name="TestCity").exists()
    assert Feature.objects.filter(properties__name="TestTown").exists()
    assert Feature.objects.filter(properties__name="TestPark").exists()
    assert Feature.objects.filter(properties__name="TestLake").exists()
    assert Feature.objects.filter(properties__name="TestProvince").exists()
    assert Feature.objects.filter(properties__name="TestReserve").exists()
    assert Feature.objects.filter(properties__name="TestRoad").exists()
    assert Feature.objects.filter(properties__name="TestRiver").exists()
    assert Feature.objects.filter(properties__name="TestCanal").exists()
    assert Feature.objects.filter(properties__name="TestRail").exists()
    assert Feature.objects.filter(properties__name="TestCountry1").exists()
    assert Feature.objects.filter(properties__name="TestCountry2").exists()


def test_seed_assigns_category_color_from_map(fixture_seed_data) -> None:
    """Every Feature's `properties.color` matches the CATEGORY_COLORS map for its category."""
    from features.management.commands.seed_features import CATEGORY_COLORS

    _run_seed_with_fixture_bundle()

    for feature in Feature.objects.all():
        category = feature.properties["category"]
        assert feature.properties["color"] == CATEGORY_COLORS[category], (
            f"Feature {feature.pk} ({feature.properties['name']}, category={category}) has color {feature.properties['color']!r}, expected {CATEGORY_COLORS[category]!r}"
        )


def test_seed_creates_all_geometry_types(fixture_seed_data) -> None:
    """The bundle covers at least one of each GeoJSON geometry type used by the seeder."""
    _run_seed_with_fixture_bundle()

    with connection.cursor() as cursor:
        cursor.execute("SELECT ST_GeometryType(geometry) FROM features_feature")
        geometry_type_rows = cursor.fetchall()

    geometry_types_in_seed = {row[0] for row in geometry_type_rows}

    expected_geometry_types = {
        "ST_Point",
        "ST_LineString",
        "ST_Polygon",
        "ST_MultiPolygon",
        "ST_GeometryCollection",
    }
    assert expected_geometry_types.issubset(geometry_types_in_seed), (
        f"Missing geometry types: {expected_geometry_types - geometry_types_in_seed}"
    )


def test_seed_exactly_three_properties(fixture_seed_data) -> None:
    """Every seeded Feature has exactly the three properties name, color, category."""
    _run_seed_with_fixture_bundle()

    property_key_counts: Counter[int] = Counter()
    for feature in Feature.objects.all():
        property_key_counts[len(feature.properties)] += 1
        assert set(feature.properties.keys()) == {"name", "color", "category"}, (
            f"Feature {feature.pk} has unexpected properties: {sorted(feature.properties.keys())}"
        )

    assert property_key_counts[3] == Feature.objects.count()


def test_seed_is_idempotent(fixture_seed_data) -> None:
    """Running seed_features twice produces the same total count and the same curated features."""
    _run_seed_with_fixture_bundle()
    first_run_count = Feature.objects.count()
    assert first_run_count == 12

    _run_seed_with_fixture_bundle()
    second_run_count = Feature.objects.count()
    assert second_run_count == first_run_count

    assert Feature.objects.filter(properties__name="TestCountry1").exists()
    assert Feature.objects.filter(properties__name="TestCountry2").exists()
```

- [ ] **Step 2: Add the `_SEED_DATA_DIR_OVERRIDE` hook in `seed_features.py`**

In `seed_features.py`, modify `_load_bundle` to honor an override (used by tests):

```python
_SEED_DATA_DIR_OVERRIDE: Path | None = None
"""Test hook: when set, _load_bundle reads from this directory instead of the bundled seed_data/."""


def _load_bundle(seed_data_dir: Path) -> list[tuple[str, dict]]:
    """Read every `seed_data/<file>.geojson` in `SEED_DATA_FILES` and return (category, feature) pairs.

    When `_SEED_DATA_DIR_OVERRIDE` is set (test fixture), read from
    that path instead of the directory passed in. This lets tests
    swap in a fixture bundle without copying files.
    """
    effective_dir = _SEED_DATA_DIR_OVERRIDE if _SEED_DATA_DIR_OVERRIDE is not None else seed_data_dir
    features: list[tuple[str, dict]] = []
    for category, filename in SEED_DATA_FILES.items():
        file_path = effective_dir / filename
        with file_path.open(encoding="utf-8") as handle:
            collection = json.load(handle)
        if collection.get("type") != "FeatureCollection":
            raise CommandError(
                f"seed_data/{filename}: expected GeoJSON FeatureCollection, got {collection.get('type')!r}"
            )
        for feature in collection.get("features", []):
            features.append((category, feature))
    return features
```

- [ ] **Step 3: Run the rewritten tests**

Run: `docker compose exec web pytest features/tests/management/test_seed_features.py -v`

Expected: 5 passed (the 5 new tests).

---

## Task 7: Add the Overpass HTTP client (with retry)

**Files:**
- Create: `features/management/commands/download_seed_data.py`
- Test: `features/tests/management/test_download_seed_data.py` (placeholder for now)

We use Python's stdlib `urllib.request` so we add no new dependencies. Three-retry policy with exponential backoff.

- [ ] **Step 1: Create the test file with the import + the first test**

Write to `features/tests/management/test_download_seed_data.py`:

```python
"""Tests for the download_seed_data management command: Overpass client, parser, bundle writer."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_overpass_client_sends_post_to_overpass_endpoint() -> None:
    """_overpass_query POSTs the query body to the Overpass API endpoint."""
    from features.management.commands.download_seed_data import _overpass_query

    with patch("features.management.commands.download_seed_data.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"elements": []}'
        _overpass_query("[out:json];nwr[place=city][name=Amsterdam];out geom;")

    args, _ = mock_urlopen.call_args
    request_obj = args[0]
    assert request_obj.full_url == "https://overpass-api.de/api/interpreter"
    assert b"[out:json]" in request_obj.data
    assert b"Amsterdam" in request_obj.data
    assert request_obj.get_method() == "POST"


def test_overpass_client_retries_on_failure() -> None:
    """_overpass_query retries up to 3 times, then raises CommandError."""
    from features.management.commands.download_seed_data import _overpass_query

    with patch(
        "features.management.commands.download_seed_data.urlopen",
        side_effect=OSError("network down"),
    ) as mock_urlopen:
        with pytest.raises(CommandError, match="Overpass request failed"):
            _overpass_query("[out:json];nwr[place=city];out geom;")

    assert mock_urlopen.call_count == 3
```

- [ ] **Step 2: Create the `download_seed_data.py` command with the client**

Write to `features/management/commands/download_seed_data.py`:

```python
"""Download real-coordinate GeoJSON from the Overpass API into the seed_data/ bundle.

Run via `python manage.py download_seed_data` (manual one-shot).
The committed `seed_data/*.geojson` bundle is the source of truth
for `seed_features`; this command re-populates it from OpenStreetMap.

See docs/superpowers/specs/2026-06-15-geojson-real-seed-data-design.md
for the full spec.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final

from django.core.management.base import BaseCommand, CommandError

OVERPASS_ENDPOINT: Final[str] = "https://overpass-api.de/api/interpreter"
"""The public Overpass API endpoint."""

OVERPASS_TIMEOUT_SECONDS: Final[int] = 60
"""Per-request timeout."""

OVERPASS_MAX_RETRIES: Final[int] = 3
"""Total attempts (1 + 2 retries) before giving up."""

OVERPASS_BACKOFF_SECONDS: Final[tuple[int, ...]] = (2, 4, 8)
"""Exponential backoff between retries (2s, 4s, 8s)."""


def _overpass_query(query_body: str) -> dict:
    """POST `query_body` to Overpass and return the parsed JSON response.

    Retries up to `OVERPASS_MAX_RETRIES` times with exponential
    backoff on network errors. Raises `CommandError` after the final
    failure.
    """
    last_error: Exception | None = None
    for attempt in range(OVERPASS_MAX_RETRIES):
        try:
            request = urllib.request.Request(
                url=OVERPASS_ENDPOINT,
                data=query_body.encode("utf-8"),
                method="POST",
                headers={"User-Agent": "GeoJSON-Django-Seed/1.0"},
            )
            with urllib.request.urlopen(request, timeout=OVERPASS_TIMEOUT_SECONDS) as response:
                payload = response.read()
            return json.loads(payload)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < OVERPASS_MAX_RETRIES - 1:
                time.sleep(OVERPASS_BACKOFF_SECONDS[attempt])
    raise CommandError(f"Overpass request failed after {OVERPASS_MAX_RETRIES} attempts: {last_error}")


class Command(BaseCommand):
    """`python manage.py download_seed_data` — populate the bundle from OpenStreetMap."""

    help = "Download real-coordinate GeoJSON from Overpass into seed_data/<category>.geojson."

    def handle(self, *args: object, **options: object) -> None:
        raise NotImplementedError("Implemented in Task 12")
```

- [ ] **Step 3: Run the tests and confirm they pass**

Run: `docker compose exec web pytest features/tests/management/test_download_seed_data.py -v`

Expected: 2 passed.

---

## Task 8: Add the Overpass query builder and result parser

**Files:**
- Modify: `features/management/commands/download_seed_data.py`
- Test: `features/tests/management/test_download_seed_data.py` (add tests)

- [ ] **Step 1: Add `QUERY_FILTERS` and the query builder**

Append to `download_seed_data.py`:

```python
QUERY_FILTERS: Final[dict[str, str]] = {
    "city":           'nwr["place"="city"]',
    "town":           'nwr["place"="town"]',
    "road":           'nwr["highway"~"motorway|trunk"]',
    "river":          'nwr["waterway"="river"]',
    "canal":          'nwr["waterway"="canal"]',
    "rail":           'nwr["railway"="rail"]',
    "park":           'nwr["leisure"="park"]',
    "lake":           'nwr["natural"="water"]["water"="lake"]',
    "province":       'nwr["admin_level"="4"]["boundary"="administrative"]',
    "nature_reserve": 'nwr["boundary"="protected_area"]',
}
"""Maps each category to the Overpass `nwr[...]` filter clause (without the name selector)."""


def _build_overpass_query(category: str, names: tuple[str, ...]) -> str:
    """Build a single Overpass query that fetches all `names` for `category`.

    Output uses `out geom;` so geometry coords come back inline in
    the elements (no need for a second `out;` call). The query is
    bounded to the Netherlands via `area["ISO3166-1"="NL"]`.
    """
    if category not in QUERY_FILTERS:
        raise CommandError(f"Unknown category: {category!r}")
    name_clauses = "\n  ".join(
        f'{QUERY_FILTERS[category]}["name"="{name}"];' for name in names
    )
    return (
        "[out:json][timeout:60];\n"
        "area[\"ISO3166-1\"=\"NL\"]->.nl;\n"
        f"(\n  {name_clauses}\n);\n"
        "out geom;"
    )
```

- [ ] **Step 2: Add `TYPE_PRIORITY` and the canonical-result picker**

Append:

```python
TYPE_PRIORITY: Final[dict[str, int]] = {
    "relation": 0,
    "way": 1,
    "node": 2,
}
"""Lower number = higher priority. We prefer relations (largest, most detailed) first."""


def _has_geometry(element: dict) -> bool:
    """Return True if the Overpass element carries geometry.

    Three shapes are valid for `out geom`:
    - node → has `lat`/`lon`
    - way → has a `geometry` list of `{lat, lon}` points
    - relation → has `members`, each of which may have a `geometry` list
    """
    if element.get("geometry"):
        return True
    if element.get("lat") is not None:
        return True
    members = element.get("members") or []
    return any(m.get("geometry") for m in members)


def _pick_canonical_result(elements: list[dict], expected_category: str) -> dict:
    """Pick the single canonical OSM element for a name, or raise CommandError.

    "Canonical" means: the highest-priority OSM type (relation > way
    > node) that produced a non-empty geometry. If no element has
    a geometry, raise. If multiple elements tie at the highest
    non-empty type, raise (ambiguity must be resolved at pool-
    selection time, not at parse time).
    """
    with_geometry = [e for e in elements if _has_geometry(e)]
    if not with_geometry:
        raise CommandError(
            f"No element with geometry for {expected_category!r} (got {len(elements)} matches)"
        )
    with_geometry.sort(key=lambda e: TYPE_PRIORITY.get(e.get("type", ""), 99))
    best = with_geometry[0]
    same_priority = [e for e in with_geometry if TYPE_PRIORITY.get(e.get("type", ""), 99) == TYPE_PRIORITY.get(best.get("type", ""), 99)]
    if len(same_priority) > 1:
        names = [e.get("tags", {}).get("name", "?") for e in same_priority]
        raise CommandError(
            f"Ambiguous result for {expected_category!r}: {len(same_priority)} candidates at type={best['type']!r}: {names}"
        )
    return best
```

- [ ] **Step 3: Add the element → GeoJSON-feature converter**

Append:

```python
def _element_to_geojson_feature(element: dict) -> dict:
    """Convert one Overpass element (with `out geom`) to a GeoJSON Feature dict.

    The element must already be the canonical result for its
    category (callers should use `_pick_canonical_result` first).
    """
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        raise CommandError(f"Overpass element missing `name` tag: {element.get('id')}")

    geometry = _element_to_geometry(element)
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {"name": name},
    }


def _element_to_geometry(element: dict) -> dict:
    """Convert one Overpass element to a GeoJSON geometry dict.

    `out geom` returns geometry in two shapes:
    - nodes have `lat`/`lon`
    - ways/relations have a `geometry` list of `{lat, lon}` points

    We rebuild a typed GeoJSON geometry from the OSM type:
    - node → Point
    - way with one geometry entry → LineString
    - way with a closed ring (first == last) → Polygon
    - relation with `type=multipolygon` → MultiPolygon
    """
    element_type = element.get("type")
    if element_type == "node":
        return {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
    if element_type == "way":
        coords = [[pt["lon"], pt["lat"]] for pt in element.get("geometry", [])]
        if len(coords) < 2:
            raise CommandError(f"Way {element.get('id')} has <2 vertices: {coords}")
        if coords[0] == coords[-1] and len(coords) >= 4:
            return {"type": "Polygon", "coordinates": [coords]}
        return {"type": "LineString", "coordinates": coords}
    if element_type == "relation":
        outers, inners = _parse_multipolygon_geometry(element.get("members", []))
        if not outers:
            raise CommandError(f"Relation {element.get('id')} has no outer rings")
        if len(inners) == 0 and len(outers) == 1:
            return {"type": "Polygon", "coordinates": [outers[0]] + [[]]}
        return {"type": "MultiPolygon", "coordinates": [[outer] + [[]] for outer in outers]}
    raise CommandError(f"Unsupported Overpass element type: {element_type!r}")


def _parse_multipolygon_geometry(members: list[dict]) -> tuple[list[list[list[float]]], list[list[list[float]]]]:
    """Parse the `members` array of an Overpass multipolygon relation into outer/inner rings.

    Outer rings are ways with `role=""` (empty) or `role="outer"`.
    Inner rings have `role="inner"`. Returns (outers, inners) where
    each is a list of coordinate rings (list of [lon, lat] pairs).
    """
    outers: list[list[list[float]]] = []
    inners: list[list[list[float]]] = []
    for member in members:
        role = member.get("role", "")
        geometry = member.get("geometry")
        if not geometry:
            continue
        ring = [[pt["lon"], pt["lat"]] for pt in geometry]
        if role in ("", "outer"):
            outers.append(ring)
        elif role == "inner":
            inners.append(ring)
    return outers, inners
```

- [ ] **Step 4: Add tests for the parser**

Append to `features/tests/management/test_download_seed_data.py`:

```python
def test_build_overpass_query_includes_all_names() -> None:
    """_build_overpass_query includes one name clause per name."""
    from features.management.commands.download_seed_data import _build_overpass_query

    query = _build_overpass_query("city", ("Amsterdam", "Rotterdam"))

    assert 'nwr["place"="city"]' in query
    assert '["name"="Amsterdam"]' in query
    assert '["name"="Rotterdam"]' in query
    assert "out geom;" in query


def test_pick_canonical_prefers_relation_over_way_over_node() -> None:
    """_pick_canonical_result returns the highest-priority type."""
    from features.management.commands.download_seed_data import _pick_canonical_result

    way_element = {
        "type": "way", "id": 1,
        "geometry": [{"lat": 52.0, "lon": 4.0}, {"lat": 53.0, "lon": 5.0}],
    }
    relation_element = {
        "type": "relation", "id": 2,
        "members": [
            {"type": "way", "ref": 10, "role": "outer", "geometry": [{"lat": 52.0, "lon": 4.0}, {"lat": 53.0, "lon": 5.0}, {"lat": 52.0, "lon": 4.0}]},
        ],
    }

    chosen = _pick_canonical_result([way_element, relation_element], "province")

    assert chosen["type"] == "relation"


def test_pick_canonical_raises_on_no_geometry() -> None:
    """_pick_canonical_result raises CommandError when no element has geometry."""
    from features.management.commands.download_seed_data import _pick_canonical_result

    with pytest.raises(CommandError, match="No element with geometry"):
        _pick_canonical_result([{"type": "way", "id": 1}], "river")


def test_pick_canonical_raises_on_ambiguity() -> None:
    """_pick_canonical_result raises CommandError when two elements tie at the same priority."""
    from features.management.commands.download_seed_data import _pick_canonical_result

    a = {"type": "way", "id": 1, "geometry": [{"lat": 52.0, "lon": 4.0}, {"lat": 53.0, "lon": 5.0}], "tags": {"name": "A"}}
    b = {"type": "way", "id": 2, "geometry": [{"lat": 52.0, "lon": 4.0}, {"lat": 53.0, "lon": 5.0}], "tags": {"name": "B"}}

    with pytest.raises(CommandError, match="Ambiguous"):
        _pick_canonical_result([a, b], "river")
```

- [ ] **Step 5: Run the new tests**

Run: `docker compose exec web pytest features/tests/management/test_download_seed_data.py -v`

Expected: 6 passed (2 from Task 7 + 4 new).

---

## Task 9: Add the bundle writer

**Files:**
- Modify: `features/management/commands/download_seed_data.py`
- Test: `features/tests/management/test_download_seed_data.py` (add tests)

The writer takes a `category` and a list of GeoJSON feature dicts, wraps them in a `FeatureCollection`, and writes to `seed_data/<category>.geojson`. (Color and category-name are added by the seeder at load time, not by the writer — keeps the bundle minimal.)

- [ ] **Step 1: Add the `_write_bundle` function**

Append to `download_seed_data.py`:

```python
def _write_bundle(seed_data_dir: Path, category: str, features: list[dict]) -> Path:
    """Write `features` to `seed_data_dir/<category>.geojson` as a FeatureCollection.

    `features` is a list of GeoJSON `Feature` dicts (the output of
    `_element_to_geojson_feature`). The output file is the bundle
    the seeder will load.

    Returns the path of the written file.
    """
    seed_data_dir.mkdir(parents=True, exist_ok=True)
    file_path = seed_data_dir / f"{category}.geojson"
    collection = {"type": "FeatureCollection", "features": features}
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(collection, handle, ensure_ascii=False, indent=2)
    return file_path
```

- [ ] **Step 2: Add tests for the writer**

Append to `features/tests/management/test_download_seed_data.py`:

```python
def test_write_bundle_creates_valid_feature_collection(tmp_path) -> None:
    """_write_bundle writes a valid GeoJSON FeatureCollection."""
    from features.management.commands.download_seed_data import _write_bundle

    features = [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [4.9, 52.37]}, "properties": {"name": "Amsterdam"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [4.48, 51.92]}, "properties": {"name": "Rotterdam"}},
    ]

    output_path = _write_bundle(tmp_path, "city", features)

    import json
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["type"] == "FeatureCollection"
    assert len(written["features"]) == 2
    assert written["features"][0]["properties"]["name"] == "Amsterdam"
```

- [ ] **Step 3: Run the test**

Run: `docker compose exec web pytest features/tests/management/test_download_seed_data.py::test_write_bundle_creates_valid_feature_collection -v`

Expected: PASS

---

## Task 10: Wire the `Command` to use the helpers (per-category flow)

**Files:**
- Modify: `features/management/commands/download_seed_data.py` (replace the placeholder `handle`)
- Test: `features/tests/management/test_download_seed_data.py` (add end-to-end test)

The `handle` method iterates `NAME_POOLS`, calls Overpass per category, picks canonical results, writes the bundle.

- [ ] **Step 1: Replace the placeholder `handle` method**

In `download_seed_data.py`, replace the `handle` method:

```python
    def handle(self, *args: object, **options: object) -> None:
        """Fetch each category from Overpass and write the bundle."""
        from features.management.commands.seed_features import NAME_POOLS

        seed_data_dir = Path(__file__).parent / "seed_data"

        for category, names in NAME_POOLS.items():
            if category not in QUERY_FILTERS:
                self.stdout.write(f"Skipping curated category {category!r}")
                continue
            self.stdout.write(f"Fetching {len(names)} {category} features from Overpass...")
            query = _build_overpass_query(category, names)
            response = _overpass_query(query)
            elements_by_name = _group_elements_by_name(response.get("elements", []))

            features_for_bundle: list[dict] = []
            for name in names:
                candidates = elements_by_name.get(name, [])
                if not candidates:
                    raise CommandError(
                        f"Overpass returned 0 results for {name!r} in category {category!r}"
                    )
                canonical = _pick_canonical_result(candidates, expected_category=category)
                features_for_bundle.append(_element_to_geojson_feature(canonical))

            output_path = _write_bundle(seed_data_dir, category, features_for_bundle)
            self.stdout.write(f"  wrote {len(features_for_bundle)} features to {output_path}")
```

- [ ] **Step 2: Add `_group_elements_by_name` helper**

Append to `download_seed_data.py`:

```python
def _group_elements_by_name(elements: list[dict]) -> dict[str, list[dict]]:
    """Group Overpass elements by their `tags.name` value.

    Returns a dict `{name: [element, ...]}`. Elements without a
    `name` tag are silently dropped (Overpass sometimes returns
    untagged ways in a relation).
    """
    grouped: dict[str, list[dict]] = {}
    for element in elements:
        name = element.get("tags", {}).get("name")
        if not name:
            continue
        grouped.setdefault(name, []).append(element)
    return grouped
```

- [ ] **Step 3: Add an end-to-end test that mocks Overpass**

Append to `features/tests/management/test_download_seed_data.py`:

```python
def test_download_command_writes_bundle_for_each_category(tmp_path) -> None:
    """The full command writes one bundle file per non-curated category, with the right shape."""
    from features.management.commands import download_seed_data
    from features.management.commands.seed_features import NAME_POOLS

    overpass_response = {
        "elements": [
            {"type": "node", "id": 1, "lat": 52.37, "lon": 4.9, "tags": {"name": "Amsterdam"}},
            {"type": "node", "id": 2, "lat": 51.92, "lon": 4.48, "tags": {"name": "Rotterdam"}},
        ]
    }
    city_response = {
        "elements": [
            {"type": "node", "id": 3, "lat": 52.08, "lon": 6.18, "tags": {"name": "Bronkhorst"}},
        ]
    }

    def fake_overpass(query_body: str) -> dict:
        if "place" in query_body and "city" in query_body:
            return overpass_response
        if "place" in query_body and "town" in query_body:
            return city_response
        return {"elements": []}

    with (
        patch.object(download_seed_data, "_overpass_query", side_effect=fake_overpass),
        patch.object(download_seed_data.Path, "parent", new=tmp_path),
    ):
        with patch("features.management.commands.seed_features.NAME_POOLS", {"city": ("Amsterdam", "Rotterdam"), "town": ("Bronkhorst",)}):
            call_command("download_seed_data", stdout=StringIO())

    import json
    city_bundle = json.loads((tmp_path / "seed_data" / "city.geojson").read_text(encoding="utf-8"))
    assert city_bundle["type"] == "FeatureCollection"
    assert len(city_bundle["features"]) == 2
    assert {f["properties"]["name"] for f in city_bundle["features"]} == {"Amsterdam", "Rotterdam"}

    town_bundle = json.loads((tmp_path / "seed_data" / "town.geojson").read_text(encoding="utf-8"))
    assert len(town_bundle["features"]) == 1
    assert town_bundle["features"][0]["properties"]["name"] == "Bronkhorst"
```

- [ ] **Step 4: Add `StringIO` import to the test file**

Add `from io import StringIO` to the imports at the top of `test_download_seed_data.py`.

- [ ] **Step 5: Run all download tests**

Run: `docker compose exec web pytest features/tests/management/test_download_seed_data.py -v`

Expected: all tests pass (8+ total: 2 client + 4 parser + 1 writer + 1 end-to-end).

---

## Task 11: Run the download script to populate the real bundle

**Files:** none (just running the command; the script writes to `seed_data/`)

- [ ] **Step 1: Run the download command**

Run: `docker compose exec web python manage.py download_seed_data`

Expected output (abridged):
```
Fetching 40 city features from Overpass...
  wrote 40 features to features/management/commands/seed_data/city.geojson
Fetching 40 town features from Overpass...
  wrote 40 features to features/management/commands/seed_data/town.geojson
...
Fetching 15 nature_reserve features from Overpass...
  wrote 15 features to features/management/commands/seed_data/nature_reserve.geojson
Skipping curated category 'country'
```

- [ ] **Step 2: If the command fails on any name, fix the pool**

The most common failure is `Overpass returned 0 results for <name>`. Open the error, find the offending name, and either:
- Remove it from `NAME_POOLS` and re-run, or
- Replace it with a similar well-known alternative (e.g., swap "Boomkwekerij-regio Boskoop" for "Landgoed Clingendael" if the former doesn't resolve)

Re-run after each fix until all 267 features download successfully.

- [ ] **Step 3: Verify the bundle round-trips**

Run: `docker compose exec web python -c "
import json
from pathlib import Path
p = Path('features/management/commands/seed_data')
total = 0
for f in sorted(p.glob('*.geojson')):
    d = json.load(f.open())
    assert d['type'] == 'FeatureCollection'
    total += len(d['features'])
    print(f.name, len(d['features']))
print('TOTAL', total)
"`

Expected output:
```
canal.geojson 20
city.geojson 40
country.geojson 2
lake.geojson 30
nature_reserve.geojson 15
park.geojson 30
province.geojson 12
rail.geojson 20
river.geojson 30
road.geojson 30
town.geojson 40
TOTAL 269
```

---

## Task 12: Run the seeder end-to-end and verify the map

**Files:** none

- [ ] **Step 1: Wipe and re-seed the dev database**

Run: `docker compose exec web python manage.py seed_features`

Expected: `seed_features: created 269 features from .../seed_data`

- [ ] **Step 2: Sanity-check a few features in the API**

Run:
```bash
docker compose exec web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from features.models import Feature
for name in ['Bronkhorst', 'Amsterdam', 'Rijn', 'Veluwemeer', 'Netherlands']:
    f = Feature.objects.filter(properties__name=name).first()
    print(name, f.properties if f else 'MISSING')
"
```

Expected: each name prints a dict with `name`, `color`, `category`. `Bronkhorst` should have a `Point` geometry with `coordinates` near `(6.18, 52.08)` (its real location), NOT a random point in the sea.

- [ ] **Step 3: Verify the dev map shows real locations**

Open `http://127.0.0.1:8000/map/` in a browser, log in, and search for "Bronkhorst". The map should pan/zoom to Gelderland (not the Wadden Sea).

---

## Task 13: Update the Makefile

**Files:**
- Modify: `Makefile` (the `seed` target comment)

The Makefile `seed` target itself is unchanged (`python manage.py seed_features`). But the comment / context around it should reflect that no flags are needed.

- [ ] **Step 1: Verify the Makefile target still works**

Run: `make seed`

Expected: `seed_features: created 269 features from .../seed_data`

(No Makefile change is strictly required; the previous flags (`--count=1000`) were never in the Makefile. This step exists to confirm the target still works after the seeder rewrite.)

---

## Task 14: Final verification

**Files:** none

- [ ] **Step 1: Run the full test suite**

Run: `docker compose exec web pytest`

Expected: all tests pass (151 existing + ~13 new = ~164 total).

- [ ] **Step 2: Run pre-commit**

Run: `pre-commit run --all-files`

Expected: all 11 hooks pass.

- [ ] **Step 3: Quick smoke test of the E2E flow**

Open `http://127.0.0.1:8000/`, click "Map", search for a real feature (e.g. "Weerribben-Wieden", "Maas", "Friesland"), click the dropdown result, and confirm the map pans to a sensible location.
