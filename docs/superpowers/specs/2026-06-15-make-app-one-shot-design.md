# One-shot `make app` + dev credential management

## Goal

A colleague cloning the repo can go from zero to a running, migrated web app on
`http://localhost:8000` with a single command — `make app` — with no manual
editing of `.env` files and no prompts. Database seeding is a separate
intentional step (`make seed`) so data loading is opt-in.

## Design

### `make app` target

Idempotent. Safe to re-run after `make down`, after pulling new changes, or
on a fresh clone. Sequence:

1. **Ensure `.env` exists.** If missing, copy `.env.example` to `.env`
   verbatim. The placeholder `DJANGO_SECRET_KEY=change-me-...` becomes the
   active secret. If `.env` already exists, leave it untouched.
2. **Bring up `db` and wait for healthy.** `docker compose up -d db`, then
   poll `docker compose exec db pg_isready -U geojson` in a loop with a
   30-second timeout. This is cheaper than starting the full stack and
   waiting.
3. **Run migrations.** `docker compose run --rm migrate`. Reuses the
   existing one-shot `migrate` service in `docker-compose.yml`. Idempotent
   — safe to re-run.
4. **Bring up `web`.** `docker compose up -d web`. Image rebuild happens
   automatically only when the Dockerfile context changes.

### What `make app` does NOT do

- Does **not** run `seed_features`. Seeding is destructive on Feature rows
  by design and should remain an explicit, separate `make seed` step.
- Does **not** open a browser. The colleague navigates to
  `http://localhost:8000` themselves.
- Does **not** install Docker Desktop or `make`. These are OS-level
  prerequisites documented in the README (out of scope for this spec).

### Existing targets, unchanged

`up`, `down`, `migrate`, `seed`, `test`, `test-e2e`, `lint`, `shell`,
`setup`, `precommit-install` all stay as-is. `make app` is an additional
high-level target on top of them.

## Dev credential management

| Secret                  | Location                                  | In git? | Notes                                                         |
|-------------------------|-------------------------------------------|---------|---------------------------------------------------------------|
| DB user / password      | `docker-compose.yml` (`geojson:geojson`)  | Yes     | Local-only throwaway DB; security is not a concern.           |
| `DATABASE_URL`          | `.env`                                    | No      | Gitignored. References compose service name `db` — portable. |
| `DJANGO_SECRET_KEY`     | `.env`                                    | No      | Placeholder from `.env.example` is fine for dev. Stable across restarts, not secret. |
| `DJANGO_DEBUG`          | `.env`                                    | No      | `True` in `.env.example`.                                     |
| `DJANGO_ALLOWED_HOSTS`  | `.env`                                    | No      | `*` in `.env.example`.                                        |
| `CORS_ALLOWED_ORIGINS`  | `.env`                                    | No      | `http://localhost:8000` in `.env.example`.                    |
| `JWT_ACCESS_MINUTES`    | `.env`                                    | No      | Default 15.                                                   |
| `JWT_REFRESH_DAYS`      | `.env`                                    | No      | Default 7.                                                    |

### Why DB creds are hardcoded in compose

The DB only runs on a colleague's local machine. It is not reachable from
the network. Keeping `geojson:geojson` hardcoded means `make app` works
with zero prompts and zero `.env` dependencies for the database layer.
Production deployment will inject real credentials via the platform's
secret store (out of scope for this spec).

### Why use the placeholder secret in dev

The Django secret in dev only signs cookies, CSRF tokens, and password
reset tokens for a web app reachable only from the colleague's own
laptop. It has no security value here. What matters is **stability
across restarts** so sessions survive — the placeholder from
`.env.example` provides that for free, with no generation step.

For production, the real secret is injected via the deploy platform
(out of scope for this spec).

### `.env` lifecycle

- `.env` is in `.gitignore`. The local file is generated, never committed.
- `.env.example` is committed and is the source of truth for keys and
  default values. `make app` copies it as the starting point for a fresh
  `.env`.

## Files touched

- `Makefile` — add `app` target. No other targets change.
- `docker-compose.yml` — no structural change required. (The existing
  `depends_on: condition: service_healthy` on `web` becomes redundant
  when `make app` is the entry point, but is still useful for callers
  who use `make up` directly. Leave as-is.)
- `.env` — generated on first `make app` run. Not committed.
- `README.md` — document `make app` and dev prerequisites. (Out of scope
  for the spec itself; flag for the implementation plan.)

## Out of scope

- Production deployment / real secret management.
- A non-Docker dev workflow.
- Removing or replacing existing granular targets (`up`, `migrate`, etc.).
- Auto-opening the browser.
- Running `seed_features` from `make app`.
