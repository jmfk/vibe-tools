.PHONY: test-backend test-frontend test

test-backend:
	pytest tests/

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend
