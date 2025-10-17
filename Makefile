COMPOSE = docker compose -f infra/compose.yaml
TEST_COMPOSE = docker compose -f infra/compose.yaml --profile test
TEST_DB_URL = postgresql+psycopg2://postgres:postgres@db_test:5432/postgres
TEST_REDIS_URL = redis://redis_test:6379/0

.PHONY: up down logs test

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	$(TEST_COMPOSE) up -d db_test redis_test
	$(TEST_COMPOSE) run --rm --no-deps \
		-e APP_ENV=test \
		-e APP_DATABASE__URL=$(TEST_DB_URL) \
		-e APP_REDIS__URL=$(TEST_REDIS_URL) \
		-e OPENAI_API_KEY=test \
		-e SECRET_KEY=test-secret \
		-e ENCRYPTION_KEY=test-encryption \
		-e TZ=UTC \
		-e PYTHONPATH=. \
		api poetry run alembic upgrade head
	$(TEST_COMPOSE) run --rm --no-deps \
		-e APP_ENV=test \
		-e APP_DATABASE__URL=$(TEST_DB_URL) \
		-e APP_REDIS__URL=$(TEST_REDIS_URL) \
		-e OPENAI_API_KEY=test \
		-e SECRET_KEY=test-secret \
		-e ENCRYPTION_KEY=test-encryption \
		-e TZ=UTC \
		-e PYTHONPATH=. \
		api poetry run pytest
	$(TEST_COMPOSE) down --remove-orphans --volumes
