install:
	python -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
format:
	.venv/bin/ruff format src tests migrations
lint:
	.venv/bin/ruff check src tests migrations
typecheck:
	.venv/bin/mypy src tests
test:
	.venv/bin/pytest
migrate:
	.venv/bin/alembic upgrade head
run:
	.venv/bin/uvicorn auth_service.main:app --reload --port 8001
