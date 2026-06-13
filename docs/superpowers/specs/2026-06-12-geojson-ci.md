# GeoJSON API — CI Spec

**Date:** 2026-06-12
**Status:** Approved for implementation
**Parent:** [2026-06-12-geojson-api-design.md](./2026-06-12-geojson-api-design.md)
**Depends on:** [Foundation](./2026-06-12-geojson-foundation.md), [Auth](./2026-06-12-geojson-auth.md), [Feature Data Model](./2026-06-12-geojson-feature-model.md), [Feature API](./2026-06-12-geojson-feature-api.md), [Seed](./2026-06-12-geojson-seed.md), [Frontend](./2026-06-12-geojson-frontend.md)
**Required by:** Docs

## 1. Purpose

GitHub Actions workflow that runs on push and pull request, plus
the `config/settings/test.py` it relies on. The workflow spins up
PostGIS, installs the project, runs pre-commit and pytest, and
uploads coverage to Codecov.

## 2. Workflow

`.github/workflows/ci.yml` runs on push and PR.

### Triggers

- `on: push` to any branch.
- `on: pull_request` targeting any branch.

### Service container

Spin up `postgis/postgis:16-3.4` as a service container with a
test database:

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    env:
      POSTGRES_DB: geojson_test
      POSTGRES_USER: geojson
      POSTGRES_PASSWORD: geojson
    ports: ["5432:5432"]
    options: >-
      --health-cmd "pg_isready -U geojson"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 10
```

`DATABASE_URL` is set to
`postgres://geojson:geojson@localhost:5432/geojson_test` in the
job's env.

### Job steps

1. **Checkout** the repository at the current SHA.
2. **Set up Python 3.12** with `actions/setup-python@v5` and the
   pip cache.
3. **Install** the project: `pip install -e ".[dev]"`.
4. **Pre-commit**: `pre-commit run --all-files`. Per
   [AGENTS.md](../../../../AGENTS.md), this is the pre-commit gate
   and must pass before the task is considered done.
5. **Migrate**: `pytest` will create the test DB automatically via
   `pytest-django`, but the migration that installs `pg_trgm`
   (see
   [Feature Data Model spec §2](./2026-06-12-geojson-feature-model.md#2-featuresfeature-model))
   must run, so the workflow runs
   `python manage.py migrate` against the test DB as a separate
   step before pytest. (Alternatively, the test session's
   `migrate` command covers this; the workflow chooses whichever
   pattern pytest-django is configured with.)
6. **Seed** (optional, only for the trigram-index EXPLAIN test in
   [Feature API spec §9](./2026-06-12-geojson-feature-api.md#9-tests)):
   if the test suite includes the index-usage assertion, the
   job runs `python manage.py seed_features --count=1000
   --seed=42` so the planner has enough rows to choose the index.
7. **Pytest**:
   `pytest --cov=features --cov=accounts --cov=config
   --cov-fail-under=80`.
8. **Codecov** upload with `codecov/codecov-action@v4` (token
   from repo secret `CODECOV_TOKEN`).

## 3. `config/settings/test.py`

Extends `base.py`. Differences from `dev.py`:

- `DEBUG = False`.
- Email backend is `locmem.EmailBackend` (no SMTP, no
  console).
- `DATABASE_URL` is read from the env; in CI the workflow sets
  it to the service-container URL above.
- `ALLOWED_HOSTS = ["*"]` (or `["testserver", "localhost"]` plus
  any container hostnames) so the test client's host header
  check passes.
- `SECURE_SSL_REDIRECT = False` and the rest of the prod
  security settings from
  [Foundation spec §9](./2026-06-12-geojson-foundation.md#9-production-security-settings)
  remain `False` (they are `False` in `base.py` by default; only
  `prod.py` flips them).
- `CSP` headers from
  [Foundation spec §10](./2026-06-12-geojson-foundation.md#10-content-security-policy)
  are not enforced in tests.
- Staticfiles are collected to a temp dir if any frontend test
  needs them (none do in v1).

`pytest.ini` / `pyproject.toml [tool.pytest.ini_options]` sets
`DJANGO_SETTINGS_MODULE = config.settings.test` and
`python_files = ["test_*.py"]` (the Django default).
