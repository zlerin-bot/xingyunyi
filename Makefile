.PHONY: install test test-fast test-postgres lint migrate run compose-up compose-down

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

install:
	uv sync --extra dev

test: test-fast

test-fast:
	$(PYTEST) -m "not postgres"

test-postgres:
	$(PYTEST) -m postgres

lint:
	$(RUFF) check .

migrate:
	PYTHONPATH=src .venv/bin/alembic upgrade head

run:
	PYTHONPATH=src .venv/bin/uvicorn agentpost.main:app --reload

compose-up:
	docker compose up --build

compose-down:
	docker compose down
