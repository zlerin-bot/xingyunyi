.PHONY: install test test-fast test-mcp test-typescript test-orbit test-postgres test-postgres-compose lint migrate run demo compose-up compose-down compose-production-config

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
NODE ?= node

install:
	uv sync --extra dev --extra mcp --extra connector

test: test-fast

test-fast:
	$(PYTEST) -m "not postgres"
	$(PYTEST) integrations/mcp/tests

test-mcp:
	$(PYTEST) integrations/mcp/tests

test-typescript:
	$(NODE) --test sdk/typescript/test/*.test.mjs

test-orbit:
	$(NODE) --test tests/javascript/*.test.mjs

test-postgres:
	$(PYTEST) tests/postgres

test-postgres-compose:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from pytest-postgres

lint:
	$(RUFF) check .
	$(RUFF) format --check .

migrate:
	PYTHONPATH=src .venv/bin/alembic upgrade head

run:
	PYTHONPATH=src .venv/bin/uvicorn agentpost.main:app --reload

demo:
	$(PYTHON) scripts/demo.py

compose-up:
	docker compose up --build

compose-down:
	docker compose down

compose-production-config:
	docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
