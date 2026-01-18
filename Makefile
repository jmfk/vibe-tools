.DEFAULT_GOAL := help

.PHONY: help build build-cli build-desktop test test-backend test-desktop test-frontend test-core dev dev-start run install install-deps dev-desktop lint lint-backend lint-frontend clean logs

help: ## Display this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Build Targets
build: build-cli build-desktop ## Build the entire project (CLI and Desktop)

build-cli: install-backend ## Install the Python CLI in editable mode
	@STANDALONE=$$(python3 -c "import json, pathlib; p = pathlib.Path('implementation/config.json'); print('true' if json.loads(p.read_text()).get('setup', {}).get('standalone', True) else 'false')" 2>/dev/null || echo "true"); \
	if [ "$$STANDALONE" = "false" ]; then \
		echo "Installing in editable mode..."; \
		pip install -e .; \
	else \
		echo "Installing in standalone mode..."; \
		pip install .; \
	fi

build-desktop: ## Build the production Tauri desktop application
	cd frontend && npm run tauri build

# Test Targets
test: test-backend test-desktop ## Run all tests (CLI and Desktop)

test-backend: ## Run pytest for the Python CLI
	pytest tests/

test-desktop: test-frontend test-core ## Run all desktop tests (Frontend and Rust core)

test-frontend: ## Run frontend-specific Vitest tests
	cd frontend && npm test

test-core: ## Run Rust-specific Cargo tests
	cd frontend/src-tauri && cargo test

# Development Targets
dev: install-deps ## Install all dependencies for development

dev-start: dev-desktop ## Start the persistent development server

run: dev-desktop ## Alias for dev-start

install-deps: install-backend install-frontend ## Install backend and frontend dependencies

install-backend: ## Install Python backend dependencies
	pip install -e .

install-frontend: ## Install Node.js frontend dependencies
	cd frontend && npm install

dev-desktop: ## Start the Tauri development environment
	cd frontend && npm run tauri dev

# Linting & Quality Targets
lint: lint-backend lint-frontend ## Run all linters (CLI and Frontend)

lint-backend: ## Run ruff and mypy on the Python codebase
	ruff check .
	mypy .

lint-frontend: ## Run linting for the frontend
	cd frontend && npm run lint

# Utility Targets
clean: ## Remove build artifacts and temporary files
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf frontend/dist/
	rm -rf frontend/src-tauri/target/
	rm -rf implementation/logs/*

logs: ## List implementation logs
	ls -R implementation/logs/