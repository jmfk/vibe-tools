.PHONY: help install batch loop monitor docker-build docker-run clean run migrate-init migrate test coverage coverage-loop frontend-install frontend-build frontend-lint frontend-test frontend-coverage frontend-run

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
	@echo "  make frontend-install - Install Frontend dependencies"
	@echo "  make frontend-build   - Build Frontend for production"
	@echo "  make frontend-lint    - Run Frontend linting"
	@echo "  make frontend-test    - Run Frontend tests with Vitest"
	@echo "  make frontend-coverage - Run Frontend tests with coverage"
	@echo "  make frontend-run     - Start Frontend development server"
	@echo "  make docker-build - Build the Docker image"
	@echo "  make docker-run   - Run the Docker container"
	@echo "  make clean        - Remove generated files"

install:
	pip install -r requirements.txt

batch:
	python3 run_cursor_batch.py

loop:
	vibe ralph

monitor:
	python3 monitor.py --interval 60

run:
	uvicorn src.main:app --reload --port 8000

migrate-init:
	aerich init -t src.core.db.TORTOISE_ORM
	aerich init-db

migrate:
	aerich migrate
	aerich upgrade

test:
	pytest -v

coverage:
	pytest --cov=src --cov-report=term-missing tests/

coverage-loop:
	python3 run_coverage_improvement_loop.py

test-fix:
	python3 run_test_fix_loop.py

frontend-install:
	cd frontend && npm install

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm run test -- --run

frontend-coverage:
	cd frontend && npm run test:coverage

frontend-run:
	cd frontend && npm run dev

docker-build:
	docker build -t staravenir -f deployment/Dockerfile .

docker-run:
	docker run -p 8000:8000 staravenir

clean:
	rm -rf generated/*

