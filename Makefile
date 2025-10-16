COMPOSE = docker compose -f infra/compose.yaml

.PHONY: up down logs test

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	$(COMPOSE) run --rm api poetry run pytest
