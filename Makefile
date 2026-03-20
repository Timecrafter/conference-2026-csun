# CSUN AT Conference Analytics — Makefile
# Compatible with macOS (BSD make) and GNU make
#
# Usage: make <target>
#   make help       — show all targets
#   make setup      — install everything
#   make dashboard  — launch the Dash dashboard
#   make docs       — build & serve the documentation site

SHELL := /bin/zsh
.DEFAULT_GOAL := help

# ─── Colors (macOS-compatible printf) ─────────────────────────────────────────
C_RESET  := \033[0m
C_BOLD   := \033[1m
C_DIM    := \033[2m
C_BLUE   := \033[34m
C_GREEN  := \033[32m
C_YELLOW := \033[33m
C_CYAN   := \033[36m
C_RED    := \033[31m
C_MAG    := \033[35m
C_WHITE  := \033[37m

define header
	@printf "\n$(C_BOLD)$(C_BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(C_RESET)\n"
	@printf "$(C_BOLD)$(C_BLUE)  $(1)$(C_RESET)\n"
	@printf "$(C_BOLD)$(C_BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(C_RESET)\n\n"
endef

define success
	@printf "\n$(C_GREEN)  ✓ $(1)$(C_RESET)\n\n"
endef

define info
	@printf "$(C_CYAN)  → $(1)$(C_RESET)\n"
endef

define warn
	@printf "$(C_YELLOW)  ⚠ $(1)$(C_RESET)\n"
endef

define section
	@printf "  $(C_BOLD)$(C_MAG)$(1)$(C_RESET)\n"
endef

# ─── Environment ──────────────────────────────────────────────────────────────
UV      := uv
PYTHON  := $(UV) run python
PORT    ?= 8050
YEAR    ?= all

# ─── Help ─────────────────────────────────────────────────────────────────────

# Section markers — these are fake targets used only for help grouping.
# The help target parses lines matching "##@" as section headers.

.PHONY: help
help: ## Show this help
	@printf "\n$(C_BOLD)$(C_MAG)  CSUN AT Conference Analytics$(C_RESET)\n"
	@printf "$(C_DIM)  ─────────────────────────────$(C_RESET)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@ / { printf "\n  $(C_BOLD)$(C_YELLOW)%s$(C_RESET)\n", substr($$0, 5); next } \
		/^[a-zA-Z_-]+:.*?## / { \
			split($$1, parts, ":"); \
			target = parts[length(parts)]; \
			printf "  $(C_GREEN)%-20s$(C_RESET) %s\n", target, $$2 \
		}' $(MAKEFILE_LIST)
	@printf "\n$(C_DIM)  Options:$(C_RESET)\n"
	@printf "    YEAR=2024|2025|2026|all  $(C_DIM)# Target year (default: all)$(C_RESET)\n"
	@printf "    PORT=8050               $(C_DIM)# Dashboard/docs port$(C_RESET)\n"
	@printf "\n$(C_DIM)  Examples:$(C_RESET)\n"
	@printf "    make setup              $(C_DIM)# First-time install$(C_RESET)\n"
	@printf "    make scrape YEAR=2026   $(C_DIM)# Scrape one year$(C_RESET)\n"
	@printf "    make pipeline           $(C_DIM)# Full analysis pipeline$(C_RESET)\n"
	@printf "    make dashboard PORT=9000$(C_DIM)# Custom port$(C_RESET)\n"
	@printf "\n"

# ══════════════════════════════════════════════════════════════════════════════
##@ Setup & Environment
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: setup
setup: ## Install all dependencies and set up environment
	$(call header,Setting up CSUN Analytics)
	$(call info,Creating virtual environment...)
	$(UV) venv --python 3.12 2>/dev/null || true
	$(call info,Installing all dependencies...)
	$(UV) sync --all-extras
	@if [ ! -f .env.local ]; then \
		cp .env.example .env.local 2>/dev/null || true; \
		printf "$(C_YELLOW)  ⚠ Created .env.local — add your ANTHROPIC_API_KEY$(C_RESET)\n"; \
	fi
	$(call success,Setup complete)

.PHONY: install
install: ## Install core dependencies only
	$(call header,Installing dependencies)
	$(UV) sync
	$(call success,Installed)

.PHONY: install-all
install-all: ## Install all optional dependencies (dash, mkdocs, dev)
	$(call header,Installing all extras)
	$(UV) sync --all-extras
	$(call success,All extras installed)

.PHONY: env-check
env-check: ## Verify environment, dependencies, and API keys
	$(call header,Environment check)
	@printf "$(C_CYAN)  → Python: %s$(C_RESET)\n" "$$($(PYTHON) --version 2>&1)"
	@printf "$(C_CYAN)  → uv:     %s$(C_RESET)\n" "$$($(UV) --version 2>&1)"
	@$(PYTHON) -c "import csun_analytics; print('  \033[32m✓ csun_analytics:', csun_analytics.__file__, '\033[0m')" 2>&1 || \
		printf "$(C_RED)  ✗ csun_analytics not importable — run: make setup$(C_RESET)\n"
	@$(PYTHON) -c "import dash; print('  \033[32m✓ dash:', dash.__version__, '\033[0m')" 2>&1 || \
		printf "$(C_YELLOW)  ⚠ dash not installed — run: make install-all$(C_RESET)\n"
	@$(PYTHON) -c "import mkdocs; print('  \033[32m✓ mkdocs:', mkdocs.__version__, '\033[0m')" 2>&1 || \
		printf "$(C_YELLOW)  ⚠ mkdocs not installed — run: make install-all$(C_RESET)\n"
	@if [ -f .env.local ]; then \
		printf "$(C_GREEN)  ✓ .env.local exists$(C_RESET)\n"; \
		if grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env.local 2>/dev/null; then \
			printf "$(C_GREEN)  ✓ ANTHROPIC_API_KEY configured$(C_RESET)\n"; \
		else \
			printf "$(C_YELLOW)  ⚠ ANTHROPIC_API_KEY not set in .env.local$(C_RESET)\n"; \
		fi; \
	else \
		printf "$(C_YELLOW)  ⚠ No .env.local — run: make setup$(C_RESET)\n"; \
	fi
	@printf "\n"

.PHONY: clean
clean: ## Remove build artifacts, caches, generated site
	$(call header,Cleaning)
	$(call info,Removing __pycache__, build artifacts, site/...)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info site/ .ruff_cache/
	$(call success,Clean)

.PHONY: clean-venv
clean-venv: ## Remove and recreate virtual environment from scratch
	$(call header,Rebuilding virtual environment)
	rm -rf .venv
	$(UV) venv --python 3.12
	$(UV) sync --all-extras
	$(call success,Virtual environment rebuilt)

# ══════════════════════════════════════════════════════════════════════════════
##@ Data Collection
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: scrape
scrape: ## Scrape sessions (YEAR=2024|all)
	$(call header,Scraping sessions)
	$(PYTHON) main.py scrape-sessions --year $(YEAR)

.PHONY: scrape-all
scrape-all: ## Scrape all available data (sessions + exhibitors)
	$(call header,Scraping all data)
	$(PYTHON) main.py scrape-all

.PHONY: scrape-exhibitors
scrape-exhibitors: ## Scrape exhibitor data (YEAR=2024|all)
	$(call header,Scraping exhibitors)
	$(PYTHON) main.py scrape-exhibitors --year $(YEAR)

# ══════════════════════════════════════════════════════════════════════════════
##@ Analysis
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: analyze
analyze: ## Run session analysis (YEAR=2024|all)
	$(call header,Analyzing sessions)
	$(PYTHON) main.py analyze-sessions --year $(YEAR)

.PHONY: analyze-all
analyze-all: ## Run all single-year analyses
	$(call header,Running all analyses)
	$(PYTHON) main.py analyze-all

.PHONY: comprehensive
comprehensive: ## Full multi-year comprehensive analysis
	$(call header,Comprehensive analysis)
	$(PYTHON) main.py comprehensive

.PHONY: knowledge-graph
knowledge-graph: ## Build knowledge graph from session data
	$(call header,Building knowledge graph)
	$(PYTHON) main.py knowledge-graph

.PHONY: normalize
normalize: ## Normalize topics using cached taxonomy
	$(call header,Topic normalization)
	$(PYTHON) main.py normalize-topics

.PHONY: normalize-force
normalize-force: ## Re-generate topic taxonomy via Claude API (requires key)
	$(call header,Topic normalization (via Claude))
	@if [ -z "$$ANTHROPIC_API_KEY" ] && ! grep -q "^ANTHROPIC_API_KEY=" .env.local 2>/dev/null; then \
		printf "$(C_RED)  ✗ ANTHROPIC_API_KEY not set$(C_RESET)\n"; \
		printf "$(C_DIM)    Add it to .env.local or export it:$(C_RESET)\n"; \
		printf "$(C_DIM)    echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env.local$(C_RESET)\n\n"; \
		exit 1; \
	fi
	$(PYTHON) main.py normalize-topics --force

.PHONY: pipeline
pipeline: comprehensive knowledge-graph ## Run full pipeline: comprehensive + knowledge graph
	$(call success,Full pipeline complete)

# ══════════════════════════════════════════════════════════════════════════════
##@ Visualization & Serving
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: dashboard
dashboard: ## Launch Plotly Dash dashboard (PORT=8050)
	$(call header,Starting dashboard)
	$(call info,http://localhost:$(PORT))
	$(PYTHON) main.py dashboard --port $(PORT)

.PHONY: dashboard-debug
dashboard-debug: ## Launch dashboard in debug mode with hot reload
	$(call header,Starting dashboard (debug))
	$(call info,http://localhost:$(PORT))
	$(PYTHON) main.py dashboard --port $(PORT) --debug

.PHONY: docs
docs: ## Build and serve documentation site
	$(call header,Building documentation)
	$(PYTHON) main.py docs --serve

.PHONY: docs-build
docs-build: ## Build documentation site (no server)
	$(call header,Building documentation)
	$(PYTHON) main.py docs
	$(call success,Site built to site/)

# ══════════════════════════════════════════════════════════════════════════════
##@ Development
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: lint
lint: ## Run ruff linter
	$(call header,Linting)
	$(UV) run ruff check src/ main.py
	$(call success,Lint passed)

.PHONY: format
format: ## Auto-format code with ruff
	$(call header,Formatting)
	$(UV) run ruff format src/ main.py
	$(UV) run ruff check --fix src/ main.py
	$(call success,Formatted)

.PHONY: test
test: ## Run tests
	$(call header,Running tests)
	$(UV) run pytest -v

.PHONY: check
check: lint test ## Run lint + tests
	$(call success,All checks passed)

# ══════════════════════════════════════════════════════════════════════════════
##@ Workflows
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: refresh
refresh: scrape-all pipeline docs-build ## Full refresh: scrape → analyze → build docs
	$(call success,Full refresh complete)
