"""Seed the database with a deterministic synthetic dataset of vector features.

Run via `python manage.py seed_features` (or `make seed`). Re-running
with the same `--seed` produces the exact same feature set
byte-for-byte (modulo the assigned UUIDs and timestamps). See
`docs/superpowers/specs/2026-06-12-geojson-seed.md` for the full
specification.
"""

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

UserModel = get_user_model()

DEFAULT_BBOX: Final[tuple[float, float, float, float]] = (3.3, 50.7, 7.3, 53.55)
"""The Netherlands in WGS84 (minx, miny, maxx, maxy).

Includes the mainland, the Wadden Islands, the Zeeland delta, and a
small slice of the North Sea; it does not include German or Belgian
land.
"""

DEFAULT_COUNT: Final[int] = 1000
"""The default total number of randomly-generated features (excludes the curated outline)."""

DEFAULT_SEED: Final[int] = 42
"""The default PRNG seed. Re-running with this seed produces the same feature set."""

BBOX_SAFETY_MARGIN: Final[float] = 0.05
"""The random center point is kept this many degrees inside the bbox on every side."""

COLOR_PALETTE: Final[tuple[str, ...]] = (
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#21468B",
)
"""The small color palette the seed draws `properties.color` from.

The NL-flag blue (`#21468B`) is reserved for the curated outline.
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
    "city": (
        "Amsterdam",
        "Rotterdam",
        "The Hague",
        "Utrecht",
        "Eindhoven",
        "Groningen",
        "Maastricht",
        "Arnhem",
        "Haarlem",
        "Delft",
        "Leiden",
        "Nijmegen",
        "Tilburg",
        "Almere",
        "Breda",
        "Apeldoorn",
        "Enschede",
        "Amersfoort",
        "Zwolle",
        "Deventer",
    ),
    "town": (
        "Lisse",
        "Valkenburg",
        "Edam",
        "Marken",
        "Volendam",
        "Giethoorn",
        "Urk",
        "Hindeloopen",
        "Naarden",
        "Willemstad",
        "Bergen",
        "Monnickendam",
        "Schoorl",
        "Woudrichem",
        "Heusden",
        "Hattem",
        "Stavoren",
        "Sloten",
        "Thorn",
        "Bronkhorst",
    ),
    "road": (
        "A1",
        "A2",
        "A4",
        "A6",
        "A7",
        "A9",
        "A10",
        "A12",
        "A15",
        "A16",
        "A20",
        "A27",
        "A28",
        "A29",
        "A30",
        "A31",
        "A32",
        "A35",
        "A37",
        "A38",
    ),
    "river": (
        "Rijn",
        "Maas",
        "IJssel",
        "Waal",
        "Lek",
        "Merwede",
        "Nederrijn",
        "Zwarte Water",
        "Vecht",
        "Dommel",
        "Mark",
        "Roer",
        "Geleenbeek",
        "Geul",
        "Jeker",
        "Swalm",
        "Beek",
        "Schelde",
        "Hollandse IJssel",
        "Oude Rijn",
    ),
    "canal": (
        "Noordhollandsch Kanaal",
        "Amsterdam-Rijnkanaal",
        "Maas-Waalkanaal",
        "Julianakanaal",
        "Noorzeekanaal",
        "Kanaal door Zuid-Beveland",
        "Kanaal door Walcheren",
        "Markkanaal",
        "Twentekanaal",
        "Zuid-Willemsvaart",
    ),
    "rail": (
        "HSL-Zuid",
        "Staatslijn A",
        "Staatslijn B",
        "Staatslijn C",
        "Staatslijn D",
        "Staatslijn E",
        "Staatslijn F",
        "Staatslijn G",
        "Staatslijn H",
        "Staatslijn K",
    ),
    "park": (
        "Veluwe",
        "Hoge Veluwe",
        "Utrechtse Heuvelrug",
        "Sallandse Heuvelrug",
        "Drents-Friese Wold",
        "Weerribben-Wieden",
        "Oostvaardersplassen",
        "Kennemerduinen",
        "Duinen van Texel",
        "Amsterdamse Bos",
    ),
    "lake": (
        "IJsselmeer",
        "Markermeer",
        "Veluwemeer",
        "Drontermeer",
        "Zwarte Meer",
        "Gooimeer",
        "Eemmeer",
        "Nuldernauw",
        "Wolderwijd",
        "Ketelmeer",
    ),
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
    "nature_reserve": (
        "Waddenzee",
        "Schiermonnikoog",
        "Vlieland",
        "Terschelling",
        "Ameland",
        "Schouwen-Duiveland",
        "Goeree-Overflakkee",
        "Voornes Duin",
        "Biesbosch",
        "Weerribben-Wieden",
    ),
}
"""Onomastic name pools, one per category. Names are unique within a category."""

# Geometry-type -> weight used by `random.choices` to pick the type.
GEOMETRY_TYPE_WEIGHTS: Final[dict[str, int]] = {
    "Point": 400,
    "LineString": 250,
    "Polygon": 200,
    "MultiPoint": 50,
    "MultiLineString": 50,
    "MultiPolygon": 50,
}
"""The geometry-type distribution from the Seed spec §3. The total is 1000 random features."""


def _generate_point(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> Point:
    """Generate a single-point geometry at the chosen center."""
    return Point(center_x, center_y, srid=4326)


def _generate_multi_point(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> MultiPoint:
    """Generate 3-8 points, each a small random offset from the center."""
    point_count = random_generator.randint(3, 8)
    points = tuple(
        Point(
            center_x + random_generator.uniform(-0.3, 0.3),
            center_y + random_generator.uniform(-0.3, 0.3),
            srid=4326,
        )
        for _ in range(point_count)
    )
    return MultiPoint(points, srid=4326)


def _generate_line_string(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> LineString:
    """Generate 2-10 positions along a roughly straight line, jittered."""
    vertex_count = random_generator.randint(2, 10)
    heading_x = random_generator.uniform(-1.0, 1.0)
    heading_y = random_generator.uniform(-1.0, 1.0)
    positions = tuple(
        (
            center_x + heading_x * step_index + random_generator.uniform(-0.1, 0.1),
            center_y + heading_y * step_index + random_generator.uniform(-0.1, 0.1),
        )
        for step_index in range(vertex_count)
    )
    return LineString(positions, srid=4326)


def _generate_multi_line_string(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> MultiLineString:
    """Generate 2-4 LineStrings, each 2-8 positions."""
    line_count = random_generator.randint(2, 4)
    lines = tuple(_generate_line_string(random_generator, bbox, center_x, center_y) for _ in range(line_count))
    return MultiLineString(lines, srid=4326)


def _generate_polygon(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> Polygon:
    """Generate a single closed ring of 3-8 positions, returning to the start point.

    RFC 7946 §3.1.6 requires a linear ring to have at least 4
    positions (3 distinct + the closing position equal to the first).
    GEOS's `GEOSGeom_createLinearRing_r` rejects rings whose first
    and last positions are not equal, so the first position is
    appended explicitly at the end.
    """
    vertex_count = random_generator.randint(3, 8)
    ring_radius = 0.2
    ring_positions = [
        (
            center_x
            + ring_radius * math.cos(2 * math.pi * vertex_index / vertex_count)
            + random_generator.uniform(-0.05, 0.05),
            center_y
            + ring_radius * math.sin(2 * math.pi * vertex_index / vertex_count)
            + random_generator.uniform(-0.05, 0.05),
        )
        for vertex_index in range(vertex_count)
    ]
    ring_positions.append(ring_positions[0])
    return Polygon(tuple(ring_positions), srid=4326)


def _generate_multi_polygon(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> MultiPolygon:
    """Generate 2-3 simple closed rings, each 3-8 positions."""
    polygon_count = random_generator.randint(2, 3)
    polygons = tuple(_generate_polygon(random_generator, bbox, center_x, center_y) for _ in range(polygon_count))
    return MultiPolygon(polygons, srid=4326)


GEOMETRY_GENERATORS: Final[dict[str, object]] = {
    "Point": _generate_point,
    "MultiPoint": _generate_multi_point,
    "LineString": _generate_line_string,
    "MultiLineString": _generate_multi_line_string,
    "Polygon": _generate_polygon,
    "MultiPolygon": _generate_multi_polygon,
}
"""Maps a geometry-type name to its `_generate_*` helper.

`GeometryCollection` is curated-only and is not in this table.
"""


NETHERLANDS_OUTLINE_RING: Final[tuple[tuple[float, float], ...]] = (
    (3.35, 51.85),
    (3.45, 51.75),
    (3.55, 51.65),
    (3.75, 51.55),
    (4.10, 51.40),
    (4.20, 51.25),
    (4.30, 51.10),
    (4.10, 51.00),
    (4.00, 50.90),
    (4.20, 50.85),
    (4.55, 50.80),
    (4.80, 50.75),
    (5.00, 50.75),
    (5.30, 50.80),
    (5.65, 50.85),
    (5.85, 50.95),
    (6.10, 50.95),
    (6.30, 50.85),
    (6.50, 50.80),
    (6.70, 50.75),
    (6.95, 50.75),
    (7.05, 50.90),
    (7.10, 51.10),
    (6.95, 51.30),
    (6.85, 51.55),
    (6.70, 51.80),
    (6.55, 52.05),
    (6.40, 52.30),
    (6.25, 52.55),
    (5.95, 52.85),
    (5.65, 53.15),
    (5.30, 53.35),
    (4.90, 53.45),
    (4.55, 53.50),
    (4.10, 53.50),
    (3.80, 53.45),
    (3.55, 53.40),
    (3.40, 53.25),
    (3.35, 53.00),
    (3.35, 52.75),
    (3.35, 52.50),
    (3.40, 52.20),
    (3.45, 51.95),
    (3.35, 51.85),
)
"""~44-vertex ring approximating the mainland NL land border."""

WADDEN_ISLANDS_RING: Final[tuple[tuple[float, float], ...]] = (
    (4.70, 53.40),
    (4.85, 53.30),
    (5.05, 53.20),
    (5.30, 53.15),
    (5.55, 53.15),
    (5.80, 53.20),
    (5.95, 53.30),
    (5.95, 53.40),
    (5.75, 53.45),
    (5.45, 53.45),
    (5.15, 53.45),
    (4.90, 53.45),
    (4.70, 53.40),
)
"""A small ring approximating the Wadden Islands as a single polygon."""

ZEELAND_RING: Final[tuple[tuple[float, float], ...]] = (
    (3.45, 51.65),
    (3.55, 51.55),
    (3.75, 51.45),
    (3.95, 51.40),
    (4.15, 51.40),
    (4.30, 51.45),
    (4.30, 51.55),
    (4.10, 51.60),
    (3.85, 51.65),
    (3.65, 51.70),
    (3.45, 51.65),
)
"""A ring approximating the Zeeland delta as a single polygon."""

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
    """`python manage.py seed_features` — populate the DB with the demo dataset."""

    help = "Populate the database with a deterministic synthetic dataset of vector features."

    def add_arguments(self, parser: object) -> None:
        """Declare the four flags described in the Seed spec §2."""
        parser.add_argument(  # type: ignore[attr-defined]
            "--bbox",
            type=str,
            default=",".join(str(coordinate) for coordinate in DEFAULT_BBOX),
            help=(
                "Generation region as 'minx,miny,maxx,maxy' (WGS84). "
                "Validated by features.filters.parse_bbox. "
                f"Default: {','.join(str(coordinate) for coordinate in DEFAULT_BBOX)} (Netherlands)."
            ),
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help=f"Number of randomly-generated features. Default: {DEFAULT_COUNT}.",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"PRNG seed for deterministic generation. Default: {DEFAULT_SEED}.",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--keep",
            action="store_true",
            help=(
                "Explicit no-op: the default behavior is to truncate and re-seed only "
                "the Feature rows and leave accounts_user alone. The flag is retained "
                "for explicit clarity and for a future flag that re-seeds users."
            ),
        )

    def handle(self, *args: object, **options: object) -> None:
        """Delete the existing Feature rows and re-seed with the deterministic dataset."""
        raw_bbox = options["bbox"]  # type: ignore[index]
        raw_count = options["count"]  # type: ignore[index]
        raw_seed = options["seed"]  # type: ignore[index]

        try:
            bbox = parse_bbox(raw_bbox)  # type: ignore[arg-type]
        except Exception as exc:
            raise CommandError(f"Invalid --bbox: {exc}") from exc

        feature_count = int(raw_count)  # type: ignore[arg-type]
        if feature_count <= 0:
            raise CommandError("--count must be a positive integer")

        seed_value = int(raw_seed)  # type: ignore[arg-type]

        Feature.objects.all().delete()

        features = _run_seed(
            bbox=bbox,
            feature_count=feature_count,
            seed=seed_value,
        )
        Feature.objects.bulk_create(features, batch_size=500)

        self.stdout.write(
            f"seed_features: created {len(features)} features (count={feature_count}, seed={seed_value}, bbox={bbox})"
        )


def _run_seed(
    bbox: tuple[float, float, float, float],
    feature_count: int,
    seed: int,
) -> list[Feature]:
    """Generate the list of Feature objects (random + curated) for the given parameters.

    The order matters: the curated Netherlands outline is appended
    last so the frontend renders it on top of the random features
    (per Seed spec §4).
    """
    min_x, min_y, max_x, max_y = bbox
    shrunken_min_x = min_x + BBOX_SAFETY_MARGIN
    shrunken_min_y = min_y + BBOX_SAFETY_MARGIN
    shrunken_max_x = max_x - BBOX_SAFETY_MARGIN
    shrunken_max_y = max_y - BBOX_SAFETY_MARGIN

    random_generator = random.Random(seed)
    geometry_type_names = list(GEOMETRY_TYPE_WEIGHTS.keys())
    geometry_type_weights = list(GEOMETRY_TYPE_WEIGHTS.values())

    used_names_by_category: dict[str, set[str]] = {category: set() for category in NAME_POOLS}
    seed_creator_id = _first_registered_user_id()

    features: list[Feature] = []
    for _ in range(feature_count):
        geometry_type_name = random_generator.choices(
            population=geometry_type_names,
            weights=geometry_type_weights,
            k=1,
        )[0]

        applicable_categories = [
            category
            for category, allowed_types in CATEGORY_TO_GEOMETRY_TYPES.items()
            if geometry_type_name in allowed_types and category != "country"
        ]
        chosen_category = random_generator.choice(applicable_categories)

        name_pool = NAME_POOLS[chosen_category]
        available_names = [name for name in name_pool if name not in used_names_by_category[chosen_category]]
        if not available_names:
            available_names = list(name_pool)
        chosen_name = random_generator.choice(available_names)
        used_names_by_category[chosen_category].add(chosen_name)

        chosen_color = random_generator.choice(COLOR_PALETTE)

        center_x = random_generator.uniform(shrunken_min_x, shrunken_max_x)
        center_y = random_generator.uniform(shrunken_min_y, shrunken_max_y)
        geometry = GEOMETRY_GENERATORS[geometry_type_name](
            random_generator=random_generator,
            bbox=bbox,
            center_x=center_x,
            center_y=center_y,
        )

        feature = Feature(
            geometry=geometry,
            properties={
                "name": chosen_name,
                "color": chosen_color,
                "category": chosen_category,
            },
            created_by_id=seed_creator_id,
        )
        features.append(feature)

    features.extend(_build_curated_features(seed_creator_id=seed_creator_id))
    return features


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
