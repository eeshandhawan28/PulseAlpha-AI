.PHONY: install lint typecheck test test-unit docker-up docker-down health

install:
	uv sync --all-extras

lint:
	uv run ruff check .

typecheck:
	uv run mypy libs/ services/ --ignore-missing-imports

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

docker-up:
	docker compose -f infra/docker/docker-compose.yml up -d

docker-down:
	docker compose -f infra/docker/docker-compose.yml down

health:
	curl -s http://localhost:8000/health | python3 -m json.tool
