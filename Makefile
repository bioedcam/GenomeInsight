.PHONY: setup setup-backend setup-frontend test test-backend test-frontend lint format run run-api run-huey clean

# Default Python and Node
PYTHON ?= python3
PIP ?= pip
NPM ?= npm

# ──────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────

setup: setup-backend setup-frontend  ## Full project setup
	@echo "✓ GenomeInsight setup complete"

setup-backend:  ## Install Python dependencies
	$(PIP) install -e ".[dev]"

setup-frontend:  ## Install frontend dependencies
	@if [ -f frontend/package.json ]; then \
		cd frontend && $(NPM) install; \
	else \
		echo "frontend/package.json not found — skipping frontend setup"; \
	fi

# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────

run: run-api  ## Start the API server (default)

run-api:  ## Start FastAPI dev server
	uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

run-huey:  ## Start Huey consumer
	huey_consumer backend.tasks.huey_tasks.huey -w 1

# ──────────────────────────────────────────────
# Test
# ──────────────────────────────────────────────

test: test-backend test-frontend  ## Run all tests

test-backend:  ## Run backend tests
	$(PYTHON) -m pytest tests/ -v

test-frontend:  ## Run frontend tests
	@if [ -f frontend/package.json ]; then \
		cd frontend && $(NPM) test; \
	else \
		echo "frontend not set up — skipping"; \
	fi

# ──────────────────────────────────────────────
# Code quality
# ──────────────────────────────────────────────

lint:  ## Lint Python code with Ruff
	$(PYTHON) -m ruff check backend/ tests/

format:  ## Format Python code with Ruff
	$(PYTHON) -m ruff format backend/ tests/
	$(PYTHON) -m ruff check --fix backend/ tests/

# ──────────────────────────────────────────────
# Clean
# ──────────────────────────────────────────────

clean:  ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
