install:
	python3 -m pip install -q -e . 2>/dev/null || true

test:
	python3 -m unittest discover -s packages -p "test_*.py" -v

up:
	docker compose up -d

down:
	docker compose down

migrate:
	psql "$$DATABASE_URL" -f db/migrations/0001_init.sql

lint:
	python3 -m ruff check . || true

.PHONY: install test up down migrate lint
