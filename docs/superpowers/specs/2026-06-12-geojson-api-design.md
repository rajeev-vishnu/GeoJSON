# GeoJSON API — Design Spec (Overview)

**Date:** 2026-06-12
**Status:** Approved for implementation
**Scope:** Single Django + PostGIS + frontend project implementing the
"BE Coding Assignment" at `BE Coding Assignment.md`.

## 1. Purpose and goals

Build a small Django REST API serving vector features in a GeoJSON-compatible
format, with a bounding-box filter, page-number pagination, JWT auth, and two
HTML frontend pages (map and edit). Data is stored in a PostGIS database. The
project ships with Docker, a seeded dataset, a test suite, and CI.

The target reviewer is a senior backend engineer at a geospatial infrastructure
company. The deliverable is judged on:

- Idiomatic Django / DRF code.
- Correct use of PostGIS for spatial storage and bbox queries.
- Lossless GeoJSON round-trip.
- Clean, runnable Docker setup.
- Test coverage and CI.

## 2. Child spec index

This overview is the project-level north star. The detailed
implementation spec is split across 8 child specs, each self-contained
enough to be implemented as an isolated plan. Cross-references use
relative file paths.

| # | Slug | Scope | Depends on |
| --- | --- | --- | --- |
| 1 | [geojson-foundation.md](./2026-06-12-geojson-foundation.md) | Stack, project layout, settings split, Docker, Makefile, env, prod security, CSP | — |
| 2 | [geojson-auth.md](./2026-06-12-geojson-auth.md) | `User` model, password validators, 4 auth endpoints, JWT, auth tests | Foundation |
| 3 | [geojson-feature-model.md](./2026-06-12-geojson-feature-model.md) | `Feature` model, GiST/BTree/trigram-GIN indexes, `Category` enum, model tests | Foundation |
| 4 | [geojson-feature-api.md](./2026-06-12-geojson-feature-api.md) | Feature endpoints, bbox filter, pagination, validation, serializers, 6 features test files | Foundation, Auth, Feature Data Model |
| 5 | [geojson-seed.md](./2026-06-12-geojson-seed.md) | `seed_features` command, NL bbox, distribution, curated outline, seed tests | Foundation, Feature Data Model |
| 6 | [geojson-frontend.md](./2026-06-12-geojson-frontend.md) | Templates, top-nav + search, map page, edit page, static assets, CSP, token storage | Foundation, Auth, Feature API |
| 7 | [geojson-ci.md](./2026-06-12-geojson-ci.md) | GitHub Actions workflow, `config/settings/test.py` | All feature specs |
| 8 | [geojson-docs.md](./2026-06-12-geojson-docs.md) | `README.md` outline and content | All other specs |

### Dependency graph

```
                                  [Overview]
                                       |
                                  [Foundation]  (1)
                                  /     |      \
                          [Auth]  [Feature  [Seed] ──┐
                           (2)    Model]   (5)       |
                              \    (3)      /        |
                               [Feature    /         |
                                  API]  ──┘          |
                                   (4)               |
                                    \               /
                                  [Frontend]       /
                                      (6)        /
                                       \       /
                                      [CI]   /
                                       (7)  /
                                        |  /
                                     [Docs]
                                       (8)
```

The graph is a DAG: Foundation has no deps, Auth and Feature
Data Model depend only on Foundation, Feature API depends on
Foundation + Auth + Feature Data Model, Seed depends on
Foundation + Feature Data Model, Frontend depends on Foundation +
Auth + Feature API, CI depends on all feature specs, Docs
depends on all other specs.

### Section mapping

| Old section | New home |
| --- | --- |
| §2 Stack and tooling | [Foundation §2](./2026-06-12-geojson-foundation.md#2-stack-and-tooling) |
| §3 Project layout | [Foundation §3](./2026-06-12-geojson-foundation.md#3-project-layout) |
| §4 Data model | [Feature Data Model §2-3](./2026-06-12-geojson-feature-model.md) (Feature); [Auth §2-3](./2026-06-12-geojson-auth.md) (User) |
| §5 API contract | [Auth §4](./2026-06-12-geojson-auth.md#4-auth-endpoints) (auth endpoints); [Feature API §2-3](./2026-06-12-geojson-feature-api.md) (feature + categories) |
| §6 Bbox filter | [Feature API §4](./2026-06-12-geojson-feature-api.md#4-bbox-filter) |
| §7 Validation | [Feature API §6](./2026-06-12-geojson-feature-api.md#6-validation) |
| §8 Pagination | [Feature API §5](./2026-06-12-geojson-feature-api.md#5-pagination) |
| §9 Serializers | [Auth §5](./2026-06-12-geojson-auth.md#5-serializers) (User/Register/Login); [Feature API §7](./2026-06-12-geojson-feature-api.md#7-serializers) (Feature) |
| §10 URL routing | [Foundation §5](./2026-06-12-geojson-foundation.md#5-root-url-routing) (root); [Auth §6](./2026-06-12-geojson-auth.md#6-url-routing-and-authentication-classes); [Feature API §8](./2026-06-12-geojson-feature-api.md#8-url-routing) |
| §11 Frontend | [Frontend §1-7](./2026-06-12-geojson-frontend.md) |
| §12 Seed data | [Seed §1-7](./2026-06-12-geojson-seed.md) |
| §13 Docker | [Foundation §6](./2026-06-12-geojson-foundation.md#6-docker) |
| §14 CI | [CI §1-3](./2026-06-12-geojson-ci.md) |
| §15 Tests | Co-located with each feature spec |
| §16 README | [Docs §1-3](./2026-06-12-geojson-docs.md) |
| §17 AGENTS.md alignment | **this spec, below** |
| §18 Out of scope for v1 | **this spec, below** |
| §19 Decisions and trade-offs | **this spec, below** |
| §20 Open follow-ups | **this spec, below** |

## 3. Test placement

Tests are co-located with the spec that owns the code they
exercise. Across the 8 specs, ~30 tests are split as:

- `accounts/tests/test_auth.py` — 10 tests
  ([Auth §7](./2026-06-12-geojson-auth.md#7-tests))
- `features/tests/test_models.py` — 4 tests
  ([Feature Data Model §4](./2026-06-12-geojson-feature-model.md#4-tests))
- `features/tests/test_serializers.py` — 4 tests
- `features/tests/test_views.py` — 6 tests
- `features/tests/test_bbox_filter.py` — 6 tests
- `features/tests/test_pagination.py` — 5 tests
- `features/tests/test_search.py` — 3 tests
- `features/tests/test_geojson_roundtrip.py` — 2 tests
  ([Feature API §9](./2026-06-12-geojson-feature-api.md#9-tests))
- `features/tests/management/test_seed_features.py` — 5 tests
  ([Seed §8](./2026-06-12-geojson-seed.md#8-tests))

Fixtures live next to the spec that introduces them: `user` and
`other_user` in [Auth §7](./2026-06-12-geojson-auth.md#7-tests),
`auth_client` and `make_feature` in
[Feature API §9](./2026-06-12-geojson-feature-api.md#9-tests).

## 17. AGENTS.md alignment

The existing `AGENTS.md` rules apply unchanged:

- Pre-commit gate (`pre-commit run --all-files` before any commit).
- Ruff with the configured rule set (E, W, F, I, N, UP, B, C4, SIM, PERF, D).
- Editorconfig LF + UTF-8.
- Python conventions: keyword args for multi-arg calls, public functions
  before private helpers, blank line after dedent, ≤ 3 levels of nesting,
  PEP 8 naming, no shortened names, top-of-file imports, ≤ 100-line
  functions.

The implementation will follow these conventions. The spec itself does not
introduce any new convention that contradicts them.

## 18. Out of scope for v1

Explicitly NOT in this spec:

- Django admin registration (deferred; one-liner if needed).
- Token blacklist / server-side logout.
- Geometry editing on the map (no `modify` interaction).
- Multi-feature select / bulk edit.
- KML, CSV, or shapefile parsing.
- Per-user feature ownership.
- Per-type property schemas (polymorphic GeoJSON). v1 has the same
  three property keys (`name`, `color`, `category`) on every feature;
  per-geometry-type property sets (e.g. `population` for cities,
  `length_km` for roads) are deferred to v2.
- Pydantic validation layer.
- Production deployment configs (only the gunicorn entrypoint and
  `prod.py` settings are provided; real deployment is left to ops).
- OpenAPI schema generation (can be added later with `drf-spectacular`).
- CORS for non-localhost origins beyond the example.
- Email verification on register (requires email service).
- Password reset flow (requires email service).
- Account lockout after N failed logins (requires `django-axes` or
  similar, plus login_attempt tracking).
- HIBP / breach-corpus password check (requires outbound network
  call to k-anonymity API or local corpus file).
- Bounding boxes that cross the antimeridian (the ±180° meridian). The
  `bbox` filter uses `minx,miny,maxx,maxy` and assumes `minx <= maxx`; a
  box like `170,-10,-170,10` (Fiji to the Aleutians, crossing 180°) has
  no valid representation in this format and would return zero results
  or wrong results. Clients crossing the date line must split the request
  into two bboxes and merge results. v1 documents this limitation; v2
  could add a wrap-aware mode.

## 19. Decisions and trade-offs summary

- **Generic geometry** over per-type models: industry default, single
  PostGIS index, single endpoint.
- **Open `properties` JSONField** over typed columns: matches RFC 7946,
  matches the assignment's "name, color e.g." phrasing (signals examples,
  not a fixed schema), matches geojson.io. Locking `name` and `color` as
  DB columns would (a) break the GeoJSON round-trip if `properties` carries
  the same keys with different values, (b) prevent extensible schemas
  (`population`, `tags`, anything else), and (c) make the API reject valid
  GeoJSON that lacks either key. The frontend gives `color` a swatch UI
  affordance, but the server treats it as a regular string.
- **UUID PKs** over auto-increment: no enumeration, friendlier for public
  APIs, no "last inserted ID" race conditions in tests.
- **Fixed 100/page** over configurable: matches the assignment verbatim,
  simplest to test.
- **`{next, prev, results}` wrapper** over DRF's default: matches the
  assignment example exactly. No `count` field.
- **No Pydantic** over Pydantic: simpler, fewer deps, easier for Django
  reviewers. Validation is ~25 lines of plain DRF.
- **JWT with stateless logout** over session auth: matches the assignment's
  "use JWT for authorization" requirement.
- **OpenLayers + Bootstrap via CDN** over a JS build: matches the
  assignment's "html frontend page" wording, no npm pipeline, fast to read.
- **PostGIS in Docker** over a local Postgres: reviewer can `make up` and
  it works on any machine.
- **PostGIS test DB** over SQLite + SpatiaLite: same engine as production,
  what a GIS shop expects.
- **pytest + pytest-django** over Django's TestCase: more idiomatic in 2026,
  better fixture composition.
- **Custom `BboxPageNumberPagination`** over a 3rd-party lib: 30 lines,
  exact field names, exact behavior.
- **Single Draw + Import + Export + Edit** map interactions over a full
  geojson.io clone: 80% of the value at 10% of the code, scope-respecting.
- **Right-side slide-in panel for map-side edit** over a new route: keeps
  map context, matches geojson.io.

## 20. Open follow-ups (not blocking implementation)

- OpenAPI schema generation with `drf-spectacular`.
- Token blacklist for true logout.
- Django admin registration.
- Geometry editing on the map.
- Multi-feature select / bulk edit.
- Additional GeoJSON import formats (KML, CSV, shapefile).
- Per-user feature ownership.
- Real deployment configs (systemd unit, Nginx, etc.).
