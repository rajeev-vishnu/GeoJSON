.PHONY: up down migrate seed test test-e2e lint shell setup precommit-install

COMPOSE := docker compose

setup: precommit-install
	pip install pre-commit ruff
	npm install
	pre-commit install

precommit-install:
	@command -v pre-commit >/dev/null 2>&1 || { echo "pre-commit not installed. Run: pip install pre-commit"; exit 1; }

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

migrate:
	$(COMPOSE) run --rm migrate

seed:
	$(COMPOSE) exec web python manage.py seed_features

test:
	$(COMPOSE) run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest

test-e2e:
	$(COMPOSE) up -d
	node e2e/map-color-style.mjs

lint:
	$(COMPOSE) exec web ruff check .

shell:
	$(COMPOSE) exec web python manage.py shell
