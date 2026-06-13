.PHONY: up down migrate seed test lint shell

COMPOSE := docker compose

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

lint:
	$(COMPOSE) exec web ruff check .

shell:
	$(COMPOSE) exec web python manage.py shell
