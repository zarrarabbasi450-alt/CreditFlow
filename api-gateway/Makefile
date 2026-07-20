install:
	python -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
format:
	.venv/bin/ruff format .
lint:
	.venv/bin/ruff check .
typecheck:
	.venv/bin/mypy src tests
test:
	.venv/bin/pytest
run:
	.venv/bin/uvicorn api_gateway.main:app --reload --port 8080
