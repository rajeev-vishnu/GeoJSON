"""Seed the database with a real-coordinate dataset of vector features.

Run via `python manage.py seed_features` (or `docker compose exec web python manage.py seed_features`). The seeder
loads from `seed_data/*.geojson` (a bundle of OpenStreetMap-sourced
features) and bulk-creates `Feature` rows. See
`docs/superpowers/specs/2026-06-15-geojson-real-seed-data-design.md`
for the full specification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import (
    GEOSGeometry,
    MultiPolygon,
    Polygon,
)
from django.core.management.base import BaseCommand, CommandError

from features.models import Feature

UserModel = get_user_model()

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

# Category -> set of geometry-type names that may use it.
# Mirrors the table in the Seed spec §5.
CATEGORY_TO_GEOMETRY_TYPES: Final[dict[str, frozenset[str]]] = {
    "city": frozenset({"Point", "MultiPoint"}),
    "town": frozenset({"Point", "MultiPoint"}),
    "road": frozenset({"LineString", "MultiLineString"}),
    "river": frozenset({"LineString", "MultiLineString"}),
    "canal": frozenset({"LineString"}),
    "rail": frozenset({"LineString", "MultiLineString"}),
    "park": frozenset({"Polygon"}),
    "lake": frozenset({"Polygon"}),
    "province": frozenset({"Polygon", "MultiPolygon"}),
    "nature_reserve": frozenset({"MultiPolygon"}),
    "country": frozenset({"MultiPolygon", "GeometryCollection"}),
}
"""The set of GeoJSON geometry types a `properties.category` value is allowed to attach to.

The seed picks a category from the values that apply to the chosen
geometry type. The `country` category is reserved for the curated
features and is never assigned to random features.
"""

# Category -> ordered tuple of human names. Names are unique within
# a category so the search dropdown has distinguishable results.
NAME_POOLS: Final[dict[str, tuple[str, ...]]] = {
    "city": ("Amsterdam", "Rotterdam", "Den Haag", "Utrecht", "Eindhoven"),
    "town": ("Edam", "Volendam", "Giethoorn"),
    "road": ("A1", "A2", "A4"),
    "river": ("Rijn", "Maas", "IJssel"),
    "canal": ("Noordzeekanaal", "Amsterdam-Rijnkanaal"),
    "rail": ("Staatslijn A", "HSL-Zuid"),
    "park": ("Veluwe", "Hoge Veluwe", "Amsterdamse Bos"),
    "lake": ("IJsselmeer", "Markermeer", "Veluwemeer"),
    "province": (
        "Groningen",
        "Friesland",
        "Drenthe",
        "Overijssel",
        "Flevoland",
        "Gelderland",
        "Utrecht",
        "Noord-Holland",
        "Zuid-Holland",
        "Zeeland",
        "Noord-Brabant",
        "Limburg",
    ),
    "nature_reserve": ("Waddenzee", "Biesbosch", "De Maasduinen"),
}
"""Onomastic name pools, one per category. Names are unique within a category.

Total: 5+3+3+3+2+2+3+3+12+3 = 39 real features, plus 2 curated
`country` features = 41 total.

The `country` category is intentionally NOT in this table — the
curated NL outline and Caribbean collection live in
`seed_data/country.geojson`, not in a name pool.
"""


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


_SEED_DATA_DIR_OVERRIDE: Path | None = None
"""Test hook: when set, `_load_bundle` reads from this directory instead of the bundled `seed_data/`.

Tests monkey-patch this module variable to swap in a fixture bundle
without copying files. The download command does not touch it.
"""


def _load_bundle(seed_data_dir: Path) -> list[tuple[str, dict]]:
    """Read every `seed_data/<file>.geojson` in `SEED_DATA_FILES` and return (category, feature) pairs.

    Each file is a GeoJSON `FeatureCollection`. This function returns
    a flat list of `(category, feature_dict)` tuples — the caller is
    responsible for constructing `Feature` model instances.

    `seed_data_dir` is the path to the directory containing the
    GeoJSON files; it defaults to the `seed_data/` directory next to
    this module. Pass an explicit path in tests, or set
    `_SEED_DATA_DIR_OVERRIDE` to swap in a fixture bundle.
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
        features.extend((category, feature) for feature in collection.get("features", []))
    return features


NETHERLANDS_OUTLINE_RING: Final[tuple[tuple[float, float], ...]] = (
    (4.65, 52.78),
    (4.70, 52.85),
    (4.75, 52.95),
    (4.85, 52.98),
    (5.05, 52.93),
    (5.20, 52.92),
    (5.40, 52.95),
    (5.55, 53.00),
    (5.70, 53.05),
    (5.85, 53.10),
    (6.05, 53.18),
    (6.20, 53.20),
    (6.35, 53.05),
    (6.55, 52.90),
    (6.75, 52.75),
    (6.95, 52.55),
    (7.10, 52.35),
    (7.20, 52.15),
    (7.05, 52.00),
    (6.85, 51.85),
    (6.55, 51.80),
    (6.25, 51.80),
    (6.05, 51.80),
    (5.92, 50.78),
    (5.85, 50.82),
    (5.78, 50.85),
    (5.68, 50.85),
    (5.55, 50.90),
    (5.40, 51.00),
    (5.20, 51.10),
    (5.00, 51.15),
    (4.80, 51.20),
    (4.55, 51.25),
    (4.30, 51.30),
    (4.10, 51.35),
    (3.85, 51.38),
    (3.60, 51.40),
    (3.70, 51.40),
    (3.90, 51.40),
    (4.10, 51.40),
    (4.25, 51.42),
    (4.35, 51.45),
    (4.45, 51.55),
    (4.50, 51.70),
    (4.50, 51.85),
    (4.45, 52.00),
    (4.35, 52.15),
    (4.25, 52.30),
    (4.20, 52.50),
    (4.20, 52.65),
    (4.30, 52.80),
    (4.65, 52.78),
)
"""~52-vertex ring approximating the mainland NL land border, traced clockwise from the NW coast.

The southwestern section deliberately avoids the Zeeland polygon's
bounding box (which is a separate polygon) by hugging the inland side
of the islands rather than tracing the actual coastline through them.
"""

WADDEN_ISLANDS_RING: Final[tuple[tuple[float, float], ...]] = (
    (4.75, 53.05),
    (4.80, 53.10),
    (4.85, 53.18),
    (4.95, 53.25),
    (5.05, 53.30),
    (5.20, 53.40),
    (5.40, 53.45),
    (5.55, 53.50),
    (5.75, 53.50),
    (5.95, 53.50),
    (6.15, 53.50),
    (6.25, 53.45),
    (6.20, 53.35),
    (6.00, 53.30),
    (5.75, 53.35),
    (5.45, 53.30),
    (5.20, 53.25),
    (4.95, 53.15),
    (4.80, 53.05),
    (4.75, 53.05),
)
"""A chain-shaped ring approximating the Wadden Islands as a single elongated polygon."""

ZEELAND_RING: Final[tuple[tuple[float, float], ...]] = (
    (3.55, 51.48),
    (3.60, 51.55),
    (3.65, 51.62),
    (3.75, 51.70),
    (3.90, 51.74),
    (4.05, 51.74),
    (4.18, 51.70),
    (4.25, 51.62),
    (4.25, 51.55),
    (4.18, 51.50),
    (4.05, 51.48),
    (3.90, 51.46),
    (3.75, 51.46),
    (3.65, 51.47),
    (3.55, 51.48),
)
"""A ring approximating the Zeeland delta islands as a single polygon."""

NETHERLANDS_OUTLINE_MULTIPOLYGON: Final[MultiPolygon] = MultiPolygon(
    (
        Polygon(NETHERLANDS_OUTLINE_RING, srid=4326),
        Polygon(WADDEN_ISLANDS_RING, srid=4326),
        Polygon(ZEELAND_RING, srid=4326),
    ),
    srid=4326,
)
"""The hand-shaped Netherlands outline: mainland + Wadden Islands + Zeeland."""

CARIBBEAN_NETHERLANDS_COLLECTION: Final[GEOSGeometry] = GEOSGeometry(
    ("GEOMETRYCOLLECTION (POINT (-68.25 12.10),POINT (-62.97 17.49),POINT (-63.23 18.03))"),
    srid=4326,
)
"""Three `Point`s at the actual WGS84 coordinates of Bonaire, Sint Eustatius, and Saba."""


def _build_curated_features(seed_creator_id: int | None) -> list[Feature]:
    """Return the two curated features (Netherlands outline + Caribbean collection) for the seed run.

    Both features share the same `properties.color` (the NL-flag blue)
    and `properties.category` ("country"). The `created_by` is set to
    the first registered user (by `id` order) if any user exists,
    else `None` — see the "created_by choice" note at the top of
    this plan.
    """
    netherlands_properties = {
        "name": "Netherlands",
        "color": "#21468B",
        "category": "country",
    }
    caribbean_properties = {
        "name": "Caribbean Netherlands",
        "color": "#21468B",
        "category": "country",
    }

    netherlands_feature = Feature(
        geometry=NETHERLANDS_OUTLINE_MULTIPOLYGON,
        properties=netherlands_properties,
        created_by_id=seed_creator_id,
    )
    caribbean_feature = Feature(
        geometry=CARIBBEAN_NETHERLANDS_COLLECTION,
        properties=caribbean_properties,
        created_by_id=seed_creator_id,
    )

    return [netherlands_feature, caribbean_feature]


class Command(BaseCommand):
    """`python manage.py seed_features` — load real-coordinate features from the bundle."""

    help = "Delete all Feature rows and reload them from seed_data/*.geojson."

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

        self.stdout.write(f"seed_features: created {len(features_to_create)} features from {seed_data_dir}")


def _first_registered_user_id() -> int | None:
    """Return the primary key of the lexicographically-first registered user, or `None` if no users exist.

    The `accounts.User` model has no `date_joined` or `created_at`
    field, so ordering by `id` (a UUID) is the only available stable
    order. UUIDs are random per registration, so this is stable
    within a run but not across runs — which is fine for the seed
    (the spec says UUIDs and timestamps vary by run).
    """
    first_user = UserModel.objects.order_by("id").first()
    if first_user is None:
        return None
    return first_user.pk
