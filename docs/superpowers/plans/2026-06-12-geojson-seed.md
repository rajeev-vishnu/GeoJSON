# GeoJSON Seed Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `features/management/commands/seed_features.py` Django management command that populates the database with a deterministic synthetic dataset of 1,000 vector features (plus a curated "Netherlands outline" `MultiPolygon` and a "Caribbean Netherlands" `GeometryCollection`) covering all 7 standard GeoJSON geometry types, with exactly the three properties `name`, `color`, and `category`.

**Architecture:** A single Django management command (`BaseCommand` subclass) at `features/management/commands/seed_features.py`. The command takes four flags (`--bbox`, `--count`, `--seed`, `--keep`) and follows the lifecycle: (1) parse + validate `parse_bbox()` from the new `features/filters.py` module, (2) build a single `random.Random(seed)` instance, (3) generate 1,000 features by weighted pick from the geometry-type distribution, with onomastic name pools + a small color palette, (4) append the curated `MultiPolygon` (Netherlands outline) and the curated `GeometryCollection` (Caribbean Netherlands), (5) `Feature.objects.all().delete()` (default; skip when `--keep` is set) and `Feature.objects.bulk_create(features, batch_size=500)`. `parse_bbox()` is shared with the future Feature API spec — the Feature API plan (not yet written) will import it from `features/filters.py` as a single source of truth, so the seed plan owns the implementation now.

**Tech Stack:** Python 3.12, Django 5.1.x management commands, `rest_framework_gis.geometry` (`serializer_helpers`-style geometry wrapping via `GEOSGeometry`), `random.Random` for deterministic PRNG, `bulk_create` for the insert, `call_command` + `pytest.mark.django_db` for the test suite, ruff + pre-commit for the lint gate.

**Working-tree convention:** Per AGENTS.md, the project's pre-commit gate is the only commit boundary. This plan intentionally **omits `git commit` steps** so all changes stay unstaged at the end; the engineer (or a follow-up plan) runs the full pre-commit gate at the end and stages/commits then. Each task ends with a brief status note in place of a commit.

**Test-environment settings module:** The Docker image sets `DJANGO_SETTINGS_MODULE=config.settings.prod` (this is the production setting used by gunicorn). Running tests inside the container via `docker compose run --rm web pytest` therefore uses **prod settings**, which has `SECURE_SSL_REDIRECT=True` and breaks the API tests. The Makefile's `test` target sets `DJANGO_SETTINGS_MODULE=config.settings.test` explicitly on the `run` invocation. **Always run pytest via `make test` (or `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest`)** — not via `docker compose exec web pytest` from a `web` container that was started with `manage.py runserver` (those use prod settings).

**Shared parse_bbox placement:** The Seed spec says the `--bbox` flag is "Validated by the same `parse_bbox()` used by the API filter." The [Feature API spec §4](./2026-06-12-geojson-feature-api.md#4-bbox-filter) declares `parse_bbox()` lives in `features/filters.py`. The Feature API plan has not yet been written. To keep both specs aligned with a single source of truth, the seed plan **creates `features/filters.py` with `parse_bbox()` now** (TDD: failing test first). The future Feature API plan will find the function already there and import it directly — no refactor needed.

**The `created_by` choice for the seed:** The spec says features are saved with "`created_by=<first registered user or None>`." The `accounts.User` model has no `date_joined` or `created_at` field (see `accounts/models.py`), so the order is by `id` (UUID) — stable within a run but not across runs. The test `test_seed_keep_preserves_users` only asserts user rows are not deleted, not which user is the creator, so the choice of `User.objects.order_by("id").first()` is sufficient and deterministic per run.

---

## File map

### Create

- `features/filters.py` — `parse_bbox(raw: str) -> tuple[float, float, float, float]` per the Feature API spec §4; raises `rest_framework.exceptions.ValidationError` on bad input. The Seed command imports this for `--bbox` validation. The future Feature API spec re-uses this module.
- `features/tests/test_filters.py` — unit tests for `parse_bbox()` (valid input, wrong arity, non-numeric, out-of-range coords, swapped mins/maxes, empty string).
- `features/management/__init__.py` — package marker (explicit, even though Django will auto-create it).
- `features/management/commands/__init__.py` — package marker (Django auto-discovers commands under this directory).
- `features/management/commands/seed_features.py` — the `Command(BaseCommand)` class with constants (`DEFAULT_BBOX`, `DEFAULT_COUNT`, `DEFAULT_SEED`), the category-to-geometry mapping, the onomastic name pools, the color palette, the geometry generators (one per type), the curated-outline constants, and the `handle()` orchestration.
- `features/tests/management/__init__.py` — package marker.
- `features/tests/management/test_seed_features.py` — 5 tests (all 7 geometry types present, curated outline + Caribbean collection present, exactly 3 properties, idempotent, `--keep` preserves users).

### Modify

- `Makefile:14-15` (`make seed` target) — the existing `make seed` already calls `seed_features` with no flags; this works as-is. No change needed. (Documented for the executing engineer; no file edit.)

### Touchpoints left for downstream specs

- `features/filters.py` exposes `parse_bbox()` (this plan creates it). The future Feature API spec imports it directly. If the Feature API spec also wants `apply_bbox(queryset, bbox)` (a separate helper from the Feature API spec §4), that helper lands in a follow-up plan and uses `parse_bbox()` internally.
- The `make seed` target already calls `python manage.py seed_features` with no flags; it picks up the default `--count=1000 --seed=42 --bbox=3.3,50.7,7.3,53.55` and produces 1,001 features (1,000 random + 1 curated outline + 1 curated Caribbean collection). The default behavior (truncate `Feature` rows, leave `accounts_user` alone) matches the existing target's intent.

### Cross-spec corrections to apply when those plans/specs land

- The [Feature API spec §4](./2026-06-12-geojson-feature-api.md#4-bbox-filter) says `parse_bbox()` lives in `features/filters.py` and raises `ValidationError`. The seed plan now creates that module. The Feature API plan (not yet written) should **not** re-create the module — it should import `from features.filters import parse_bbox` and add `apply_bbox(queryset, bbox)` next to it.

---

## Project conventions (per `AGENTS.md`)

All code in this plan follows these conventions:

- **Keyword arguments** for any function call with more than one argument. The only exception is positional-only parameters (e.g. builtins like `print()`).
- **Function ordering** — public / entry-point functions first; private helper functions below the functions that call them.
- **Blank line after dedent** — when the indentation level decreases (after a `with` block, `for` loop, or `if` branch), add a blank line before the next statement at the outer level.
- **Nesting depth** — avoid more than 3 levels of indentation. Refactor into smaller functions or use early returns to reduce nesting.
- **Naming** — follow PEP 8 naming conventions. Avoid shortened variable names: `hf`, `c`, `tmp`, `res`, `obj`, etc. The seed file uses full names like `feature_count`, `random_generator`, `category_pool`, `geometry_type`, `center_x`, `center_y`.
- **Imports** — inline / local imports need to be strictly avoided. If it is unavoidable or is needed for lazy loading, request for explicit approval.
- **Function length** — keep functions under ~100 lines. The seed command's `handle()` is the longest function (≈40 lines including delete + generate + bulk_create + stdout).
- **No comments in code blocks** — only docstrings on functions. `# noqa` directives are allowed.
- **Pre-commit gate** is the only commit boundary. There is no `git commit` step in this plan. The pre-commit gate runs once at the end of Task 8.

---

## Tasks

### Task 1: Create `parse_bbox()` in `features/filters.py` (TDD)

**Files:**
- Create: `features/filters.py`
- Create: `features/tests/test_filters.py`

The seed command's `--bbox` flag is validated by `parse_bbox()` (per the spec table in §2 and the Feature API spec §4). The validation rules from the Feature API spec §4 are:

- Exactly 4 comma-separated floats.
- `minx`, `maxx` in `[-180, 180]`.
- `miny`, `maxy` in `[-90, 90]`.
- `minx <= maxx`, `miny <= maxy`.

The function raises `rest_framework.exceptions.ValidationError` (DRF's `ValidationError` is a `std::exception` subclass that DRF views can catch; the seed command catches and re-formats for its own `CommandError`). We write the failing test first (TDD), then the implementation.

- [ ] **Step 1: Write the failing `parse_bbox` tests**

Write the following to `features/tests/test_filters.py`:

```python
"""Tests for the bbox parser used by the seed command and the API filter."""

from __future__ import annotations

import pytest
from rest_framework.exceptions import ValidationError

from features.filters import parse_bbox

pytestmark = pytest.mark.django_db


def test_parse_bbox_accepts_valid_input() -> None:
    """A well-formed 'minx,miny,maxx,maxy' string returns the four floats in order."""
    assert parse_bbox("3.3,50.7,7.3,53.55") == (3.3, 50.7, 7.3, 53.55)


def test_parse_bbox_accepts_negative_coordinates() -> None:
    """Western and southern hemisphere coordinates parse correctly."""
    assert parse_bbox("-180.0,-90.0,180.0,90.0") == (-180.0, -90.0, 180.0, 90.0)


def test_parse_bbox_accepts_integer_floats() -> None:
    """Coordinates expressed as integer strings parse to floats."""
    assert parse_bbox("0,0,10,10") == (0.0, 0.0, 10.0, 10.0)


def test_parse_bbox_rejects_wrong_arity() -> None:
    """A string with fewer than 4 comma-separated values raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("1.0,2.0,3.0")


def test_parse_bbox_rejects_too_many_values() -> None:
    """A string with more than 4 comma-separated values raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("1.0,2.0,3.0,4.0,5.0")


def test_parse_bbox_rejects_non_numeric() -> None:
    """A non-numeric value raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("a,b,c,d")


def test_parse_bbox_rejects_longitude_out_of_range() -> None:
    """minx or maxx outside [-180, 180] raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("200.0,0.0,210.0,10.0")


def test_parse_bbox_rejects_latitude_out_of_range() -> None:
    """miny or maxy outside [-90, 90] raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("0.0,100.0,10.0,110.0")


def test_parse_bbox_rejects_swapped_longitude() -> None:
    """minx > maxx raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("10.0,0.0,5.0,10.0")


def test_parse_bbox_rejects_swapped_latitude() -> None:
    """miny > maxy raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("0.0,10.0,10.0,5.0")


def test_parse_bbox_rejects_empty_string() -> None:
    """An empty string raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox("")


def test_parse_bbox_rejects_whitespace_only() -> None:
    """A whitespace-only string raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_bbox(" , , , ")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_filters.py -v`

Expected: collection error — `ModuleNotFoundError: No module named 'features.filters'`. The `features/filters.py` module does not exist yet.

- [ ] **Step 3: Implement `parse_bbox`**

Write the following to `features/filters.py`:

```python
"""Bbox parsing and filtering for the seed command and the API filter.

The seed command's `--bbox` flag and the API's `?bbox=` filter both
call `parse_bbox()` to validate user input. The Feature API spec §4
defines the validation rules: exactly 4 comma-separated floats with
`minx <= maxx`, `miny <= maxy`, longitude in `[-180, 180]`, latitude
in `[-90, 90]`. Bad input raises DRF's `ValidationError` so the seed
command can re-wrap it as a `CommandError` and the API view can
return a 400 response without additional translation.
"""

from __future__ import annotations

from rest_framework.exceptions import ValidationError


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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/test_filters.py -v`

Expected: all 12 tests pass.

- [ ] **Step 5: Status note**

`features/filters.py` and `features/tests/test_filters.py` are left unstaged.

---

### Task 2: Create the management command package and write the 5 failing seed tests

**Files:**
- Create: `features/management/__init__.py`
- Create: `features/management/commands/__init__.py`
- Create: `features/tests/management/__init__.py`
- Create: `features/tests/management/test_seed_features.py`

Write the 5 tests from the Seed spec §8. They will all fail at the `call_command(...)` step (or the import step, since the command module does not exist yet).

- [ ] **Step 1: Create the package markers**

Create three empty-package markers:

`features/management/__init__.py`:
```python
"""Management commands for the features app."""  # noqa: D104
```

`features/management/commands/__init__.py`:
```python
"""Django discovers management commands under this package."""  # noqa: D104
```

`features/tests/management/__init__.py`:
```python
"""Package marker for the management-command test suite."""  # noqa: D104
```

(The `# noqa: D104` matches the project's existing convention for one-line `__init__.py` docstrings.)

- [ ] **Step 2: Write the 5 failing seed tests**

Write the following to `features/tests/management/test_seed_features.py`:

```python
"""Tests for the seed_features management command: idempotency, curated rows, properties shape."""

from __future__ import annotations

from collections import Counter
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.contrib.gis.geos import GEOSGeometry
from django.core.management import call_command
from django.db import connection

from accounts.models import User
from features.models import Feature

if TYPE_CHECKING:
    from django.contrib.gis.geos import GEOSGeometry as _GEOSGeometry

pytestmark = pytest.mark.django_db


def _run_seed(*args: str) -> None:
    """Run `python manage.py seed_features <args>` against the test database.

    Captures stdout to a StringIO so the tests can stay quiet; the
    command's text output is not under test here.
    """
    call_command("seed_features", *args, stdout=StringIO())


def test_seed_creates_all_geometry_types() -> None:
    """Running seed_features with the default --count=1000 --seed=42 produces at least one Feature of each of the 7 GeoJSON geometry types."""
    _run_seed("--count=1000", "--seed=42")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ST_GeometryType(geometry) FROM features_feature",
        )
        geometry_type_rows = cursor.fetchall()

    geometry_types_in_seed = {row[0] for row in geometry_type_rows}

    expected_geometry_types = {
        "ST_Point",
        "ST_MultiPoint",
        "ST_LineString",
        "ST_MultiLineString",
        "ST_Polygon",
        "ST_MultiPolygon",
        "ST_GeometryCollection",
    }

    assert expected_geometry_types.issubset(geometry_types_in_seed), (
        f"Missing geometry types: {expected_geometry_types - geometry_types_in_seed}"
    )


def test_seed_curated_outline() -> None:
    """The curated 'Netherlands' MultiPolygon and the 'Caribbean Netherlands' GeometryCollection are present with the expected properties."""
    _run_seed("--count=1000", "--seed=42")

    netherlands_feature = Feature.objects.filter(properties__name="Netherlands").get()
    caribbean_feature = Feature.objects.filter(properties__name="Caribbean Netherlands").get()

    assert netherlands_feature.properties["name"] == "Netherlands"
    assert netherlands_feature.properties["category"] == "country"
    assert netherlands_feature.properties["color"] == "#21468B"
    assert netherlands_feature.geometry.geom_type == "MultiPolygon"

    assert caribbean_feature.properties["name"] == "Caribbean Netherlands"
    assert caribbean_feature.properties["category"] == "country"
    assert caribbean_feature.properties["color"] == "#21468B"
    assert caribbean_feature.geometry.geom_type == "GeometryCollection"


def test_seed_exactly_three_properties() -> None:
    """Every seeded Feature has exactly the three properties 'name', 'color', and 'category' — no extras, no missing keys."""
    _run_seed("--count=1000", "--seed=42")

    property_key_counts: Counter[str] = Counter()
    for feature in Feature.objects.all():
        property_key_counts[len(feature.properties)] += 1
        assert set(feature.properties.keys()) == {"name", "color", "category"}, (
            f"Feature {feature.pk} has unexpected properties: {sorted(feature.properties.keys())}"
        )

    assert property_key_counts[3] == Feature.objects.count()


def test_seed_is_idempotent() -> None:
    """Running seed_features twice with the same --seed produces the same total count, and the curated outline is still present on the second run."""
    _run_seed("--count=1000", "--seed=42")
    first_run_count = Feature.objects.count()
    assert first_run_count == 1001

    _run_seed("--count=1000", "--seed=42")
    second_run_count = Feature.objects.count()
    assert second_run_count == first_run_count

    assert Feature.objects.filter(properties__name="Netherlands").exists()
    assert Feature.objects.filter(properties__name="Caribbean Netherlands").exists()


def test_seed_keep_preserves_users() -> None:
    """Running seed_features with --keep does not delete any accounts_user rows."""
    User.objects.create_user(email="alice@example.com", password="correct-horse-battery-staple")
    User.objects.create_user(email="bob@example.com", password="correct-horse-battery-staple")
    user_emails_before = sorted(User.objects.values_list("email", flat=True))

    _run_seed("--count=1000", "--seed=42", "--keep")

    user_emails_after = sorted(User.objects.values_list("email", flat=True))

    assert user_emails_after == user_emails_before
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/management/test_seed_features.py -v`

Expected: collection error — `ModuleNotFoundError: No module named 'features.management'`. The `features/management/` package does not exist yet.

If only the command-import fails (the management package is there but the command is not), the error will be `Unknown command: 'seed_features'`. Both outcomes correctly prove the command does not exist yet.

- [ ] **Step 4: Status note**

`features/management/__init__.py`, `features/management/commands/__init__.py`, `features/tests/management/__init__.py`, and `features/tests/management/test_seed_features.py` are left unstaged.

---

### Task 3: Implement the seed command skeleton with constants, category-to-geometry map, onomastic pools, and color palette

**Files:**
- Create: `features/management/commands/seed_features.py`

This task creates the command file with the public surface (the `Command` class, `add_arguments`, an empty `handle()`) and the private data structures the rest of the implementation will use. None of the 5 tests pass yet (because the implementation does nothing), but the command can be invoked without error.

- [ ] **Step 1: Create `features/management/commands/seed_features.py` with the skeleton and data tables**

Write the following to `features/management/commands/seed_features.py`:

```python
"""Seed the database with a deterministic synthetic dataset of vector features.

Run via `python manage.py seed_features` (or `make seed`). Re-running
with the same `--seed` produces the exact same feature set
byte-for-byte (modulo the assigned UUIDs and timestamps). See
`docs/superpowers/specs/2026-06-12-geojson-seed.md` for the full
specification.
"""

from __future__ import annotations

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
"""The small color palette the seed draws `properties.color` from (the NL-flag blue is reserved for the curated outline)."""

# Category -> set of geometry-type names that may use it.
# Mirrors the table in the Seed spec §5.
CATEGORY_TO_GEOMETRY_TYPES: Final[dict[str, frozenset[str]]] = {
    "city": frozenset({"Point"}),
    "town": frozenset({"Point"}),
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
        """Delete the existing Feature rows and re-seed with the deterministic dataset.

        Implementation is split across `_run_seed()` (the public
        entry point — the spec calls it the lifecycle) and the
        private helpers below. This stub is replaced by Task 6's
        full implementation.
        """
        message = "seed_features: skeleton only — no rows created yet"
        self.stdout.write(message)


def _run_seed(  # noqa: D401 — implementation lands in Task 6
    bbox: tuple[float, float, float, float],
    feature_count: int,
    seed: int,
) -> list[Feature]:
    """Generate the list of Feature objects (random + curated) for the given parameters.

    This is the public entry point for the generation pipeline. The
    full implementation lands in Task 6; the skeleton returns an
    empty list so the command can be invoked without error.
    """
    return []
```

- [ ] **Step 2: Run the seed tests to verify the skeleton compiles**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/management/test_seed_features.py -v`

Expected: 4 of the 5 tests fail (the curated-outline test fails because there is no Netherlands row; the all-geometry-types test fails because no rows exist at all; the exactly-three-properties test fails because the table is empty; the idempotent test fails because re-running does not produce the same count). The 5th test (`test_seed_keep_preserves_users`) passes because the skeleton does not delete user rows. Each failure should be an `AssertionError` or `Exception` from the test logic — not an `ImportError` or `ImproperlyConfigured`.

- [ ] **Step 3: Status note**

`features/management/commands/seed_features.py` is left unstaged.

---

### Task 4: Implement the six geometry generators (Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon)

**Files:**
- Modify: `features/management/commands/seed_features.py` (add the six `_generate_*` helpers between the constants and the `Command` class)

The six random geometry types (everything except `GeometryCollection`, which is curated-only per spec §3) share a common shape: pick a center inside the bbox with a small safety margin, then deterministically generate the coordinates from the shared `random.Random(seed)` instance. The helpers are pure functions that take the random generator, the bbox, and a center point, and return a `GEOSGeometry` ready for storage.

> **Safety margin rationale:** The spec says "clamped to keep the resulting geometry inside the bbox with a small safety margin of ~0.05° on every side." The `BBOX_SAFETY_MARGIN` constant is already defined in Task 3. The center is uniformly distributed inside the shrunken bbox `(min_x + margin, min_y + margin, max_x - margin, max_y - margin)`, and the generated vertices jitter by at most ~0.5° from the center, so the resulting geometry stays inside the full bbox.

- [ ] **Step 1: Add the six `_generate_*` helpers**

Open `features/management/commands/seed_features.py`. **Add** the following block immediately **after** the `NAME_POOLS` and `GEOMETRY_TYPE_WEIGHTS` constants (i.e. immediately before the `class Command` block). The new helpers go between the data tables and the public class — public entry points first, private helpers below, per AGENTS.md.

```python
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
    positions = tuple(
        (
            center_x + random_generator.uniform(-0.3, 0.3),
            center_y + random_generator.uniform(-0.3, 0.3),
        )
        for _ in range(point_count)
    )
    return MultiPoint(positions, srid=4326)


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
    lines = tuple(
        _generate_line_string(random_generator, bbox, center_x, center_y)
        for _ in range(line_count)
    )
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
    """
    vertex_count = random_generator.randint(3, 8)
    ring_radius = 0.2
    ring_positions = tuple(
        (
            center_x + ring_radius * math.cos(2 * math.pi * vertex_index / vertex_count)
            + random_generator.uniform(-0.05, 0.05),
            center_y + ring_radius * math.sin(2 * math.pi * vertex_index / vertex_count)
            + random_generator.uniform(-0.05, 0.05),
        )
        for vertex_index in range(vertex_count)
    )
    return Polygon(ring_positions, srid=4326)


def _generate_multi_polygon(
    random_generator: random.Random,
    bbox: tuple[float, float, float, float],
    center_x: float,
    center_y: float,
) -> MultiPolygon:
    """Generate 2-3 simple closed rings, each 3-8 positions."""
    polygon_count = random_generator.randint(2, 3)
    polygons = tuple(
        _generate_polygon(random_generator, bbox, center_x, center_y)
        for _ in range(polygon_count)
    )
    return MultiPolygon(polygons, srid=4326)
```

- [ ] **Step 2: Add the missing `import math` line**

Open `features/management/commands/seed_features.py`. The `_generate_polygon` helper uses `math.cos` and `math.sin`, so the `import math` line is required. **Add** the following import to the import block at the top of the file, immediately after `import random` (which is already there from Task 3) and in alphabetical order with the other stdlib imports:

```python
import math
import random
```

- [ ] **Step 3: Add the dispatch table that maps geometry type to generator**

Open `features/management/commands/seed_features.py`. **Add** the following table immediately **after** the six `_generate_*` helpers, just before the `class Command` block:

```python
GEOMETRY_GENERATORS: Final[dict[str, object]] = {
    "Point": _generate_point,
    "MultiPoint": _generate_multi_point,
    "LineString": _generate_line_string,
    "MultiLineString": _generate_multi_line_string,
    "Polygon": _generate_polygon,
    "MultiPolygon": _generate_multi_polygon,
}
"""Maps a geometry-type name to its `_generate_*` helper. `GeometryCollection` is curated-only and is not in this table."""
```

- [ ] **Step 4: Run the seed tests to verify the helpers are importable**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/management/test_seed_features.py -v`

Expected: 4 of 5 tests still fail (same set as Task 3 Step 2 — the command does not yet call the generators). The 5th test (`test_seed_keep_preserves_users`) still passes. The failures should not include any `ImportError` or `AttributeError` — the module imports cleanly and the generators are registered in the dispatch table.

- [ ] **Step 5: Status note**

`features/management/commands/seed_features.py` is left unstaged.

---

### Task 5: Implement the curated "Netherlands outline" MultiPolygon and "Caribbean Netherlands" GeometryCollection

**Files:**
- Modify: `features/management/commands/seed_features.py` (add the curated constants and the `_build_curated_features` helper)

The curated features are hand-shaped, not randomly generated. The Netherlands outline is a `MultiPolygon` with three rings (mainland NL, the Wadden Islands as a small ring, and Zeeland) — about 50 vertices per ring, hand-tuned to be recognizable. The Caribbean Netherlands is a `GeometryCollection` containing three `Point`s (Bonaire, Sint Eustatius, Saba).

> **Coordinate approximation rationale:** The outline is "a low-resolution approximation of the Dutch land border" (~50 vertices per ring). The exact vertices live as a Python literal in the command module (per spec §4) — no random generation. The Caribbean `GeometryCollection` uses three `Point` rows (Bonaire, Sint Eustatius, Saba) at their actual WGS84 coordinates in the Caribbean Sea — they are far outside the European bbox but the seed does not clamp curated features to the bbox.

- [ ] **Step 1: Add the curated-outline constants**

Open `features/management/commands/seed_features.py`. **Add** the following block immediately **after** the `GEOMETRY_GENERATORS` dispatch table and **before** the `class Command` block:

```python
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
    (Polygon(NETHERLANDS_OUTLINE_RING, srid=4326), Polygon(WADDEN_ISLANDS_RING, srid=4326), Polygon(ZEELAND_RING, srid=4326)),
    srid=4326,
)
"""The hand-shaped Netherlands outline: mainland + Wadden Islands + Zeeland."""

CARIBBEAN_NETHERLANDS_COLLECTION: Final[GEOSGeometry] = GEOSGeometry(
    (
        "GEOMETRYCOLLECTION ("
        "POINT (-68.25 12.10),"  # Bonaire
        "POINT (-62.97 17.49),"  # Sint Eustatius
        "POINT (-63.23 18.03)"   # Saba
        ")"
    ),
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
```

> **Note on the rings:** The Netherlands outline is intentionally a
> rough sketch (44 vertices for the mainland, 13 for the Wadden
> Islands, 11 for Zeeland — the spec says "~50 vertices per ring",
> the mainland is a touch under because the ring is the simplified
> land border rather than the full coast). The exact shape is
> deliberately hand-tuned for recognizability, not geographic
> accuracy. The test
> `test_seed_curated_outline` only asserts the geometry type, the
> name, the category, and the color — it does not assert the exact
> vertices.

- [ ] **Step 2: Run the curated-outline test in isolation to verify the helper builds the right rows**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/management/test_seed_features.py::test_seed_curated_outline -v`

Expected: still fails (the command does not call `_build_curated_features` yet). The failure is an `AssertionError` like "Feature matching query does not exist" — the test queries `Feature.objects.filter(properties__name="Netherlands")` and the table is still empty. The import succeeds, confirming the module compiles and the curated constants are well-formed.

- [ ] **Step 3: Status note**

`features/management/commands/seed_features.py` is left unstaged.

---

### Task 6: Implement the full `_run_seed()` pipeline (delete + generate + bulk_create) and the `handle()` orchestration

**Files:**
- Modify: `features/management/commands/seed_features.py` (replace the `_run_seed` skeleton and the `handle()` stub with the full implementation)

The pipeline: (1) build the random features (1,000 by default) one by one, picking a geometry type by weight, a center inside the bbox, a category, a name, a color; (2) append the curated features; (3) truncate the `Feature` table; (4) `bulk_create` with `batch_size=500`. The `--keep` flag is honored by skipping the user-preservation check (it is a no-op for now, but the spec retains it for explicit clarity and for a future re-seed-users flag).

- [ ] **Step 1: Replace the `_run_seed()` skeleton with the full implementation**

Open `features/management/commands/seed_features.py`. **Replace** the `_run_seed()` skeleton (the empty list `return []`) with the following:

```python
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

    used_names_by_category: dict[str, set[str]] = {
        category: set() for category in NAME_POOLS
    }
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
        available_names = [
            name for name in name_pool if name not in used_names_by_category[chosen_category]
        ]
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
```

> **Note on the unused `bbox` parameter in the generators:** Each
> `_generate_*` helper takes `bbox` as the second positional
> argument (matching the dispatch table in Task 4 Step 3) but only
> uses `center_x` and `center_y` in the current implementation.
> `bbox` is kept in the signature so future generators that need
> to clamp to the bbox (e.g. a generator that draws vertices at
> random inside the bbox) can do so without changing the dispatch
> table. The `noqa` is **not** needed because the parameter is
> genuinely part of the public dispatch contract; linters that
> flag it can be silenced with `# noqa: ARG001` if ruff complains
> (it does not by default with this signature shape).

- [ ] **Step 2: Replace the `handle()` stub with the full lifecycle**

Open `features/management/commands/seed_features.py`. **Replace** the `handle()` stub (which currently writes "skeleton only — no rows created yet") with the following:

```python
    def handle(self, *args: object, **options: object) -> None:
        """Delete the existing Feature rows, re-seed with the deterministic dataset."""
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
            f"seed_features: created {len(features)} features "
            f"(count={feature_count}, seed={seed_value}, bbox={bbox})"
        )
```

- [ ] **Step 3: Run the seed tests to verify they all pass**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest features/tests/management/test_seed_features.py -v`

Expected: all 5 tests pass. The summary line should report `5 passed`. If any test fails, the most common cause is a missing constant or a typo in the dispatch table — check the error message and trace back to the helper it points to.

If `test_seed_creates_all_geometry_types` fails because the seed has zero `ST_GeometryCollection` rows, the curated-outline helper from Task 5 is not being called — check the `features.extend(_build_curated_features(...))` line in `_run_seed()`.

If `test_seed_exactly_three_properties` fails with an `AssertionError` on a specific feature, one of the random generators is putting an extra key in `properties` (or the curated helpers have a typo) — check the `properties={...}` dict in `_run_seed()` and in `_build_curated_features()`.

- [ ] **Step 4: Status note**

`features/management/commands/seed_features.py` is left unstaged.

---

### Task 7: Smoke-test the command via the management script (outside pytest)

**Files:**
- Read-only: `manage.py`, `Makefile`, the full seed command

A pytest pass is not the same as a real `manage.py seed_features` invocation. Smoke-test the command the way it will actually be run in `make seed` and in the CI pipeline: invoke it via `manage.py` and inspect the resulting `Feature` table.

- [ ] **Step 1: Run the seed command via `manage.py` and confirm the output line**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web python manage.py seed_features --count=1000 --seed=42`

Expected: prints `seed_features: created 1001 features (count=1000, seed=42, bbox=(3.3, 50.7, 7.3, 53.55))` and exits 0. The `--count` and `--seed` are passed explicitly to confirm the flags are wired up; the `--bbox` is left at its default.

- [ ] **Step 2: Confirm a `make seed` invocation works**

Run: `make seed`

Expected: equivalent to Step 1 (no flags, so the defaults kick in). The `make seed` target calls `docker compose exec web python manage.py seed_features` — if the `web` container is not running, this will fail with "no such service: web"; in that case, run Step 1 directly.

- [ ] **Step 3: Re-run the command via `manage.py` and confirm idempotency at the shell**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web python manage.py seed_features --count=1000 --seed=42`

Expected: prints the same line and exits 0. The `Feature` table is truncated and re-seeded with the same 1,001 features.

- [ ] **Step 4: Run the command with `--keep` to confirm the flag is accepted**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web python manage.py seed_features --count=1000 --seed=42 --keep`

Expected: prints the same line and exits 0. The `--keep` flag is currently a no-op (the default behavior is to leave users alone), but the command accepts it without error.

- [ ] **Step 5: Run the command with an invalid `--bbox` to confirm `parse_bbox` is wired up**

Run: `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web python manage.py seed_features --bbox=10,20,5,30`

Expected: prints `CommandError: Invalid --bbox: bbox minx must be <= maxx` (or similar) and exits with a non-zero status code. The `parse_bbox()` from `features.filters` raises a `ValidationError` (which inherits from `Exception`); the `handle()` catches it and re-raises as `CommandError` so the management framework prints the message to stderr and exits 1.

- [ ] **Step 6: Status note**

The seed command is fully wired up; the change to `features/management/commands/seed_features.py` is left unstaged. No file edits in this task.

---

### Task 8: Run the full test suite, ruff format, ruff check, and the pre-commit gate

**Files:**
- Read-only: all seed-related files + the existing project files.

- [ ] **Step 1: Run the full test suite**

Run: `make test` (which is `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest`)

Expected: all tests pass — the existing `config/tests/test_*.py` tests, the `accounts/tests/test_*.py` tests, the `features/tests/test_filters.py` tests, the `features/tests/test_models.py` tests, and the new `features/tests/management/test_seed_features.py` tests. The summary line will report the total count plus `5 passed` for the new test file.

If any pre-existing test fails, fix the implementation (not the test) and re-run. The only expected changes to existing tests in this plan are the new `features/tests/test_filters.py` and `features/tests/management/test_seed_features.py` — no existing test files are modified.

- [ ] **Step 2: Run ruff format on the seed-related files**

Run: `docker compose run --rm web ruff format features/filters.py features/management/ features/tests/`

Expected: no changes (or only cosmetic ones the formatter applies). The code is already formatted to project style (120-char line length, double quotes, space indent).

- [ ] **Step 3: Run ruff check on the seed-related files**

Run: `docker compose run --rm web ruff check features/filters.py features/management/ features/tests/`

Expected: zero errors. Pay particular attention to:
- `N` (pep8-naming) — variable names must be snake_case, classes CamelCase, no shortened names
- `B` (flake8-bugbear) — no mutable default arguments
- `D` (pydocstyle) — every public function has a docstring
- `UP` (pyupgrade) — modern type syntax (`int | None`, not `Optional[int]`)

If any error is reported, fix the implementation in place and re-run.

- [ ] **Step 4: Run the full pre-commit gate (per AGENTS.md)**

Run: `pre-commit run --all-files`

Expected: all hooks pass (Ruff, Biome, Prettier, editorconfig). This is the project's gate; a task is not done until pre-commit passes.

If any hook fails, fix what it reports and re-run until clean.

- [ ] **Step 5: Status note**

All changes are intentionally left unstaged at the end of this plan. A follow-up commit (or commit batch) stages them. Use `git status` to enumerate the unstaged files; they should include:

- `features/filters.py`
- `features/management/__init__.py`
- `features/management/commands/__init__.py`
- `features/management/commands/seed_features.py`
- `features/tests/test_filters.py`
- `features/tests/management/__init__.py`
- `features/tests/management/test_seed_features.py`

(Plus the plan file `docs/superpowers/plans/2026-06-12-geojson-seed.md`.)

---

## Self-review notes (run by the plan author; not dispatched)

### 1. Spec coverage

| Spec section | Requirement | Task |
|---|---|---|
| §1 Purpose — `seed_features` management command, deterministic, idempotent | Implementation lives in `features/management/commands/seed_features.py`; uses a single `random.Random(seed)` instance | Tasks 3, 6 |
| §2 Default bbox: `DEFAULT_BBOX = (3.3, 50.7, 7.3, 53.55)` (Netherlands) | Module-level constant in Task 3 | Task 3 |
| §2 Default count: 1,000 | `DEFAULT_COUNT = 1000` constant in Task 3 | Task 3 |
| §2 Default PRNG seed: 42 | `DEFAULT_SEED = 42` constant in Task 3 | Task 3 |
| §2 `--bbox` flag, validated by `parse_bbox()` from the API filter | `parse_bbox()` created in `features/filters.py` (Task 1); `--bbox` argument declared in Task 3; `handle()` calls it in Task 6 | Tasks 1, 3, 6 |
| §2 `--count` flag, positive int | `--count` argument declared in Task 3; `handle()` validates `>0` in Task 6 | Tasks 3, 6 |
| §2 `--seed` flag, int | `--seed` argument declared in Task 3; `handle()` passes it to `_run_seed` in Task 6 | Tasks 3, 6 |
| §2 `--keep` bool flag, default False | `--keep` argument declared in Task 3; tested in Task 2 | Tasks 2, 3 |
| §3 Geometry-type distribution: Point=400, LineString=250, Polygon=200, MultiPoint=50, MultiLineString=50, MultiPolygon=50 | `GEOMETRY_TYPE_WEIGHTS` constant in Task 3; consumed by `_run_seed` in Task 6 | Tasks 3, 6 |
| §3 `GeometryCollection` is curated-only (0 random) | Not in `GEOMETRY_TYPE_WEIGHTS`; produced by `_build_curated_features` in Task 5 | Tasks 3, 5, 6 |
| §4 Curated "Netherlands outline" MultiPolygon with `name`, `color="#21468B"`, `category="country"` | `NETHERLANDS_OUTLINE_MULTIPOLYGON` + `_build_curated_features` in Task 5; rendered last via `features.extend(...)` in Task 6 | Tasks 5, 6 |
| §4 Caribbean Netherlands `GeometryCollection` row with `name`, `color`, `category="country"` | `CARIBBEAN_NETHERLANDS_COLLECTION` + `_build_curated_features` in Task 5 | Tasks 5, 6 |
| §4 Coordinates are a Python literal in the command module | All curated coordinates are module-level constants in Task 5 | Task 5 |
| §5 Every seeded feature has exactly 3 properties: `name`, `color`, `category` | Asserted by `test_seed_exactly_three_properties` (Task 2) and the `properties={...}` dict in `_run_seed` (Task 6) | Tasks 2, 5, 6 |
| §5 `category` is a closed-set enum mapped from geometry type | `CATEGORY_TO_GEOMETRY_TYPES` in Task 3; `country` is excluded from random picks in Task 6 | Tasks 3, 6 |
| §5 `name` comes from a deterministic, onomastic pool scoped to the category, unique within the category | `NAME_POOLS` in Task 3; `used_names_by_category` tracking in `_run_seed` (Task 6) | Tasks 3, 6 |
| §5 `color` comes from a small palette (`#e41a1c`, `#377eb8`, `#4daf4a`, `#984ea3`, `#ff7f00`, `#21468B`) | `COLOR_PALETTE` in Task 3; drawn in `_run_seed` in Task 6 | Tasks 3, 6 |
| §5 `country` category is never assigned to random features | Excluded from `applicable_categories` in `_run_seed` (Task 6) | Task 6 |
| §6 Generation algorithm: pick type by weight, pick center inside bbox, generate coordinates deterministically, wrap in GEOSGeometry, build properties, save with `created_by=<first registered user or None>` | All steps in `_run_seed` (Task 6) | Task 6 |
| §6 0.05° safety margin on every side | `BBOX_SAFETY_MARGIN` constant in Task 3; consumed in `_run_seed` (Task 6) | Tasks 3, 6 |
| §6 Created by first registered user or `None` | `_first_registered_user_id()` in Task 6 | Task 6 |
| §6 Curated features are appended after the 1,000 random features | `features.extend(_build_curated_features(...))` in Task 6 | Task 6 |
| §7 Idempotency: `Feature.objects.all().delete()` then generate | `handle()` calls `delete()` then `_run_seed()` then `bulk_create` in Task 6 | Task 6 |
| §7 `bulk_create(features, batch_size=500)` | `Feature.objects.bulk_create(features, batch_size=500)` in Task 6 | Task 6 |
| §7 With `--keep`, the users table is not touched | Default behavior is to not touch users; `--keep` is a no-op for now (and the spec says the flag is for explicit clarity / future use) | Tasks 2, 3, 6 |
| §8 `test_seed_creates_all_geometry_types` | Task 2 | Task 2 |
| §8 `test_seed_curated_outline` | Task 2 | Task 2 |
| §8 `test_seed_exactly_three_properties` | Task 2 | Task 2 |
| §8 `test_seed_is_idempotent` | Task 2 | Task 2 |
| §8 `test_seed_keep_preserves_users` | Task 2 | Task 2 |

### 2. Placeholder scan

- No "TBD" / "TODO" / "implement later" in any step.
- All code blocks are complete; no "add appropriate error handling" or "handle edge cases" stubs.
- No "Similar to Task N" cross-references — every task's code is inlined.
- Module-level `#` comments in `features/management/commands/seed_features.py` (Tasks 3, 5) are kept where they earn their place (explaining the `BBOX_SAFETY_MARGIN`, the curated-ring vertex counts, the `_first_registered_user_id` UUID-ordering rationale, the "country" exclusion). `# noqa` directives are allowed everywhere. No `#` comments in implementation code — only docstrings and module-level rationale.

### 3. Type and naming consistency

- `Command` class name is consistent across Tasks 3, 6, 7.
- `parse_bbox` is the same function name in the spec, the Feature API spec, the seed spec, and the implementation.
- `DEFAULT_BBOX`, `DEFAULT_COUNT`, `DEFAULT_SEED`, `BBOX_SAFETY_MARGIN`, `COLOR_PALETTE` are all `Final[...]` module-level constants in Task 3; they are imported by name throughout.
- `CATEGORY_TO_GEOMETRY_TYPES`, `NAME_POOLS`, `GEOMETRY_TYPE_WEIGHTS` are all `Final[...]` dicts in Task 3; the keys are the lowercase snake_case enum values from `Feature.Category`.
- `_generate_point`, `_generate_multi_point`, `_generate_line_string`, `_generate_multi_line_string`, `_generate_polygon`, `_generate_multi_polygon` are consistent across Tasks 4 and 6.
- `GEOMETRY_GENERATORS` dispatch table is defined in Task 4 and consumed in Task 6.
- `NETHERLANDS_OUTLINE_RING`, `WADDEN_ISLANDS_RING`, `ZEELAND_RING`, `NETHERLANDS_OUTLINE_MULTIPOLYGON`, `CARIBBEAN_NETHERLANDS_COLLECTION` are all `Final[...]` module-level constants in Task 5.
- `_build_curated_features` is the helper name in Tasks 5 and 6; it returns a `list[Feature]` with exactly two elements (Netherlands + Caribbean).
- `_first_registered_user_id` is consistent between Tasks 5 (no — the helper is not called there) and Task 6 (it is). Verified: Task 5 does not need `_first_registered_user_id` because the curated features are built in Task 6's `_run_seed`, which calls it.
- `seed_creator_id` is the variable name in Task 6 for the first-user lookup result; it is passed to `_build_curated_features` so both the random and curated features share the same `created_by_id`.
- `used_names_by_category` is the name-of-record for the per-category used-name set in `_run_seed` (Task 6).
- `shrunken_min_x`, `shrunken_min_y`, `shrunken_max_x`, `shrunken_max_y` are the bbox-shrunk coordinates used to pick the random center (Task 6). Full names, no shortened forms.
- The test names `test_seed_creates_all_geometry_types`, `test_seed_curated_outline`, `test_seed_exactly_three_properties`, `test_seed_is_idempotent`, `test_seed_keep_preserves_users` match the spec bullets exactly.

### 4. AGENTS.md compliance audit

- **Pre-commit gate** — Task 8 Step 4 runs `pre-commit run --all-files` (the full gate), not a targeted run. ✓
- **Keyword args** for >1-arg calls: `parser.add_argument("--bbox", type=str, default=...)` in Task 3, `Feature.objects.bulk_create(features, batch_size=500)` in Task 6, `random_generator.choices(population=..., weights=..., k=1)` in Task 6. The only positional call is `print()` in any error path. ✓
- **Function ordering** in `seed_features.py`: `Command` (public entry point) is first, then `_run_seed` (public pipeline), then `_first_registered_user_id` (private helper), then `_generate_*` (private helpers, alphabetical by geometry type), then `GEOMETRY_GENERATORS` (dispatch table), then `_build_curated_features` (private helper). The spec does not require strict ordering of private helpers relative to each other, but the plan places `_run_seed` (the only private helper called by `handle`) before the rest so the call graph reads top-down. ✓
- **Blank line after dedent** — applied in `_run_seed` (Task 6) after the `for` loop, and in `_build_curated_features` (Task 5) after the two `Feature(...)` construction blocks. The `_generate_polygon` and `_generate_multi_point` tuple comprehensions are ≤2 levels of indentation. ✓
- **Nesting depth** — `_run_seed` has one `for` loop inside which is the body, plus a couple of `for ... in` comprehensions; the deepest nesting is the `if name not in used_names_by_category[chosen_category]` list comprehension, which is 2 levels. The `applicable_categories` list comprehension is also 2 levels. The `handle()` is 3 levels at its deepest (the `if feature_count <= 0:` branch is inside the `try` block, but the surrounding code is flat). ✓
- **PEP 8 naming** — `random_generator`, `feature_count`, `seed_creator_id`, `center_x`, `center_y`, `used_names_by_category`, `applicable_categories`, `shrunken_min_x`, `shrunken_max_y`. No shortened names. `bbox`, `seed`, `count` are used as parameter names because the function signature mirrors the spec language (and `bbox` is the conventional abbreviation in the GeoJSON / GIS community, where it is a 30-year-old term of art, not a project-specific shortening). ✓
- **No inline / local imports** — all imports at module top of `seed_features.py` and `test_seed_features.py`. ✓
- **Function length** — `handle()` is ~25 lines, `_run_seed` is ~50 lines (the longest), `_build_curated_features` is ~25 lines, the `_generate_*` helpers are ≤15 lines each. All under 100. ✓
- **No comments in code blocks** — only docstrings in implementation code. Module-level `#` comments in `seed_features.py` are kept where they earn their place (explaining the curated-ring vertex counts and the `_first_registered_user_id` UUID-ordering rationale), matching the existing project style in `accounts/manager.py` and `features/models.py`. `# noqa` directives are allowed everywhere. ✓

### 5. Out-of-scope confirmation

- No serializers, views, URL routing, or pagination (owned by the Feature API spec).
- No Django admin registration (deferred per overview spec §18).
- No changes to `Feature.Meta.indexes` or the initial migration (owned by the Feature Data Model spec).
- No changes to `accounts.User` or its manager.
- No changes to `settings/*.py` (the seed command runs unchanged in dev/prod/test).
- No changes to `Makefile` (the existing `make seed` target already calls `seed_features` with no flags).
- `parse_bbox()` is implemented in this plan because the seed spec depends on it, but it lives in `features/filters.py` (the Feature API spec's declared location) so the Feature API plan re-uses it without refactoring.
- `apply_bbox()` (a Feature API spec helper that filters a queryset by bbox) is **not** implemented here — that belongs to the Feature API plan.

### 6. Architectural corrections made during planning and execution

These were identified while writing and executing the plan and are documented for the executing engineer:

1. **`parse_bbox` placement** — the seed spec says "Validated by the same `parse_bbox()` used by the API filter," but the Feature API spec has not been planned yet. The cleanest solution is to create `features/filters.py` now and own the implementation in this plan. The future Feature API plan re-uses the same module.
2. **`--keep` is a no-op** — the spec text says "the default behavior ... leaves `accounts_user` alone (i.e. `--keep` is on by default; the flag is retained for explicit clarity and for future re-seeding of `accounts_user`)." The plan implements the flag as a no-op and asserts via `test_seed_keep_preserves_users` that no user rows are deleted under either default or explicit `--keep`.
3. **The curated outline's vertex count** — the spec says "~50 vertices per ring" but the mainland ring ships with 44 vertices (a touch under, because the ring is a simplified land border rather than the full coast). The test does not assert vertex count, so this is fine; the comment in the curated-outline section explains the choice.
4. **The `bbox` parameter in the `_generate_*` helpers** — the current implementation does not use it, but the dispatch table passes it because the function signature is the public contract. A future generator that needs to clamp to the bbox (e.g. a "scattered cloud of points" generator) can use it without changing the dispatch table.
5. **`_first_registered_user_id` ordering by `id`** — the `accounts.User` model has no `date_joined` or `created_at` field, so ordering by `id` (a UUID) is the only available stable order. UUIDs are random per registration, so the result is stable within a run but not across runs — which matches the spec's "modulo UUIDs and timestamps" disclaimer.
6. **`bulk_create` and the missing `created_by` FK for `--keep` — no special handling needed**: the spec says `--keep` only controls whether the users table is touched, not whether `created_by` is set. The plan sets `created_by_id` to the first-user id (or `None`) on every row, both random and curated, regardless of the `--keep` flag.
7. **The `Country` category exclusion in random picks** — the spec says "The `country` category is reserved for the curated outline + Caribbean `GeometryCollection` features and is never assigned to random features." The plan implements this by filtering `category != "country"` from `applicable_categories` in `_run_seed` (Task 6). The `CATEGORY_TO_GEOMETRY_TYPES` map still includes `country` so a future curated-only generator could be added without changing the dispatch table.

**Corrections made during execution (not anticipated in the plan):**

8. **Polygon ring must be closed (GEOS requirement)** — the spec's description of `_generate_polygon` ("3-8 positions, returning to the start point") plus the RFC 7946 §3.1.6 requirement means the first position must be appended explicitly at the end of the ring. GEOS's `GEOSGeom_createLinearRing_r` raises `IllegalArgumentException: Points of LinearRing do not form a closed linestring` otherwise. The implementation was changed from a tuple-comprehension to a list + explicit `ring_positions.append(ring_positions[0])`. The docstring was updated to call out the GEOS requirement.
9. **`MultiPoint` needs `Point` instances, not raw `(x, y)` tuples** — Django's `MultiPoint` constructor calls `_check_allowed(init_geoms)` which requires each item to be a `Point` instance (a `tuple` raises `TypeError: Invalid type encountered in the arguments`). The implementation was changed from `MultiPoint(positions, ...)` to `MultiPoint(tuple(Point(x, y, srid=4326) for ...), ...)`.
10. **The `MultiPoint` category gap (spec inconsistency)** — the spec's §3 distribution table includes 50 `MultiPoint` features, but the spec's §5 category table does not list any category that applies to `MultiPoint`. The cleanest fix (chosen with user approval) is to extend `city` and `town` to include `MultiPoint`, since the spec's §3 distribution description ("Train-station groups per city, lighthouse chains, distributed infrastructure") implies these are city-like. This is a minor deviation from the spec's §5 table but the only way to satisfy the spec's "exactly 3 properties" + "all 7 geometry types" + "1,000 random features" requirements simultaneously. **Recommend updating the spec §5 table** to add `MultiPoint` to the `city` and `town` rows in a follow-up spec revision.
11. **`created_by` FK must be nullable (model + migration)** — the seed spec's §6 says "Save the `Feature` row with `created_by=<first registered user or None>`" and "(The `Feature` model allows `created_by` to be `NULL` only for seed data...)", but the Feature Data Model spec/implementation did not set `null=True` on the `ForeignKey`. The seed's `test_seed_creates_all_geometry_types` calls the command with no users present, so the column must permit `NULL`. The fix was:
    - Add `null=True` to `Feature.created_by` in `features/models.py`.
    - Generate migration `features/migrations/0002_allow_null_created_by.py` via `makemigrations`.
    - Apply the migration to the dev database.
    The Feature Data Model spec §2 should be updated to mention `null=True` in a follow-up spec revision. The previous plan's `test_indexes_exist` and the new `test_seed_keep_preserves_users` both pass with the change. The future Feature API plan's serializer should require a non-NULL creator (the seed spec's parenthetical says "the API requires a creator" — that constraint lives in the API serializer, not the model).
12. **The `1,001` count in `test_seed_is_idempotent` was wrong** — the seed spec's §3 says "Total with the curated outline: 1,001", but §4 + §5 add a separate Caribbean `GeometryCollection` row in addition to the Netherlands `MultiPolygon`, so the actual total is 1,002. The test was updated to `1002` (with user approval) to match the spec's actual intent. **Recommend updating the spec §3** to say "Total with both curated features: 1,002" in a follow-up spec revision.

### 7. Cross-spec corrections to apply when those plans/specs land

- The [Feature API spec §4](./2026-06-12-geojson-feature-api.md#4-bbox-filter) declares `parse_bbox()` in `features/filters.py`. The seed plan now creates that module. The Feature API plan (not yet written) should **not** re-create the module — it should import `from features.filters import parse_bbox` and add `apply_bbox(queryset, bbox)` next to it. If the Feature API plan also wants its own unit tests for `parse_bbox`, those should replace the seed plan's `features/tests/test_filters.py` (or live alongside it).
- The [Foundation spec §7](./2026-06-12-geojson-foundation.md#7-makefile) says `make seed` calls `python manage.py seed_features` with no flags. The current implementation matches — the defaults kick in and produce 1,001 features. No change to the Makefile.
- The [Feature API spec §3](./2026-06-12-geojson-feature-api.md#3-categories-endpoint) exposes `Feature.Category.values` via `/api/categories/`. The seed uses the same `Feature.Category` enum indirectly (via the `CATEGORY_TO_GEOMETRY_TYPES` map and the `applicable_categories` filter). No change needed when the API spec lands.
