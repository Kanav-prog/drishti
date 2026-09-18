# ─────────────────────────────────────────────────────────────────────────────
# DRISHTI — Developer Command Centre
# ─────────────────────────────────────────────────────────────────────────────
# Usage: make <target>
# All team operations are here. No need to memorise CLI flags.
#
# QUICK START (first time):
#   make setup          → creates venv, installs all deps, generates graph
#
# DAILY DEV:
#   make dev            → starts API + frontend in parallel (two terminals auto)
#   make test           → runs full test suite
#   make lint           → checks code quality
#
# DEPLOYMENT:
#   make docker-up      → full stack in Docker (production-like local)
#   make deploy-render  → push to Render via git
# ─────────────────────────────────────────────────────────────────────────────

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Colours ──────────────────────────────────────────────────────────────────
BOLD   := \033[1m
RESET  := \033[0m
GREEN  := \033[32m
YELLOW := \033[33m
CYAN   := \033[36m
RED    := \033[31m

# ── Config ───────────────────────────────────────────────────────────────────
PYTHON      := python
PIP         := pip
VENV        := .venv
API_PORT    := 8000
FE_PORT     := 5173
COMPOSE     := docker compose -f docker-compose.simple.yml
COMPOSE_DEV := docker compose -f docker-compose.dev.yml

# ── Detect OS (Windows vs Unix) ──────────────────────────────────────────────
ifeq ($(OS),Windows_NT)
    PYTHON      := python
    VENV_ACT    := $(VENV)/Scripts/activate
    SEP         := ;
else
    PYTHON      := python3
    VENV_ACT    := $(VENV)/bin/activate
    SEP         := :
endif

# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "$(BOLD)$(CYAN)DRISHTI — Developer Command Centre$(RESET)"
	@echo "$(CYAN)════════════════════════════════════════════$(RESET)"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Setup$(RESET)"
	@echo "  make setup          First-time setup (venv + deps + graph)"
	@echo "  make install        Install Python deps only"
	@echo "  make install-dev    Install dev deps (pytest, ruff, httpx)"
	@echo "  make graph          Generate/refresh network_graph.json"
	@echo "  make osint          Enrich graph with CRS accident OSINT data"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Development$(RESET)"
	@echo "  make dev            Start API + Frontend (parallel)"
	@echo "  make api            Start API only (port $(API_PORT))"
	@echo "  make frontend       Start frontend only (port $(FE_PORT))"
	@echo "  make logs           Tail Docker logs (if running)"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Quality$(RESET)"
	@echo "  make test           Run full test suite (pytest)"
	@echo "  make test-api       Run API endpoint tests only"
	@echo "  make test-intel     Run intelligence layer tests only"
	@echo "  make test-cov       Run tests with coverage report"
	@echo "  make lint           Run ruff linter"
	@echo "  make lint-fix       Run ruff with auto-fix"
	@echo "  make typecheck      Run mypy type checker"
	@echo "  make format         Auto-format with ruff"
	@echo "  make check          lint + typecheck + test (pre-commit quality gate)"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Docker$(RESET)"
	@echo "  make docker-build   Build all Docker images"
	@echo "  make docker-up      Start full stack (Redis + API + Frontend)"
	@echo "  make docker-down    Stop all containers"
	@echo "  make docker-reload  Rebuild and restart (after code changes)"
	@echo "  make docker-ps      Show container status"
	@echo "  make docker-shell   Open shell in API container"
	@echo "  make docker-clean   Remove all DRISHTI containers + images"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Deploy$(RESET)"
	@echo "  make build-prod     Build frontend for production"
	@echo "  make deploy-render  Push to Render (requires git push)"
	@echo "  make health         Check live health endpoints"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Git$(RESET)"
	@echo "  make pr             Open GitHub PR for current branch"
	@echo "  make tag v=x.y.z    Create and push a release tag"
	@echo "  make changelog      Print commits since last tag"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: setup
setup: install install-dev graph osint
	@echo ""
	@echo "$(GREEN)✅ DRISHTI dev environment ready!$(RESET)"
	@echo "   → Run: $(BOLD)make dev$(RESET) to start everything"
	@echo ""

.PHONY: install
install:
	@echo "$(CYAN)📦 Installing Python dependencies...$(RESET)"
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: install-dev
install-dev:
	@echo "$(CYAN)🔧 Installing dev tools...$(RESET)"
	$(PYTHON) -m pip install ruff pytest pytest-asyncio pytest-cov httpx respx mypy

.PHONY: graph
graph:
	@echo "$(CYAN)🗺️  Generating IR network graph (51 nodes)...$(RESET)"
	$(PYTHON) scripts/generate_graph.py
	@echo "$(GREEN)✅ network_graph.json generated$(RESET)"

.PHONY: osint
osint:
	@echo "$(CYAN)🔍 Enriching graph with CRS OSINT data (32 accidents, 1981–2023)...$(RESET)"
	$(PYTHON) backend/data/osint_engine.py
	@echo "$(GREEN)✅ OSINT enrichment complete$(RESET)"

# ─────────────────────────────────────────────────────────────────────────────
# DEVELOPMENT
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: dev
dev:
	@echo "$(CYAN)🚀 Starting DRISHTI dev stack (API + Frontend)...$(RESET)"
	@echo "   API  → http://localhost:$(API_PORT)"
	@echo "   App  → http://localhost:$(FE_PORT)"
	@echo "   Ctrl+C to stop both"
	@echo ""
	@$(PYTHON) -m uvicorn backend.api.server:app --host 0.0.0.0 --port $(API_PORT) --reload & \
	 cd frontend && npm run dev & \
	 wait

.PHONY: api
api:
	@echo "$(CYAN)🔌 Starting API server on :$(API_PORT)...$(RESET)"
	$(PYTHON) -m uvicorn backend.api.server:app --host 0.0.0.0 --port $(API_PORT) --reload --log-level info

.PHONY: frontend
frontend:
	@echo "$(CYAN)⚛️  Starting frontend on :$(FE_PORT)...$(RESET)"
	cd frontend && npm run dev

.PHONY: logs
logs:
	$(COMPOSE) logs -f --tail=100

# ─────────────────────────────────────────────────────────────────────────────
# QUALITY
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: test
test:
	@echo "$(CYAN)🧪 Running full test suite...$(RESET)"
	$(PYTHON) -m pytest tests/ -v --tb=short

.PHONY: test-api
test-api:
	@echo "$(CYAN)🧪 Running API tests...$(RESET)"
	$(PYTHON) -m pytest tests/test_api.py -v --tb=short

.PHONY: test-intel
test-intel:
	@echo "$(CYAN)🧪 Running intelligence layer tests...$(RESET)"
	$(PYTHON) -m pytest tests/test_intelligence.py tests/test_cascade.py -v --tb=short

.PHONY: test-cov
test-cov:
	@echo "$(CYAN)📊 Running tests with coverage...$(RESET)"
	$(PYTHON) -m pytest tests/ --cov=backend --cov-report=term-missing --cov-report=html:htmlcov/
	@echo "$(GREEN)Coverage report → htmlcov/index.html$(RESET)"

.PHONY: lint
lint:
	@echo "$(CYAN)🔍 Running ruff linter...$(RESET)"
	$(PYTHON) -m ruff check backend/ scripts/

.PHONY: lint-fix
lint-fix:
	@echo "$(CYAN)🔧 Auto-fixing lint issues...$(RESET)"
	$(PYTHON) -m ruff check --fix backend/ scripts/

.PHONY: format
format:
	@echo "$(CYAN)✨ Formatting code...$(RESET)"
	$(PYTHON) -m ruff format backend/ scripts/

.PHONY: typecheck
typecheck:
	@echo "$(CYAN)🔎 Running mypy type checks...$(RESET)"
	$(PYTHON) -m mypy backend/ --ignore-missing-imports --no-strict-optional

.PHONY: check
check: lint test
	@echo "$(GREEN)✅ All quality checks passed$(RESET)"

# ─────────────────────────────────────────────────────────────────────────────
# DOCKER
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: docker-build
docker-build: graph osint build-prod
	@echo "$(CYAN)🐳 Building Docker images...$(RESET)"
	$(COMPOSE) build --no-cache

.PHONY: docker-up
docker-up:
	@echo "$(CYAN)🐳 Starting full DRISHTI stack...$(RESET)"
	$(COMPOSE) up -d
	@echo "$(GREEN)✅ Stack running at http://localhost$(RESET)"
	@$(MAKE) docker-ps

.PHONY: docker-down
docker-down:
	@echo "$(CYAN)🛑 Stopping DRISHTI stack...$(RESET)"
	$(COMPOSE) down

.PHONY: docker-reload
docker-reload: build-prod
	@echo "$(CYAN)🔄 Rebuilding and restarting...$(RESET)"
	$(COMPOSE) down
	$(COMPOSE) build
	$(COMPOSE) up -d
	sleep 5
	@$(MAKE) health

.PHONY: docker-ps
docker-ps:
	@echo "$(CYAN)📋 Container status:$(RESET)"
	$(COMPOSE) ps

.PHONY: docker-shell
docker-shell:
	$(COMPOSE) exec drishti-api /bin/bash

.PHONY: docker-clean
docker-clean:
	@echo "$(RED)🗑️  Removing all DRISHTI containers, images, volumes...$(RESET)"
	$(COMPOSE) down -v --rmi all
	@echo "$(GREEN)Done$(RESET)"

# ─────────────────────────────────────────────────────────────────────────────
# DEPLOY
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: build-prod
build-prod:
	@echo "$(CYAN)🏗️  Building frontend for production...$(RESET)"
	cd frontend && npm ci && npm run build
	@echo "$(GREEN)✅ Frontend built → frontend/dist/$(RESET)"

.PHONY: deploy-render
deploy-render: check build-prod
	@echo "$(CYAN)🚀 Deploying to Render...$(RESET)"
	git add -A
	git commit -m "deploy: $(shell date '+%Y-%m-%d %H:%M')"
	git push origin main
	@echo "$(GREEN)✅ Pushed. Render will auto-deploy in ~2 minutes.$(RESET)"
	@echo "   Monitor: https://dashboard.render.com"

.PHONY: health
health:
	@echo "$(CYAN)💓 Checking health endpoints...$(RESET)"
	@curl -sf http://localhost:$(API_PORT)/api/health | python -m json.tool || \
	 echo "$(RED)❌ API not responding on :$(API_PORT)$(RESET)"

# ─────────────────────────────────────────────────────────────────────────────
# GIT / RELEASE
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: pr
pr:
	@BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	 echo "$(CYAN)Opening PR for branch: $$BRANCH$(RESET)"; \
	 gh pr create --fill || echo "Install GitHub CLI: https://cli.github.com"

.PHONY: tag
tag:
	@if [ -z "$(v)" ]; then echo "Usage: make tag v=1.2.3"; exit 1; fi
	@echo "$(CYAN)🏷️  Tagging release v$(v)...$(RESET)"
	git tag -a v$(v) -m "Release v$(v)"
	git push origin v$(v)
	@echo "$(GREEN)✅ Tagged and pushed v$(v)$(RESET)"

.PHONY: changelog
changelog:
	@echo "$(CYAN)📋 Changes since last tag:$(RESET)"
	@git log $$(git describe --tags --abbrev=0)..HEAD --oneline || \
	 git log --oneline -20
