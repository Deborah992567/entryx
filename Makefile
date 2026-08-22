.PHONY: help dev test lint format migrate seed clean docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

dev: ## Start backend dev server
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run all backend tests
	cd backend && source .venv/bin/activate && python -m pytest tests/ --tb=short

test-cov: ## Run tests with coverage report
	cd backend && source .venv/bin/activate && python -m pytest tests/ --cov=app --cov-report=html --tb=short

lint: ## Run ruff linter
	cd backend && source .venv/bin/activate && ruff check app/ tests/

format: ## Format code with ruff
	cd backend && source .venv/bin/activate && ruff format app/ tests/ && ruff check --fix app/ tests/

migrate: ## Run alembic migrations
	cd backend && source .venv/bin/activate && alembic upgrade head

seed: ## Seed the database with demo data
	cd backend && source .venv/bin/activate && python -m app.seed

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/htmlcov backend/.coverage

docker-up: ## Start services with docker compose
	docker compose up -d --build

docker-down: ## Stop docker compose services
	docker compose down

frontend: ## Run Flutter frontend
	cd frontend && flutter run

flutter-analyze: ## Analyze Flutter code
	cd frontend && flutter analyze

flutter-test: ## Run Flutter tests
	cd frontend && flutter test
