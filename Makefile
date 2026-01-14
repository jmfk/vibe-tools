.PHONY: test-backend test-frontend test test-integration test-regression

test-backend:
	pytest tests/

test-frontend:
	cd frontend && npm test

test-integration:
	pytest tests/

test-regression:
	pytest tests/

test: test-backend test-frontend
