.PHONY: help install batch loop monitor docker-build docker-run clean run migrate-init migrate test coverage coverage-loop frontend-install frontend-build frontend-lint frontend-test frontend-coverage frontend-run test-backend test-frontend test-infra test-integration test-regression lint-backend lint-frontend lint-infra cleanup git-reset

# Default target
help:
	@echo "Available commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make batch        - Run the Cursor batch process (run_cursor_batch.py)"
	@echo "  make loop         - Run the Ralph loop process (run_cursor_ralph_loop.py)"
	@echo "  make monitor      - Run the progress monitor (monitor.py)"
	@echo "  make run          - Run the FastAPI app locally (uvicorn)"
	@echo "  make migrate-init - Initialize Aerich migrations"
	@echo "  make migrate      - Run Aerich migrations"
	@echo "  make test         - Run all tests with pytest"
	@echo "  make test-fix     - Run the test fix loop (run_test_fix_loop.py)"
	@echo "  make coverage     - Run tests and show coverage report"
	@echo "  make coverage-loop - Run the automatic coverage improvement loop"
	@echo "  make lint-backend - Run backend linting and type checking"
	@echo "  make frontend-install - Install Frontend dependencies"
	@echo "  make frontend-build   - Build Frontend for production"
	@echo "  make frontend-lint    - Run Frontend linting"
	@echo "  make frontend-test    - Run Frontend tests with Vitest"
	@echo "  make frontend-coverage - Run Frontend tests with coverage"
	@echo "  make docker-build - Build the Docker image"
	@echo "  make docker-run   - Run the Docker container"
	@echo "  make clean        - Remove generated files"
	@echo "  make cleanup      - Kill stale pytest and agent processes"
	@echo "  make git-reset    - Reset local main branch to match origin/main"

test-backend:
	PYTHONPATH=. pytest -v tests/

test-frontend:
	cd frontend && npx vitest --run

test-infra:
	@echo "Running infra tests..."
	pytest tests/test_cli.py

test-integration:
	@echo "Running integration tests..."
	pytest tests/test_api.py

test-regression:
	@echo "Running regression tests..."
	pytest tests/test_utils.py

lint-backend:
	@echo "Running backend lint (ruff)..."
	ruff check .
	@echo "Running backend type check (mypy)..."
	mypy .

lint-frontend:
	cd frontend && npx eslint . --ext ts,tsx

lint-infra:
	@echo "Running infra lint..."
	ruff check vibe_tools/

install:
	./install.sh

batch:
	python3 run_cursor_batch.py

loop:
	vibe ralph

monitor:
	vibe monitor --interval 60

run:
	uvicorn src.main:app --reload --port 8000

migrate-init:
	aerich init -t src.core.db.TORTOISE_ORM
	aerich init-db

migrate:
	aerich migrate
	aerich upgrade

test:
	PYTHONPATH=. pytest -v

coverage:
	pytest --cov=src --cov=vibe_tools --cov-report=term-missing tests/

coverage-loop:
	vibe coverage

test-fix:
	vibe test-fix

frontend-install:
	cd frontend && npm install

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npx eslint . --ext ts,tsx

frontend-test:
	cd frontend && npx vitest --run

frontend-coverage:
	cd frontend && npx vitest --coverage

frontend-run:
	cd frontend && npm run dev

docker-build:
	docker build -t staravenir -f deployment/Dockerfile .

docker-run:
	docker run -p 8000:8000 staravenir

clean:
	rm -rf generated/*

cleanup:
	vibe cleanup

git-reset:
	git fetch origin
	git reset --hard origin/main

