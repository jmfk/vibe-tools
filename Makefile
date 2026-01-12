.PHONY: test-backend test-frontend test

test: test-backend test-frontend

test-backend:
	pytest tests/

test-frontend:
	cd frontend && npm test
