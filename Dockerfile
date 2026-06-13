# syntax=docker/dockerfile:1.7

# --- build stage --------------------------------------------------------
FROM python:3.12-slim AS build

WORKDIR /app

# System deps for psycopg binary wheels and any Postgres client libs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY config ./config
COPY accounts ./accounts
COPY features ./features
COPY frontend ./frontend
COPY manage.py ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# --- runtime stage ------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only system deps (libpq for psycopg, GDAL/GEOS/PROJ for GeoDjango).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libgdal36 \
        libproj25 \
        libgeos-c1t64 \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed packages and the project from the build stage.
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /app /app

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# gunicorn is the production CMD; the dev compose service overrides
# this with `python manage.py runserver` in docker-compose.yml.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
