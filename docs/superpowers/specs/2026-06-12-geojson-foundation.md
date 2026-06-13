# GeoJSON API — Foundation & Tooling Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** —
**Required by:** Auth, Feature Data Model, Feature API, Seed, Frontend, CI, Docs

## 1. Purpose

The cross-cutting infrastructure for the project: language and
framework versions, project layout, settings split, Docker
configuration, Makefile targets, environment variables, and
production security settings. Everything every other spec needs but
no other spec owns.

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

**Dependency management:** all runtime and dev deps live in
`pyproject.toml` under `[project.dependencies]` and
`[project.optional-dependencies].dev`. The Dockerfile and CI install
with `pip install -e ".[dev]"`.

**Frontend CDN policy:** Bootstrap 5 and OpenLayers are loaded from
`jsdelivr.net`. The project ships with no `node_modules`. The
Content-Security-Policy header that allows this is defined in
§10 and consumed by the [Frontend spec](./2026-06-12-geojson-frontend.md).

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

## 4. Settings split

`config/settings/` is a package with one module per environment:

- `base.py` — common settings (apps, middleware, templates, auth
  password validators from the
  [Auth spec §3](./2026-06-12-geojson-auth.md#3-password-validators),
  REST_FRAMEWORK defaults pointing at `JWTAuthentication`,
  `DEFAULT_PAGINATION_CLASS = None`, `PAGE_SIZE` not used at the
  global level). Imports `DATABASE_URL` via `dj-database-url`.
- `dev.py` — `DEBUG=True`, console email backend, SQLite-style
  relaxed checks, PostGIS via docker-compose `db` service.
- `prod.py` — `DEBUG=False`, security settings from §10, CSP
  middleware, gunicorn-friendly, `STATIC_ROOT` collected at deploy.
- `test.py` — extends `base.py`, `DEBUG=False`, in-memory email
  backend (`locmem`), uses the test DB URL from env, disables host
  header checks. Used by CI (see [CI spec](./2026-06-12-geojson-ci.md)).

Selection is via `DJANGO_SETTINGS_MODULE`:

- `DJANGO_SETTINGS_MODULE=config.settings.dev` — default in
  docker-compose and `manage.py runserver`.
- `DJANGO_SETTINGS_MODULE=config.settings.prod` — gunicorn entrypoint.
- `DJANGO_SETTINGS_MODULE=config.settings.test` — set by
  `pytest.ini` / `pyproject.toml [tool.pytest.ini_options]`.

`prod.py` raises `ImproperlyConfigured` at import time if
`DJANGO_SECRET_KEY` is the example placeholder from `.env.example`.

## 5. Root URL routing

```python
# config/urls.py
urlpatterns = [
    path("", include("frontend.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("features.urls")),
]
```

The Django admin URL (`path("admin/", admin.site.urls)`) is **not**
included. Admin is fully out of scope for v1 (see [Overview
§18](./2026-06-12-geojson-api-design.md#18-out-of-scope-for-v1)),
including its URL route — adding it back is a one-line change if/when
an admin is needed.

## 6. Docker

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

`Dockerfile` is multi-stage with `python:3.12-slim` and installs the
project editable with dev extras (`pip install -e ".[dev]"`).
Gunicorn is the default `CMD`; the dev compose service overrides
with `runserver`.

## 7. Makefile

Targets: `up`, `down`, `migrate`, `seed`, `test`, `lint`, `shell`.

- `make up` — `docker-compose up -d` (starts `db` and `web`).
- `make down` — `docker-compose down`.
- `make migrate` — runs the `migrate` compose service.
- `make seed` — `docker-compose exec web python manage.py seed_features`.
- `make test` — `docker-compose exec web pytest`.
- `make lint` — `docker-compose exec web ruff check .`.
- `make shell` — `docker-compose exec web python manage.py shell`.

## 8. Environment variables

`.env.example` is committed; `.env` is git-ignored. The example file
shows the keys the application reads:

| Key | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` (default), `prod`, or `test`. |
| `DJANGO_SECRET_KEY` | Required; `prod.py` rejects the example placeholder. |
| `DJANGO_DEBUG` | `True` in dev/test, `False` in prod. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host list. |
| `DATABASE_URL` | `postgres://geojson:geojson@db:5432/geojson` in compose. |
| `JWT_ACCESS_MINUTES` | Access-token lifetime; default 15. |
| `JWT_REFRESH_DAYS` | Refresh-token lifetime; default 7. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins for `django-cors-headers`. |

## 9. Production security settings

All of the following are `False` in `dev.py` and `test.py`, and
`True` in `prod.py`:

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

## 10. Content-Security-Policy

`prod.py` sets the `Content-Security-Policy` header via a custom
middleware or `SECURE_CSP` (Django 5.1+):

```
default-src 'self'; script-src 'self' https://cdn.jsdelivr.net;
style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline';
img-src 'self' data:; connect-src 'self'
```

The CSP is consumed by the [Frontend spec](./2026-06-12-geojson-frontend.md)
to confirm the page-load behavior matches (no inline scripts, no
third-party scripts beyond the CDN).
