# =============================================================================
# netbox-dhcp-kea-plugin — Makefile
# =============================================================================
#
# Development tasks for the NetBox DHCP-KEA plugin. Tests import NetBox from
# NETBOX_PATH and run in the Python environment that has NetBox's requirements
# and this plugin installed (pip install -e ".[test]").
#
# Usage:
#   make test             # Run the test suite
#   make docs             # Preview the documentation site
#   make help             # Show every target and variable
#
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
PROJECT_DIR  := $(shell pwd)
PLUGIN_PKG   := netbox_dhcp_kea_plugin
TESTS_DIR    := tests
DIST_DIR     := dist
SITE_DIR     := site
NETBOX_PATH  ?=

# test-ci: the NetBox configuration CI uses, with a database of its own so it
# never touches the test database of your own configuration.py
CI_CONFIG    := tests.netbox_configuration
CI_DB_NAME   ?= netbox_ci

# Docs
ZENSICAL     ?= zensical
DOCS_ADDR    ?= localhost:8000

# ---------------------------------------------------------------------------
# Pytest flags
# ---------------------------------------------------------------------------
PYTEST_FLAGS := --no-header -q
ifdef VERBOSE
	PYTEST_FLAGS += -v
endif
ifdef STOP
	PYTEST_FLAGS += -x
endif
# Pass extra flags: make test EXTRA_FLAGS="--tb=long -s"
EXTRA_FLAGS ?=
PYTEST_FLAGS += $(EXTRA_FLAGS)

PYTEST_TARGET := $(if $(T),$(T),$(TESTS_DIR)) $(PYTEST_FLAGS) $(if $(K),-k "$(K)")

# ---------------------------------------------------------------------------
# Help formatting
# ---------------------------------------------------------------------------
CYAN   := \033[36m
GREEN  := \033[32m
YELLOW := \033[33m
RESET  := \033[0m
BOLD   := \033[1m
DIM    := \033[2m

# One printf format per kind of help row, so the columns cannot drift apart.
# Padded columns must stay ASCII: printf pads by bytes, not characters.
H_SECT := "\n  $(BOLD)%s$(RESET)\n"
H_CMD  := "    $(CYAN)%-20s$(RESET)%s\n"
H_EG   := "      $(YELLOW)%-42s$(RESET)%s\n"
H_NOTE := "    $(DIM)%s$(RESET)\n"
H_VAR  := "    %-11s$(YELLOW)%-26s$(RESET)%s\n"

# =============================================================================
# Targets
# =============================================================================

.PHONY: help
help: ## Show this help
	@printf "\n  $(BOLD)netbox-dhcp-kea-plugin$(RESET) - tests, docs, checks and packaging\n"
	@printf $(H_SECT) "TEST"
	@printf $(H_CMD)  "make test"          "Run the tests, reusing the test database"
	@printf $(H_EG)   "make test T=tests/test_models.py"        "one file, or a node id"
	@printf $(H_EG)   "make test K=test_pool STOP=1 VERBOSE=1"  "filter, stop early, list names"
	@printf $(H_CMD)  "make test-fresh"    "Recreate the test database first"
	@printf $(H_CMD)  "make test-file"     "Run one file, given as F=tests/test_x.py"
	@printf $(H_CMD)  "make test-cov"      "Tests with a coverage report in htmlcov/"
	@printf $(H_CMD)  "make test-ci"       "Tests under the NetBox configuration CI uses"
	@printf $(H_NOTE) "test-ci loads tests/netbox_configuration.py instead of your configuration.py, so"
	@printf $(H_NOTE) "only netbox_dns and this plugin are installed: what a fresh deployment sees."
	@printf $(H_SECT) "DOCS"
	@printf $(H_CMD)  "make docs"          "Live preview of the documentation site"
	@printf $(H_CMD)  "make docs-build"    "Build the site into site/"
	@printf $(H_CMD)  "make docs-check"    "Strict build that fails on any warning, as CI does"
	@printf $(H_SECT) "CHECKS"
	@printf $(H_CMD)  "make lint"          "ruff check"
	@printf $(H_CMD)  "make format"        "ruff format, then ruff check --fix"
	@printf $(H_CMD)  "make format-check"  "ruff format --check"
	@printf $(H_CMD)  "make mypy"          "mypy type checking"
	@printf $(H_CMD)  "make pre-commit"    "pre-commit hooks on every file"
	@printf $(H_CMD)  "make check"         "lint, format-check and test"
	@printf $(H_SECT) "PACKAGE"
	@printf $(H_CMD)  "make dist"          "Build the wheel and sdist into dist/ and check them"
	@printf $(H_CMD)  "make lock"          "Update uv.lock from pyproject.toml"
	@printf $(H_SECT) "HOUSEKEEPING"
	@printf $(H_CMD)  "make clean"         "Remove build output, caches, coverage and site/"
	@printf $(H_SECT) "VARIABLES"
	@printf $(H_VAR)  "selection"   "T=<path or node id>"       "what the test targets run"
	@printf $(H_VAR)  ""            "F=<path>"                  "the file make test-file runs"
	@printf $(H_VAR)  ""            "K=<expr>"                  "pytest -k, on any test target"
	@printf $(H_VAR)  "output"      "VERBOSE=1"                 "list each test by name (-v)"
	@printf $(H_VAR)  ""            "STOP=1"                    "stop at the first failure (-x)"
	@printf $(H_VAR)  ""            "EXTRA_FLAGS=\"...\""       "passed to pytest verbatim"
	@printf $(H_VAR)  "netbox"      "NETBOX_PATH=<path>"        "NetBox's netbox/ directory"
	@printf $(H_VAR)  ""            ""                          "now: $(or $(NETBOX_PATH),unset)"
	@printf $(H_VAR)  "test-ci"     "CI_DB_NAME=$(CI_DB_NAME)"  "tests run in test_<name>"
	@printf $(H_VAR)  ""            "NETBOX_DB_USER=<user>"     "also _PASSWORD, _HOST and _PORT;"
	@printf $(H_VAR)  ""            "NETBOX_REDIS_HOST=<host>"  "also _PORT and _PASSWORD"
	@printf $(H_VAR)  "docs"        "DOCS_ADDR=$(DOCS_ADDR)"    "live preview address"
	@printf "\n"

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run the tests (reuses the test DB)
	NETBOX_PATH=$(NETBOX_PATH) PYTHONPATH=$(NETBOX_PATH):$(PYTHONPATH) \
	python -m pytest $(PYTEST_TARGET)
	@printf '$(GREEN)✔ Tests passed.$(RESET)\n'

.PHONY: test-fresh
test-fresh: ## Run the tests with a fresh database (--create-db)
	NETBOX_PATH=$(NETBOX_PATH) PYTHONPATH=$(NETBOX_PATH):$(PYTHONPATH) \
	python -m pytest $(PYTEST_TARGET) --create-db
	@printf '$(GREEN)✔ Tests passed (fresh DB).$(RESET)\n'

.PHONY: test-file
test-file: ## Run a single test file (F=path/to/test.py)
ifndef F
	$(error Set F=<test file>, e.g. make test-file F=tests/test_reservation_modes.py)
endif
	NETBOX_PATH=$(NETBOX_PATH) PYTHONPATH=$(NETBOX_PATH):$(PYTHONPATH) \
	python -m pytest $(F) $(PYTEST_FLAGS) $(if $(K),-k "$(K)")
	@printf '$(GREEN)✔ Tests passed.$(RESET)\n'

.PHONY: test-cov
test-cov: ## Run the tests with a coverage report
	NETBOX_PATH=$(NETBOX_PATH) PYTHONPATH=$(NETBOX_PATH):$(PYTHONPATH) \
	python -m pytest $(PYTEST_TARGET) --cov=$(PLUGIN_PKG) --cov-report=term-missing --cov-report=html
	@printf '$(GREEN)✔ Coverage report written to htmlcov/$(RESET)\n'

# The database credentials come from NETBOX_DB_* in the environment, read by
# tests/netbox_configuration.py; only the name is set here.
.PHONY: test-ci
test-ci: ## Run the tests under the NetBox configuration CI uses
	NETBOX_CONFIGURATION=$(CI_CONFIG) \
	NETBOX_DB_NAME=$(CI_DB_NAME) \
	NETBOX_PATH=$(NETBOX_PATH) \
	PYTHONPATH=$(NETBOX_PATH):$(PROJECT_DIR):$(PYTHONPATH) \
	python -m pytest $(PYTEST_TARGET)
	@printf '$(GREEN)✔ Tests passed under $(CI_CONFIG).$(RESET)\n'

# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------

.PHONY: docs
docs: ## Live preview of the documentation site
	@printf '$(BOLD)▶ Serving$(RESET) at $(CYAN)http://$(DOCS_ADDR)$(RESET) (Ctrl-C to stop)\n'
	$(ZENSICAL) serve --dev-addr $(DOCS_ADDR)

.PHONY: docs-build
docs-build: ## Build the documentation site into site/
	$(ZENSICAL) build
	@printf '$(GREEN)✔ Site built in $(SITE_DIR)/$(RESET)\n'

.PHONY: docs-check
docs-check: ## Strict docs build: fail on broken links and other warnings
	$(ZENSICAL) build --clean --strict
	@printf '$(GREEN)✔ Docs build without warnings.$(RESET)\n'

# ---------------------------------------------------------------------------
# Lint & format
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff linter
	ruff check $(PLUGIN_PKG) $(TESTS_DIR)
	@printf '$(GREEN)✔ Lint passed.$(RESET)\n'

.PHONY: format
format: ## Auto-format code with ruff
	ruff format $(PLUGIN_PKG) $(TESTS_DIR)
	ruff check --fix $(PLUGIN_PKG) $(TESTS_DIR)
	@printf '$(GREEN)✔ Formatted.$(RESET)\n'

.PHONY: format-check
format-check: ## Check formatting without changes
	ruff format --check $(PLUGIN_PKG) $(TESTS_DIR)
	@printf '$(GREEN)✔ Format check passed.$(RESET)\n'

# ---------------------------------------------------------------------------
# Type checking
# ---------------------------------------------------------------------------

.PHONY: mypy
mypy: ## Run mypy type checking
	mypy $(PLUGIN_PKG)
	@printf '$(GREEN)✔ Type check passed.$(RESET)\n'

# ---------------------------------------------------------------------------
# Combined checks
# ---------------------------------------------------------------------------

.PHONY: check
check: lint format-check test ## Run lint + format check + tests

.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------

.PHONY: dist
dist: ## Build the wheel and sdist, then check them as PyPI will
	rm -rf $(DIST_DIR)
	uv build --out-dir $(DIST_DIR)
	uvx twine check $(DIST_DIR)/*
	@printf '$(GREEN)✔ Built:$(RESET) %s\n' "$$(ls $(DIST_DIR) | tr '\n' ' ')"

.PHONY: lock
lock: ## Update uv.lock from pyproject.toml
	uv lock

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf *.egg-info $(DIST_DIR) build htmlcov .coverage $(SITE_DIR) .cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@printf '$(GREEN)✔ Cleaned.$(RESET)\n'
