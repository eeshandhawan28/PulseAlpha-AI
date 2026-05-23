.PHONY: install lint typecheck test test-unit docker-up docker-down health

install:
	uv sync --all-extras

lint:
	uv run ruff check . && uv run ruff format --check .

typecheck:
	uv run mypy libs/ services/

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

docker-up:
	@test -f infra/docker/docker-compose.yml || (echo "ERROR: infra/docker/docker-compose.yml not yet created (see Task 4)" && exit 1)
	docker compose -f infra/docker/docker-compose.yml up -d

docker-down:
	@test -f infra/docker/docker-compose.yml || (echo "ERROR: infra/docker/docker-compose.yml not yet created (see Task 4)" && exit 1)
	docker compose -f infra/docker/docker-compose.yml down

health:
	curl -s http://localhost:8000/health | python3 -m json.tool
