.PHONY: install test test-fast test-postgres test-postgres-compose lint migrate run demo compose-up compose-down

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

install:
	uv sync --extra dev

test: test-fast

test-fast:
	$(PYTEST) -m "not postgres"

test-postgres:
	$(PYTEST) tests/postgres

test-postgres-compose:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from pytest-postgres

lint:
	$(RUFF) check .

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
