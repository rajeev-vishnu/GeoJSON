# One-shot `make app` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `make app` target that brings a fresh clone to a running, migrated web app on `http://localhost:8000` in one command, with no manual `.env` editing.

**Architecture:** Add a single `app` target to the existing `Makefile` that composes the existing `docker compose` services. The target (1) materializes `.env` from `.env.example` if missing, (2) starts `db` and waits for its healthcheck, (3) runs the existing one-shot `migrate` service, (4) starts `web`. Seeding stays a separate explicit step. A small bash smoke test guards the target's shape via `make -n` (dry-run) so future regressions are caught without needing Docker.

**Tech Stack:** GNU Make, Docker Compose, Bash (for the smoke test). No new Python, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-15-make-app-one-shot-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `Makefile` | Modify | Add `app` target that orchestrates bring-up |
| `scripts/test_makefile.sh` | Create | Bash smoke test asserting `make -n app` shape |
| `README.md` | Create | Quickstart + dev-credential notes for the colleague |

No other files change. `.env` is generated at runtime, never committed.

---

### Task 1: Add a failing smoke test for the `app` target

**Files:**
- Create: `scripts/test_makefile.sh`

- [ ] **Step 1: Create the test script**

Write `scripts/test_makefile.sh`:

```bash
#!/usr/bin/env bash
# Smoke test for Makefile targets. Runs `make -n` (dry-run) on each
# target and greps the output for expected command fragments. Catches
# accidental removal of steps without needing Docker.

set -euo pipefail

cd "$(dirname "$0")/.."

assert_dry_run_contains() {
  local target="$1"
  local needle="$2"
  local output
  output=$(make -n "$target")
  if ! printf '%s\n' "$output" | grep -qF "$needle"; then
    echo "FAIL: make -n $target does not contain: $needle"
    echo "----- actual output -----"
    printf '%s\n' "$output"
    echo "-------------------------"
    exit 1
  fi
}

assert_dry_run_contains app "cp .env.example .env"
assert_dry_run_contains app "docker compose up -d db"
assert_dry_run_contains app "pg_isready"
assert_dry_run_contains app "docker compose run --rm migrate"
assert_dry_run_contains app "docker compose up -d web"

echo "PASS: make app target looks correct"
```

- [ ] **Step 2: Make the script executable**

Run from repo root:

```bash
git update-index --chmod=+x scripts/test_makefile.sh
```

(This stages the executable bit; the actual `chmod` happens on commit.)

- [ ] **Step 3: Run the test and verify it fails**

Run: `bash scripts/test_makefile.sh`
Expected: exit code 1, output contains `FAIL: make -n app does not contain: cp .env.example .env` (the `app` target does not exist yet, so dry-run fails — but more importantly the test's grep would miss the fragment even if `make` succeeded with an empty target).

- [ ] **Step 4: Commit the failing test**

```bash
git add scripts/test_makefile.sh
git commit -m "test(make): add smoke test for make app target shape"
```

---

### Task 2: Implement the `app` target in the Makefile

**Files:**
- Modify: `Makefile:1-36`

- [ ] **Step 1: Update the `.PHONY` line**

In `Makefile`, change line 1 from:

```makefile
.PHONY: up down migrate seed test test-e2e lint shell setup precommit-install
```

to:

```makefile
.PHONY: app up down migrate seed test test-e2e lint shell setup precommit-install
```

- [ ] **Step 2: Add the `app` target**

Append to the end of `Makefile` (after the `shell` target, preserving the existing blank-line style of the file):

```makefile

app:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; fi
	$(COMPOSE) up -d db
	@echo "Waiting for db to be healthy..."
	@for i in $$(seq 1 30); do \
		$(COMPOSE) exec -T db pg_isready -U geojson >/dev/null 2>&1 && echo "db is healthy" && exit 0; \
		sleep 1; \
	done; \
	echo "db failed to become healthy in 30s" >&2; \
	exit 1
	$(COMPOSE) run --rm migrate
	$(COMPOSE) up -d web
	@echo ""
	@echo "App is up at http://localhost:8000"
	@echo "Run 'make seed' to load sample data."
```

Notes:
- `$$` escapes the single `$` so Make doesn't try to expand `$(seq ...)` as a Make variable.
- `exec -T` disables pseudo-TTY allocation so the command works in non-TTY contexts (CI, scripts).
- The `for` loop is intentionally a single recipe line so `make -n` prints it as one logical step.
- The 30-second timeout matches the spec.

- [ ] **Step 3: Run the smoke test and verify it passes**

Run: `bash scripts/test_makefile.sh`
Expected: `PASS: make app target looks correct`, exit code 0.

- [ ] **Step 4: Inspect the dry-run output to sanity-check**

Run: `make -n app`
Expected: the four `docker compose` / `cp` lines, in order, plus the `pg_isready` loop and the trailing `echo` lines. No `make: *** [app] Error` lines.

- [ ] **Step 5: Commit**

```bash
git add Makefile
git commit -m "feat(make): add app target for one-shot dev bring-up"
```

---

### Task 3: End-to-end manual verification from a clean state

This task has no automated test — it is the integration test for a Makefile change. It must be run by the implementing engineer on their own machine.

**Files:** none modified.

- [ ] **Step 1: Stop and clean existing containers + .env**

Run:

```bash
make down
rm -f .env
```

Expected: `make down` reports stopping the stack. `.env` is gone.

- [ ] **Step 2: Run `make app` from clean and time it**

Run: `time make app`
Expected:
- First line of output: `Created .env from .env.example`
- Docker builds/pulls images, starts `db`, the healthcheck loop passes (`db is healthy`).
- `migrate` runs (output of Django migrations).
- `web` starts.
- Final two `echo` lines print the URL and the seed hint.
- Exit code 0.

- [ ] **Step 3: Verify the app responds**

Run: `curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/`
Expected: `200` (or `302` if the root redirects — both are acceptable signals the app is up). If the app has a known health endpoint, prefer that.

- [ ] **Step 4: Verify idempotency: run `make app` a second time**

Run: `make app`
Expected: no `Created .env from .env.example` line (because `.env` now exists). No errors. App is still up.

- [ ] **Step 5: Tear down for further work**

Run: `make down`
Expected: stack stops cleanly. `pgdata` volume is preserved (intentional — keeps the DB across restarts).

- [ ] **Step 6: Do not commit** — this task produces no code changes.

If any step fails, debug and amend Task 2's commit before proceeding.

---

### Task 4: Document `make app` in the README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

Write `README.md`:

````markdown
# GeoJSON API

Django + GeoDjango backend serving a GeoJSON feature API, with a built-in
map front-end for browsing features.

## Quickstart

Prerequisites: Docker Desktop and `make` (Git Bash / WSL on Windows).

```bash
make app      # build, start db + web, run migrations
make seed     # optional: load sample GeoJSON features
```

Open <http://localhost:8000>.

## Day-to-day

```bash
make up       # start db + web (assumes already built and migrated)
make down     # stop db + web
make seed     # (re)load sample data
make test     # run unit tests
make test-e2e # run end-to-end browser tests
make shell    # open a Django shell inside the web container
```

## Credentials (dev only)

Postgres credentials (`geojson:geojson`) are hardcoded in
`docker-compose.yml` — the database only runs on your laptop, so
security is not a concern there. `DJANGO_SECRET_KEY` and other
settings live in `.env`, which is generated from `.env.example` on
the first `make app` and is gitignored. For production, secrets are
injected by the deploy platform.
````

- [ ] **Step 2: Sanity-check rendering**

Run: `head -30 README.md`
Expected: front-matter, `## Quickstart`, the two `make` commands, the `## Day-to-day` block, the `## Credentials (dev only)` block. No emoji (per repo conventions).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with quickstart and dev credential notes"
```

---

### Task 5: Pre-commit gate

**Files:** potentially any tracked file, if linters fix formatting.

- [ ] **Step 1: Run pre-commit on the full repo**

Run: `pre-commit run --all-files`
Expected: all hooks pass. If any fail, fix what they report and re-run.

- [ ] **Step 2: Commit any auto-fixes (if any)**

```bash
git status
# If pre-commit made changes:
git add -A
git commit -m "style: pre-commit auto-fixes"
```

If pre-commit reported no changes, skip this commit.

- [ ] **Step 3: Final summary**

Run: `git log --oneline -10`
Expected: a clean linear history with the four (or five) commits from Tasks 1, 2, 4, and 5 in order, with no untracked modifications.

---

## Out of scope

- Removing or changing the existing `up` / `down` / `migrate` / `seed` targets.
- Production secret management.
- Auto-opening a browser.
- Bundling `make seed` into `make app`.
- Cross-platform Makefile shims for environments without `seq` / `sleep` (the project already requires a Unix-like shell via Docker tooling).
