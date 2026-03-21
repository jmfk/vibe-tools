.DEFAULT_GOAL := help

.PHONY: help install install-app reinstall-app uninstall-app install-dev-global build-dist clean-dist check-pipx check-build test lint clean logs

help: ## Display this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-dev-global ## Install the editable global dev CLI via pipx

check-pipx: ## Verify pipx is installed
	@command -v pipx >/dev/null 2>&1 || (echo "pipx is required. Install it first: python3 -m pip install --user pipx && python3 -m pipx ensurepath" && exit 1)

check-build: ## Ensure the Python build package is available
	@python -c "import build" >/dev/null 2>&1 || python -m pip install build

install-app: check-pipx build-dist ## Install the packaged CLI globally via pipx from a built wheel
	@WHEEL=$$(ls -t dist/*.whl 2>/dev/null | head -n 1); \
	if [ -z "$$WHEEL" ]; then echo "No wheel found in dist/"; exit 1; fi; \
	pipx uninstall vibe-tools >/dev/null 2>&1 || true; \
	pipx install --python python3 "$$WHEEL"

reinstall-app: uninstall-app install-app ## Reinstall the packaged global CLI

uninstall-app: check-pipx ## Remove the globally installed CLI from pipx
	@pipx uninstall vibe-tools >/dev/null 2>&1 || true

install-dev-global: check-pipx ## Install the repo as a global editable CLI via pipx
	@pipx uninstall vibe-tools >/dev/null 2>&1 || true
	pipx install --python python3 --editable .

build-dist: check-build clean-dist ## Build wheel and sdist artifacts into dist/
	python -m build

clean-dist: ## Remove distribution build artifacts
	rm -rf build dist *.egg-info

test: ## Run the Python test suite
	pytest tests/

lint: ## Run Python lint checks
	python -m compileall vibe_tools tests

clean: ## Remove Python build and cache artifacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	python -c "import pathlib, shutil; [shutil.rmtree(path, ignore_errors=True) for path in pathlib.Path('.').rglob('__pycache__')]"

logs: ## List repo-local vibe logs
	ls -R .vibe-tools/logs 2>/dev/null || true