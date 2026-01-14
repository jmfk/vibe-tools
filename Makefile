.PHONY: all build test lint clean logs install-backend test-backend lint-backend install-frontend dev-desktop build-desktop test-frontend lint-frontend

all: build

install-backend:
	pip install -e .

test-backend:
	pytest tests/

lint-backend:
	ruff check .
	mypy .

install-frontend:
	cd frontend && npm install

dev-desktop:
	cd frontend && cargo tauri dev

build-desktop:
	cd frontend && cargo tauri build

test-frontend:
	cd frontend && npm test

lint-frontend:
	cd frontend && npm run lint

test: test-backend test-frontend

build: install-backend build-desktop

lint: lint-backend lint-frontend

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf frontend/dist/
	rm -rf frontend/src-tauri/target/
	rm -rf implementation/logs/*

logs:
	ls -R implementation/logs/