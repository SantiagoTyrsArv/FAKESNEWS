.PHONY: up down seed test test-api lint lint-api lint-web logs

up:
	docker compose up --build

down:
	docker compose down

seed:
	docker compose exec api uv run python -m app.cli.seed_demo

test: test-api

test-api:
	cd apps/api && uv run pytest

lint: lint-api lint-web

lint-api:
	cd apps/api && uv run ruff check .

lint-web:
	cd apps/web && pnpm run lint

logs:
	docker compose logs -f
