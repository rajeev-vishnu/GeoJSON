# GeoJSON API — Design Spec

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

## 2. Stack and tooling

| Concern | Choice | Pinned version |
| --- | --- | --- |
| Language | Python | 3.12 |
| Framework | Django | 5.1.x |
| API | Django REST Framework | 3.15.x |
| Auth | djangorestframework-simplejwt | 5.3.x |
| Geo | djangorestframework-gis | 1.0.x |
| CORS | django-cors-headers | 4.3.x |
| DB driver | psycopg[binary] | 3.1.x |
| Prod server | gunicorn | 22.0.x |
| Database | PostgreSQL + PostGIS | 16 + 3.4 |
| Tests | pytest, pytest-django, pytest-cov | latest 8.x, 4.8.x, 5.x |
| Lint | ruff | already configured in `pyproject.toml` |
| Hooks | pre-commit | already configured |
| CI | GitHub Actions | n/a |
| Frontend | Django templates + Bootstrap 5 + OpenLayers (CDN) | latest |
| Frontend language | Vanilla JS (ES modules) | n/a |
| Build step | None | n/a |
| Container | Docker + docker-compose | n/a |
| Package manager | pip + `pyproject.toml` (no `requirements.txt`) | n/a |

**Dependency management:** all runtime and dev deps live in `pyproject.toml`
under `[project.dependencies]` and `[project.optional-dependencies].dev`. The
Dockerfile and CI install with `pip install -e ".[dev]"`.

**Frontend CDN policy:** Bootstrap 5 and OpenLayers are loaded from
`jsdelivr.net`. The project ships with no `node_modules`.

## 3. Project layout

```
geojson-api/
├── .github/workflows/ci.yml
├── accounts/             # User model + JWT views
│   ├── models.py         # User (custom)
│   ├── managers.py       # UserManager
│   ├── serializers.py    # User, Register, Login
│   ├── views.py          # Register, Login, Refresh, Me
│   ├── urls.py
│   └── tests/test_auth.py
├── config/
│   ├── settings/         # base, dev, prod, test
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── features/             # the domain app
│   ├── models.py         # Feature
│   ├── serializers.py    # FeatureSerializer
│   ├── views.py          # FeatureViewSet
│   ├── pagination.py     # BboxPageNumberPagination
│   ├── filters.py        # parse_bbox, apply_bbox
│   ├── urls.py
│   ├── management/commands/seed_features.py
│   └── tests/            # 8 test files, ~30 tests
├── frontend/
│   ├── templates/        # base, home, login, register, map, edit
│   └── static/
│       ├── css/site.css
│       └── js/           # 8 small ES modules
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── README.md
├── manage.py
├── pyproject.toml
└── .env.example
```

## 4. Data model

### `accounts.User`

Custom user model. Inherits `AbstractBaseUser` only (no `PermissionsMixin`,
no `is_staff` / `is_superuser` — admin is deferred, see Section 18).
`USERNAME_FIELD = "email"`. `REQUIRED_FIELDS = []` (no username).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `UUIDField` (PK, default `uuid4`) | Stable IDs. |
| `email` | `EmailField` (unique) | Login identifier. |
| `password` | `CharField` | Hashed by `set_password()`. |
| `is_active` | `BooleanField` (default True) | Standard. |

No `username`, no `is_staff`, no `is_superuser`, no `last_login`, no
`date_joined`. Django's `BaseUserManager` is subclassed with
`create_user(email, password)`; `create_superuser` is **not** defined.
Users are created via the public register endpoint (see the auth
endpoints table in the API contract section).

**Password validators.** `AUTH_PASSWORD_VALIDATORS` in
`config/settings/base.py` configures Django's 4 built-in validators, in
this order:

1. `UserAttributeSimilarityValidator` — rejects passwords too similar to
   the user's email.
2. `MinimumLengthValidator(min_length=8)` — minimum length, per
   NIST SP 800-63B. 12+ is recommended but 8 is the hard floor.
3. `CommonPasswordValidator` — rejects Django's bundled top-20k list of
   common passwords.
4. `NumericPasswordValidator` — rejects all-numeric passwords.

Policy decisions, justified by NIST SP 800-63B:

- **No composition rules** (no "must contain uppercase + number + symbol").
  These rules are counterproductive; they push users to `Password1!`.
- **No maximum length** beyond Django's 4096-char input cap.
- **All characters allowed**, including spaces and Unicode.
- **No periodic rotation** (the "rotate every 90 days" rule is
  deprecated).

The same validators run on user creation and on future password change
(v2). `RegisterSerializer` calls `validate_password()` from
`django.contrib.auth.password_validation` (see the Serializers
section).

### `features.Feature`

Single model. Generic geometry. Open `properties` JSONField (no typed columns).

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `UUIDField` (PK, default `uuid4`) | Stable IDs. |
| `geometry` | `GeometryField(srid=4326)` | Accepts all 6 GeoJSON geometry types. GiST spatial index. |
| `properties` | `JSONField(default=dict)` | The only "data" beyond geometry. Fully open `dict[str, JsonValue]`. |
| `created_by` | `FK(User, on_delete=CASCADE)` | Audit trail only; no per-user ownership, so deletion takes the user's features with them. |
| `created_at` | `DateTimeField(auto_now_add)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

`Meta.indexes`:

- `GistIndex(fields=["geometry"])`
- `BTreeIndex(fields=["-updated_at"])` — supports the list endpoint's default
  sort (`-updated_at, id`).

**No `Meta.ordering`.** Default sort is set explicitly in
`FeatureViewSet.get_queryset()` as `order_by("-updated_at", "id")` so the
model has no hidden behavior. Tests and other call sites must sort
explicitly.

**No first-class `name` or `color` columns.** Those are values inside
`properties`, treated the same as any other property. See Section 19
("Decisions and trade-offs summary") for the rationale.

## 5. API contract

Base path: `/api/`. Auth: `Authorization: Bearer <access_token>` header.
Pagination: 100 results per request, fixed.

### Auth endpoints

| Method | Path | Auth | Body | Response |
| --- | --- | --- | --- | --- |
| `POST` | `/api/auth/register/` | none | `{email, password, password_confirm}` | `201 {id, email}` |
| `POST` | `/api/auth/login/` | none | `{email, password}` | `200 {access, refresh}` |
| `POST` | `/api/auth/refresh/` | none | `{refresh}` | `200 {access, refresh}` (rotated) |
| `GET` | `/api/auth/me/` | required | — | `200 {id, email}` |

JWT lifetimes: access 15 min, refresh 7 days, `ROTATE_REFRESH_TOKENS=True`,
`BLACKLIST_AFTER_ROTATION=False` in v1 (no token blacklist). The frontend
deletes tokens from `localStorage` on logout. Standard error responses:

- `401 Unauthorized` for missing or invalid `Authorization` header.
- `401 Unauthorized` for an expired access token.
- `401 Unauthorized` for a refresh token that has been rotated already.
- `403 Forbidden` if we ever add permission classes (not used in v1).

**Login enumeration.** The login endpoint returns the same generic
`401 {"detail": "No active account found with the given credentials"}`
whether the email doesn't exist or the password is wrong. The
`LoginSerializer` does not include the user object in errors, and the
`validate()` method returns the SimpleJWT auth failure unchanged. This
prevents attackers from using the login endpoint to enumerate which
emails are registered.

### Feature endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/features/` | required | List, paged, bbox-filterable, searchable. |
| `GET` | `/api/features/{id}/` | required | Retrieve one. |
| `POST` | `/api/features/` | required | Create. |
| `PATCH` | `/api/features/{id}/` | required | Partial update. |
| `PUT` | `/api/features/{id}/` | required | Full update. |
| `DELETE` | `/api/features/{id}/` | required | Delete. |

**List query parameters:**

- `bbox` (optional): `minx,miny,maxx,maxy` in WGS84.
- `page` (optional, default `1`): page number.
- `search` (optional): case-insensitive substring on `properties->>'name'`.
- `ordering` (optional): one of `name`, `-name`, `created_at`, `-created_at`,
  `updated_at`, `-updated_at`. Default `-updated_at`.

**List response shape (200):**

```json
{
  "next": "http://host/api/features/?bbox=-10,40,5,55&page=2",
  "prev": null,
  "results": [ <Feature>, <Feature>, ... ]
}
```

`next` is `null` on the last page. `prev` is `null` on the first page.
100 features per request, hardcoded as `PAGE_SIZE = 100` in
`features/pagination.py`. 404 on `page` past the last page. 400 on invalid
`bbox` (wrong arity, out-of-range values, min > max). 400 on invalid `page`
(non-integer, < 1).

**Feature wire format (RFC 7946):**

```json
{
  "type": "Feature",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "geometry": { "type": "Point", "coordinates": [10.0, 20.0] },
  "properties": {
    "name": "Foo",
    "color": "#ff0000",
    "population": 1200
  }
}
```

No `created_at` / `updated_at` / `created_by` on the list wire (the assignment
example shows plain Features). The detail endpoint includes them in a wrapper
key `_meta` inside `properties` (foreign-member pattern from RFC 7946):

```json
{
  "type": "Feature",
  "id": "...",
  "geometry": {...},
  "properties": {
    "name": "Foo",
    "color": "#ff0000",
    "_meta": {
      "created_at": "2026-06-12T10:30:00Z",
      "updated_at": "2026-06-12T10:30:00Z",
      "created_by": "..."
    }
  }
}
```

## 6. Bbox filter

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
3. `.filter(properties__name__icontains=search)` (skipped when no `search`).
4. `.order_by("-updated_at", "id")` — the default sort; `?ordering=...`
   overrides this.

PostGIS uses the GiST index on `geometry` for the bbox filter.

The bbox param is optional. Omitting it returns all features, still paged.

## 7. Validation

Pure DRF. No Pydantic.

- `geometry` is validated by `rest_framework_gis.serializers.GeoJSONGeometryField`,
  which accepts all 6 standard GeoJSON geometry types and rejects malformed
  coordinates.
- `properties` is a `serializers.JSONField()` with a `validate_properties()`
  method that:
  1. Treats `None` as `{}`.
  2. Rejects non-dict values with a 400 ("properties must be a JSON object").
  3. Recursively checks all values are JSON-serializable (`str | int | float
     | bool | None | list | dict`).
  4. Validates keys are non-empty strings.
- `type` field is ignored on input (we always emit `"Feature"` on output).
- The 400 response uses DRF's default error format:
  `{"detail": "..."}` for non-field errors and `{"<field>": ["..."]}` for
  field-level errors.

## 8. Pagination

`features/pagination.py` defines `BboxPageNumberPagination(PageNumberPagination)`:

- `page_size = 100` (hardcoded, not configurable via query string).
- `page_query_param = "page"`.
- Custom `get_paginated_response()` returns exactly `{ next, prev, results }`.
- `next` and `prev` are built by `request.build_absolute_uri()` so they
  preserve query string params (`bbox`, `ordering`, `search`).
- 404 on `page` past the last page (DRF default).
- No `count` field in the response (matches the assignment example exactly).

## 9. Serializers

- `features/serializers.py`:
  - `FeatureSerializer(ModelSerializer)` — `geometry` via
    `GeoJSONGeometryField`, `properties` via `JSONField` with
    `validate_properties()`. Read-only: `id`, `created_at`, `updated_at`,
    `created_by`.
  - `FeatureListItemSerializer(FeatureSerializer)` — overrides `to_representation`
    to strip `_meta` for list responses. Used by the paginator.
- `accounts/serializers.py`:
  - `UserSerializer` — read-only `{id, email}`.
  - `RegisterSerializer` — `{email, password, password_confirm}`. Validates
    `password == password_confirm`, email uniqueness, and calls
    `validate_password()` from `django.contrib.auth.password_validation`
    so the 4 `AUTH_PASSWORD_VALIDATORS` (defined just above) run
    on register.
    On success, creates the user via `User.objects.create_user(email, password)`.
  - `LoginSerializer` — `{email, password}`. Fields-only validation;
    SimpleJWT does the auth. Returns the same generic failure whether
    the email is unknown or the password is wrong (see "Login
    enumeration" below the auth-endpoints table).

## 10. URL routing

```python
# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("frontend.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("features.urls")),
]
```

- `frontend/urls.py` routes `/`, `/map/`, `/edit/`, `/login/`, `/register/`
  to view functions that render templates.
- `accounts/urls.py` routes the 4 auth endpoints.
- `features/urls.py` is a DRF `DefaultRouter` with `FeatureViewSet`
  registered as `features`.

**API authentication classes.** Both API viewsets and auth views set
`authentication_classes = [JWTAuthentication]` only — `SessionAuthentication`
is not used, so the API is unaffected by CSRF (JWT in the
`Authorization` header is not auto-attached by browsers, so CSRF doesn't
apply). The frontend templates (login form, register form) use Django's
standard CSRF protection via `{% csrf_token %}` and POST to the
auth endpoints with the token in a form-encoded body — those requests
are protected by Django's CSRF middleware.

## 11. Frontend

Two server-rendered HTML pages plus a top nav, login, and register. Bootstrap
5 + OpenLayers via CDN. Vanilla JS ES modules, no build step.

### Routes and templates

| Route | Template | Auth | Purpose |
| --- | --- | --- | --- |
| `GET /` | `home.html` | none | Landing, two big buttons, login state. |
| `GET /map/` | `map.html` | required | OpenLayers map with bbox filter, draw, import, export, click-to-edit panel, search. |
| `GET /edit/` | `edit.html` | required | Server-paged table of all features and their properties. |
| `GET /login/` | `login.html` | none | Login form. |
| `GET /register/` | `register.html` | none | Registration form. |

### Top nav (visible on `/map/` and `/edit/`)

```
[Logo] [Map] [Edit Properties]   [🔍 Search by name...]   [user@email] [Logout]
```

Search bar is debounced 250ms. On input, GETs
`/api/features/?search=<query>&page=1`, renders a Bootstrap dropdown of up
to 10 results. Each result row shows `properties.name`, a `properties.color`
swatch, and the geometry type. Click result → map flies to the feature's
centroid and opens the right-side edit panel. Esc closes the dropdown.

### Map page features

1. **Viewport-driven bbox filter** with debounced 250ms `moveend`. "Load more"
   button appends subsequent pages.
2. **Draw mode** with Point/Line/Polygon picker. On draw finish, a Bootstrap
   modal asks for one key + one value (the user can add more on the edit
   page). POSTs the new feature, refreshes the map.
3. **Import `.geojson`**: file input, parsed with `ol/format/GeoJSON`, rendered
   on the map temporarily, "Save all to server" button batch-POSTs.
4. **Export `.geojson`**: assembles the in-memory features into a
   FeatureCollection, triggers a download.
5. **Click a feature** → right-side slide-in panel with a key/value table
   for that one feature. Inline-edit each property (PATCH on Enter,
   Esc cancels). "Delete feature" button at the panel bottom.
6. **Search bar** (top nav, see above).
7. **No `modify` interaction** in v1 (geometry editing is out of scope).
8. **No multi-select** in v1 (single-feature click only).

### Edit page features

1. Server-paged table of all features. For each feature, a sub-table of
   `properties` rows: key, value, type badge, × delete, + add new.
2. Inline edit per row (PATCH on Enter, Esc cancels). Key is not editable
   in v1 (avoids breaking map color references).
3. Pagination Prev/Next at the bottom (disabled when `prev` / `next` is `null`).
4. Sort dropdown (default `-updated_at`).
5. No bulk-edit, no multi-select.

### Static assets

- `frontend/static/css/site.css` — ≤ 100 lines. Includes the right-side
  panel slide-in animation and the search dropdown styling.
- `frontend/static/js/`:
  - `api.js` — `fetch` wrapper with token refresh on 401.
  - `auth.js` — login/logout, token storage in `localStorage`.
  - `map.js` — OpenLayers map setup, bbox debounce, feature rendering.
  - `map-draw.js` — draw interaction.
  - `map-import.js` — GeoJSON import/export.
  - `map-panel.js` — right-side panel for inline edit.
  - `search.js` — top-nav search dropdown with debounce and fly-to.
  - `edit.js` — edit-page table with inline edit and pagination.

Each module is a small ES module loaded with `<script type="module">` from
the template. `api.js` and `auth.js` are shared via `{% include %}`-style
script tags in `base.html`.

**Token storage trade-off.** Tokens live in `localStorage`, which is
XSS-readable. This is the standard pragmatic choice for a small SPA
with no `httpOnly`-cookie infrastructure; the alternative (`httpOnly`
cookies + CSRF tokens on the API) is significantly more code and
requires splitting the auth flow between cookie + header. v1 accepts
this trade-off. Mitigations:

- `Content-Security-Policy: default-src 'self'; script-src 'self'
  https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net
  'unsafe-inline'; img-src 'self' data:; connect-src 'self'` is set
  in `prod.py` to reduce XSS blast radius (no inline scripts, no
  third-party scripts beyond the CDN).
- No user-supplied content is ever rendered as HTML in the frontend
  (always as text or via safe `textContent`).
- Frontend has no third-party analytics, ads, or comment widgets.
- Logout deletes both `access` and `refresh` from `localStorage`.

A `v2` migration to `httpOnly` cookies + CSRF is a follow-up (open
follow-up, Section 20).

## 12. Seed data

`features/management/commands/seed_features.py` creates 1,000 features
inside a configurable bbox (default: continental US). Idempotent
(truncates and re-seeds on each run, behind a `--keep` flag). Three
property shapes mixed:

- Point: `{name, color, population, is_capital}`.
- Polygon: `{name, color, area_km2, land_use}`.
- LineString: `{name, color, length_km, road_class}`.

This demonstrates the open-properties model in practice. Reviewers can
search by name, see varied property shapes, and exercise all geometry
types and the bbox filter at world/region scale.

## 13. Docker

`docker-compose.yml` (no `version:` key, modern Compose):

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: geojson
      POSTGRES_USER: geojson
      POSTGRES_PASSWORD: geojson
    volumes: [pgdata:/var/lib/postgresql/data]
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U geojson"]
      interval: 5s
      timeout: 5s
      retries: 10

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    env_file: .env
    volumes: [.:/app]
    ports: ["8000:8000"]
    depends_on:
      db: { condition: service_healthy }

  migrate:
    build: .
    command: python manage.py migrate --noinput
    env_file: .env
    depends_on:
      db: { condition: service_healthy }
    restart: "no"

volumes:
  pgdata:
```

`Dockerfile` is multi-stage with `python:3.12-slim` and installs the project
editable with dev extras (`pip install -e ".[dev]"`). Gunicorn is the default
`CMD`; the dev compose service overrides with `runserver`.

`Makefile` targets: `up`, `down`, `migrate`, `seed`, `test`, `lint`, `shell`.

`.env.example` is committed; `.env` is git-ignored. The example file shows:
`DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
`DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `JWT_ACCESS_MINUTES`,
`JWT_REFRESH_DAYS`, `CORS_ALLOWED_ORIGINS`.

**Production security settings (`config/settings/prod.py`).** All of the
following are `False` in `dev.py` and `test.py`, and `True` in `prod.py`:

| Setting | Value | Purpose |
| --- | --- | --- |
| `SECURE_SSL_REDIRECT` | `True` | Force HTTPS. |
| `SESSION_COOKIE_SECURE` | `True` | Cookies only over HTTPS. |
| `CSRF_COOKIE_SECURE` | `True` | CSRF cookie only over HTTPS. |
| `SECURE_HSTS_SECONDS` | `31_536_000` | HSTS for 1 year. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | HSTS covers subdomains. |
| `SECURE_HSTS_PRELOAD` | `True` | Eligible for browser preload list. |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | Block MIME-type sniffing. |
| `SECURE_REFERRER_POLICY` | `"same-origin"` | Referer only for same-origin. |
| `X_FRAME_OPTIONS` | `"DENY"` | Block clickjacking. |
| `SECURE_PROXY_SSL_HEADER` | `("HTTP_X_FORWARDED_PROTO", "https")` | Trust the proxy's XFP header (so `SECURE_SSL_REDIRECT` works behind a reverse proxy). |

`prod.py` also sets the `Content-Security-Policy` header via a custom
middleware or `SECURE_CSP` (Django 5.1+), with the policy from Section 11
(`default-src 'self'`, etc.). `DEBUG = False` is enforced via the env
var, and the prod settings file raises `ImproperlyConfigured` at
import time if `DJANGO_SECRET_KEY` is the example placeholder.

## 14. CI

`.github/workflows/ci.yml` runs on push and PR:

1. Spin up `postgis/postgis:16-3.4` as a service container with a test DB.
2. Checkout, setup Python 3.12 with pip cache.
3. `pip install -e ".[dev]"`.
4. `pre-commit run --all-files`.
5. `pytest --cov=features --cov=accounts --cov=config --cov-fail-under=80`.
6. Upload coverage to Codecov.

A `config/settings/test.py` is included that turns off email, uses the test
DB URL from env, and disables host header checks.

## 15. Tests

Coverage target: 80%+ on `features/`, `accounts/`, `config/`. ~30 tests.

Test files and what they cover:

- `accounts/tests/test_auth.py` — register success/fail, login success/fail,
  refresh, /me, JWT required.
- `features/tests/test_models.py` — Feature creation, default values,
  geometry round-trip, `created_by` FK.
- `features/tests/test_serializers.py` — geometry in/out, properties
  validation (rejects non-dict, non-JSON), read-only fields, create vs
  update.
- `features/tests/test_views.py` — list, retrieve, create, update,
  partial_update, delete, auth required, pagination response shape.
- `features/tests/test_bbox_filter.py` — fixtures spread across the world,
  filter by various bboxes, verify counts and IDs. Invalid bboxes return
  400.
- `features/tests/test_pagination.py` — page 1, page 2, last page, past
  last page (404), page=0 (400), `next`/`prev` URL building with `bbox`
  preserved.
- `features/tests/test_search.py` — features with varied `properties.name`,
  substring search, verify filter.
- `features/tests/test_geojson_roundtrip.py` — POST a feature with nested
  objects/arrays in `properties`, GET it back, verify exact equality.
- `features/tests/management/test_seed_features.py` — run the command,
  verify N features exist with varied shapes.

Custom fixtures in `features/tests/conftest.py`:

- `user` — a regular user (the standard fixture; used by all auth tests).
- `other_user` — a second user, for tests that need two principals.
- `auth_client(api_client, user)` — DRF APIClient with a valid JWT in the
  `Authorization` header.
- `make_feature` — factory creating features with sensible defaults.

## 16. README

Single `README.md`, ~200 lines. Sections:

1. Project description + ASCII architecture diagram.
2. Features (bulleted).
3. Quick start (`cp .env.example .env && make up && make migrate && make
   seed`). There is no `createsuperuser`; register a user with the form at
   `/register/`.
4. Architecture overview + pointers to key files.
5. API reference (curl examples for login, list with bbox, create, patch).
6. Frontend pages (with screenshots added during implementation).
7. Development (`make test`, `make lint`, `make shell`).
8. Deployment notes (gunicorn, `prod.py` settings, CORS).
9. Decisions and trade-offs (open properties, fixed 100/page, no Pydantic,
   PostGIS test DB).

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
- Per-type property schemas (polymorphic GeoJSON).
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
