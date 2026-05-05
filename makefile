.SUFFIXES:

help:  ## Show this help
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: test
test:  ## Run pytest
	uv run pytest

.PHONY: tox
tox:  ## Run full matrix via tox
	uv run tox

.PHONY: lint
lint:  ## Ruff check + format check + mypy (no writes)
	uv run ruff check ./src ./tests
	uv run ruff format --check ./src ./tests
	uv run mypy

.PHONY: format
format:  ## Ruff format + autofix in place
	uv run ruff format ./src ./tests
	uv run ruff check --fix ./src ./tests

.PHONY: cover
cover:  ## Coverage profile + HTML (htmlcov/)
	uv run pytest --cov=horse --cov-report=term --cov-report=html

.PHONY: cover-open
cover-open: cover  ## Run coverage and open report
	open htmlcov/index.html

.PHONY: build
build:  ## Build sdist + wheel
	uv build

.PHONY: verify
verify: lint test  ## Pre-commit gate: lint + test
	@echo "All checks passed."

.PHONY: clean
clean:  ## Remove caches + build artefacts
	@rm -rf .mypy_cache .pytest_cache .ruff_cache .tox
	@rm -rf htmlcov .coverage*
	@rm -rf build dist
	@find . -name '*.egg-info' -type d -exec rm -rf {} +
	@find . -name '__pycache__' -type d -exec rm -rf {} +
