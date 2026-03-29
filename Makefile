# =============================================================================
# netbox-dhcp-kea-plugin — Makefile
# =============================================================================
#
# Common development tasks for the NetBox DHCP-KEA plugin.
# Tests require NetBox installed and the plugin in dev mode (pip install -e .).
#
# Usage:
#   make test             # Run full test suite
#   make lint             # Lint & format check
#   make help             # Show this help
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
NETBOX_PATH  ?=

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

# =============================================================================
# Targets
# =============================================================================

.PHONY: help
help: ## Show this help
	@printf '\n\033[1mUsage:\033[0m make \033[36m<target>\033[0m [VAR=value ...]\n\n'
	@printf '\033[1m── Test ──\033[0m\n'
	@grep -E '^[a-zA-Z_-]+:.*?##\[test\] .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?##\\[test\\] "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1m── Lint & Format ──\033[0m\n'
	@grep -E '^[a-zA-Z_-]+:.*?##\[lint\] .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?##\\[lint\\] "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1m── Type Checking ──\033[0m\n'
	@grep -E '^[a-zA-Z_-]+:.*?##\[types\] .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?##\\[types\\] "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1m── Cleanup ──\033[0m\n'
	@grep -E '^[a-zA-Z_-]+:.*?##\[cleanup\] .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?##\\[cleanup\\] "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1mVariables:\033[0m\n'
	@printf '  \033[36m%-24s\033[0m %s\n' "NETBOX_PATH"  "Path to NetBox source (currently: $(NETBOX_PATH))"
	@printf '  \033[36m%-24s\033[0m %s\n' "VERBOSE"      "Set to 1 for verbose test output (-v)"
	@printf '  \033[36m%-24s\033[0m %s\n' "STOP"         "Set to 1 to stop on first failure (-x)"
	@printf '  \033[36m%-24s\033[0m %s\n' "EXTRA_FLAGS"  "Extra pytest flags (e.g. \"--tb=long -s\")"
	@printf '  \033[36m%-24s\033[0m %s\n' "K"            "pytest -k expression (e.g. K=test_pool)"
	@printf '\n\033[1mExamples:\033[0m\n'
	@printf '  make test                                       \033[2m# full suite (reuse DB)\033[0m\n'
	@printf '  make test-fresh                                 \033[2m# full suite (recreate DB)\033[0m\n'
	@printf '  make test-file F=tests/test_reservation_modes.py\033[2m# single file\033[0m\n'
	@printf '  make test K=test_pool STOP=1 VERBOSE=1          \033[2m# filter + stop + verbose\033[0m\n'
	@printf '  make check                                      \033[2m# lint + types + test\033[0m\n'
	@printf '\n'

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

.PHONY: test
test: ##[test] Run full test suite (reuses test DB)
	NETBOX_PATH=$(NETBOX_PATH) \
	python -m pytest $(TESTS_DIR) $(PYTEST_FLAGS) $(if $(K),-k "$(K)")
	@printf '\033[32m✔ Tests passed.\033[0m\n'

.PHONY: test-fresh
test-fresh: ##[test] Run full test suite with fresh database (--create-db)
	NETBOX_PATH=$(NETBOX_PATH) \
	python -m pytest $(TESTS_DIR) --create-db $(PYTEST_FLAGS) $(if $(K),-k "$(K)")
	@printf '\033[32m✔ Tests passed (fresh DB).\033[0m\n'

.PHONY: test-file
test-file: ##[test] Run a single test file (F=path/to/test.py)
ifndef F
	$(error Set F=<test file>, e.g. make test-file F=tests/test_reservation_modes.py)
endif
	NETBOX_PATH=$(NETBOX_PATH) \
	python -m pytest $(F) $(PYTEST_FLAGS) $(if $(K),-k "$(K)")
	@printf '\033[32m✔ Tests passed.\033[0m\n'

.PHONY: test-cov
test-cov: ##[test] Run tests with coverage report
	NETBOX_PATH=$(NETBOX_PATH) \
	python -m pytest $(TESTS_DIR) --cov=$(PLUGIN_PKG) --cov-report=term-missing --cov-report=html $(PYTEST_FLAGS) $(if $(K),-k "$(K)")
	@printf '\033[32m✔ Coverage report written to htmlcov/\033[0m\n'

# ---------------------------------------------------------------------------
# Lint & format
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ##[lint] Run ruff linter
	ruff check $(PLUGIN_PKG) $(TESTS_DIR)
	@printf '\033[32m✔ Lint passed.\033[0m\n'

.PHONY: format
format: ##[lint] Auto-format code with ruff
	ruff format $(PLUGIN_PKG) $(TESTS_DIR)
	ruff check --fix $(PLUGIN_PKG) $(TESTS_DIR)
	@printf '\033[32m✔ Formatted.\033[0m\n'

.PHONY: format-check
format-check: ##[lint] Check formatting without changes
	ruff format --check $(PLUGIN_PKG) $(TESTS_DIR)
	@printf '\033[32m✔ Format check passed.\033[0m\n'

# ---------------------------------------------------------------------------
# Type checking
# ---------------------------------------------------------------------------

.PHONY: mypy
mypy: ##[types] Run mypy type checking
	mypy $(PLUGIN_PKG)
	@printf '\033[32m✔ Type check passed.\033[0m\n'

# ---------------------------------------------------------------------------
# Combined checks
# ---------------------------------------------------------------------------

.PHONY: check
check: lint format-check test ##[test] Run lint + format check + tests

.PHONY: pre-commit
pre-commit: ##[lint] Run pre-commit hooks on all files
	pre-commit run --all-files

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ##[cleanup] Remove build artifacts and caches
	rm -rf *.egg-info dist build htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@printf '\033[32m✔ Cleaned.\033[0m\n'
