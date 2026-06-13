# GeoJSON API — Documentation Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** All other child specs (the README documents the
whole project)
**Required by:** —

## 1. Purpose

Single `README.md` at the repo root, ~200 lines, that orients a
new reviewer: what the project is, how to run it, where the
interesting code lives, how to call the API, and what the
important decisions were.

## 2. Sections

1. **Project description + ASCII architecture diagram.**

   Two short paragraphs: what the project is (Django + PostGIS
   GeoJSON API with HTML frontend) and what the reviewer is
   graded on (idiomatic Django/DRF, correct PostGIS usage,
   lossless GeoJSON round-trip, Docker, tests, CI). One ASCII
   block diagram showing the request path: browser → Django
   templates (frontend) or fetch from JS → DRF viewsets →
   `parse_bbox` + `BboxPageNumberPagination` + `FeatureSerializer`
   → PostGIS (GiST + BTree + trigram GIN) → JSON response.

2. **Features** (bulleted list).

   - Bbox-filterable, paged, searchable GeoJSON list endpoint.
   - Full CRUD on features.
   - `/api/categories/` enum source.
   - JWT auth (register, login, refresh, me).
   - OpenLayers map with draw, import, export, click-to-edit
     panel, debounced bbox filter, search.
   - Edit page with paged table and inline-edit per property
     (type-preserving).
   - Seeded deterministic NL dataset covering all 7 GeoJSON
     geometry types.
   - Docker + docker-compose + Makefile.
   - 80%+ test coverage with CI.

3. **Quick start.**

   ```sh
   cp .env.example .env
   make up
   make migrate
   make seed
   ```

   Then open `http://localhost:8000/`. There is **no
   `createsuperuser`**; the project uses the public register
   endpoint. After the seed runs, register a user with the form
   at `/register/`, log in, and visit `/map/` and `/edit/`.

4. **Architecture overview + pointers to key files.**

   - `config/settings/` — split between `base`, `dev`, `prod`,
     `test`.
   - `accounts/` — custom `User` model, JWT views,
     `RegisterSerializer` (NIST-aligned password validators),
     `LoginSerializer` (no enumeration).
   - `features/models.py` — `Feature` with GiST, BTree, and
     trigram GIN indexes; `Category` enum.
   - `features/views.py` — `FeatureViewSet` with the
     bbox/search/ordering chain.
   - `features/serializers.py` — `FeatureSerializer`,
     `FeatureListItemSerializer` (strips `_audit`).
   - `features/pagination.py` — `BboxPageNumberPagination`.
   - `features/filters.py` — `parse_bbox()`.
   - `features/management/commands/seed_features.py` — the
     deterministic seed.
   - `frontend/templates/`, `frontend/static/js/`, and
     `frontend/static/css/site.css` — the HTML pages and 8 ES
     modules.
   - `pyproject.toml` — pinned versions and dev extras.

5. **API reference** (curl examples).

   - **Login** (capture the access token):

     ```sh
     curl -X POST http://localhost:8000/api/auth/login/ \
       -H "Content-Type: application/json" \
       -d '{"email":"alice@example.com","password":"hunter2hunter2"}'
     ```

   - **List features in a bbox** (NL bbox, page 1):

     ```sh
     curl http://localhost:8000/api/features/?bbox=3.3,50.7,7.3,53.55&page=1 \
       -H "Authorization: Bearer $TOKEN"
     ```

   - **Create a feature** (Point in Amsterdam):

     ```sh
     curl -X POST http://localhost:8000/api/features/ \
       -H "Authorization: Bearer $TOKEN" \
       -H "Content-Type: application/json" \
       -d '{
         "geometry": {"type":"Point","coordinates":[4.9,52.37]},
         "properties": {"name":"Amsterdam","color":"#e41a1c","category":"city"}
       }'
     ```

   - **Patch a feature's `name`**:

     ```sh
     curl -X PATCH http://localhost:8000/api/features/$ID/ \
       -H "Authorization: Bearer $TOKEN" \
       -H "Content-Type: application/json" \
       -d '{"properties":{"name":"New name"}}'
     ```

   Note that the PATCH is additive on `properties`: keys not in
   the body are preserved.

6. **Frontend pages** (with screenshots added during
   implementation).

   - `/` — landing.
   - `/register/` and `/login/` — auth forms.
   - `/map/` — OpenLayers map; bbox filter, draw, import,
     export, search.
   - `/edit/` — paged property table with inline edit.

7. **Development.**

   - `make test` — run the full pytest suite.
   - `make lint` — `ruff check .` (configured in
     `pyproject.toml`).
   - `make shell` — open a Django shell inside the web
     container.
   - `pre-commit run --all-files` — the pre-commit gate from
     [AGENTS.md](../../../../AGENTS.md). Must pass before any
     commit.

8. **Deployment notes** (gunicorn, `prod.py` settings, CORS).

   - Production server: `gunicorn config.wsgi:application`
     bound to a Unix socket or `0.0.0.0:8000`.
   - `DJANGO_SETTINGS_MODULE=config.settings.prod` for the
     gunicorn process.
   - `prod.py` enforces `DEBUG=False`, the security settings
     from
     [Foundation spec §9](./2026-06-12-geojson-foundation.md#9-production-security-settings),
     the CSP from
     [Foundation spec §10](./2026-06-12-geojson-foundation.md#10-content-security-policy),
     and rejects the example `DJANGO_SECRET_KEY` placeholder.
   - `CORS_ALLOWED_ORIGINS` env var lists the public origins
     allowed to call the API.
   - Real deployment configs (systemd unit, Nginx, container
     orchestration) are out of scope for v1 — only the
     gunicorn entrypoint and `prod.py` settings are provided.
     See
     [Overview §18](./2026-06-12-geojson-api-design.md#18-out-of-scope-for-v1).

9. **Decisions and trade-offs** (pointers to
   [Overview §19](./2026-06-12-geojson-api-design.md#19-decisions-and-trade-offs-summary)).

   - Generic geometry over per-type models.
   - Open `properties` JSONField over typed columns.
   - UUID PKs over auto-increment.
   - Fixed 100/page over configurable.
   - `{next, prev, results}` wrapper over DRF's default.
   - No Pydantic.
   - JWT with stateless logout.
   - OpenLayers + Bootstrap via CDN (no npm pipeline).
   - PostGIS in Docker.
   - PostGIS test DB (not SQLite + SpatiaLite).
   - pytest + pytest-django.
   - Custom `BboxPageNumberPagination`.
   - Single Draw + Import + Export + Edit map interactions.
   - Right-side slide-in panel for map-side edit.

## 3. Style

- ~200 lines, no longer.
- Use fenced code blocks with `sh` / `json` / `python`
  languages.
- Every link to a sibling spec uses a relative file path so the
  README stays usable when checked out on its own.
- No emoji, no badges, no auto-generated TOC (the 9 numbered
  sections are the TOC).
- The screenshot section is a placeholder list — concrete images
  are added during implementation when the frontend is stable.
