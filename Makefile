.PHONY: install lint format typecheck test check docker-build docker-test

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy app

test:
	uv run python -m pytest  # pytest.exe is blocked by Application Control on this machine

check: lint typecheck test

IMAGE ?= mlops-model-serving:local

docker-build:
	docker build -t $(IMAGE) --build-arg SOURCE_REVISION=$$(git rev-parse --short HEAD) .

docker-test: docker-build
	MSS_IMAGE=$(IMAGE) uv run python -m pytest tests/integration/test_container.py -v
