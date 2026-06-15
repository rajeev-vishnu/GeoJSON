# GeoJSON API

Django + GeoDjango backend serving a GeoJSON feature API, with a built-in
map front-end for browsing features.

## Quickstart

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env          # one-time: create your local .env from the template
docker compose up --wait      # start db + web (with migrations); blocks until healthy
```

Open <http://localhost:8000>.

Optionally load sample GeoJSON features:

```bash
docker compose exec web python manage.py seed_features
```

Stop the stack:

```bash
docker compose down
```

## Day-to-day

```bash
docker compose up --wait      # bring the stack up (idempotent, safe to re-run)
docker compose exec web python manage.py seed_features          # (re)load sample data
docker compose exec web python manage.py shell                 # open a Django shell
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest   # unit tests
docker compose exec web ruff check .                           # run ruff
```
