# SuperAgent - Makefile for Docker Management
# Simplifies common Docker commands for development and deployment

.PHONY: help build up down restart logs shell status clean backup restore test

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

##@ General

help: ## Display this help message
	@echo "$(BLUE)SuperAgent - Docker Management$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Docker Lifecycle

build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker compose -f config/docker-compose.yml build

up: ## Start all services
	@echo "$(BLUE)Starting services...$(NC)"
	docker compose -f config/docker-compose.yml up -d
	@echo "$(GREEN)Services started successfully!$(NC)"
	@make status

down: ## Stop all services
	@echo "$(BLUE)Stopping services...$(NC)"
	docker compose -f config/docker-compose.yml down
	@echo "$(GREEN)Services stopped$(NC)"

restart: down up ## Restart all services

stop: ## Stop services without removing containers
	docker compose -f config/docker-compose.yml stop

start: ## Start previously stopped services
	docker compose -f config/docker-compose.yml start

##@ Logs and Monitoring

logs: ## View logs (follow mode)
	docker compose -f config/docker-compose.yml logs -f

logs-app: ## View SuperAgent logs only
	docker compose -f config/docker-compose.yml logs -f superagent

logs-redis: ## View Redis logs only
	docker compose -f config/docker-compose.yml logs -f redis

logs-tail: ## View last 100 lines of logs
	docker compose -f config/docker-compose.yml logs --tail=100

status: ## Show service status
	@echo "$(BLUE)Service Status:$(NC)"
	@docker compose -f config/docker-compose.yml ps
	@echo ""
	@echo "$(BLUE)Health Check:$(NC)"
	@docker inspect --format='{{.State.Health.Status}}' superagent-app 2>/dev/null || echo "Not running"

stats: ## Show resource usage statistics
	docker compose -f config/docker-compose.yml stats

##@ Development

shell: ## Open bash shell in SuperAgent container
	docker compose -f config/docker-compose.yml exec superagent /bin/bash

python: ## Open Python REPL in SuperAgent container
	docker compose -f config/docker-compose.yml exec superagent python

redis-cli: ## Open Redis CLI
	docker compose -f config/docker-compose.yml exec redis redis-cli

dev: ## Start services with code volume mount (for live editing)
	@echo "$(YELLOW)Starting in development mode...$(NC)"
	docker compose -f config/docker-compose.yml up -d
	@echo "$(GREEN)Development mode enabled$(NC)"

##@ SuperAgent CLI

cli-status: ## Run 'superagent status'
	docker compose -f config/docker-compose.yml exec superagent python agent_system/cli.py status

cli-route: ## Run 'superagent route' (requires TASK and DESC)
	@test -n "$(TASK)" || (echo "Error: TASK not set. Usage: make cli-route TASK=write_test DESC='Create login test'" && exit 1)
	@test -n "$(DESC)" || (echo "Error: DESC not set. Usage: make cli-route TASK=write_test DESC='Create login test'" && exit 1)
	docker compose -f config/docker-compose.yml exec superagent python agent_system/cli.py route $(TASK) "$(DESC)"

cli-kaya: ## Run 'superagent kaya' (requires CMD)
	@test -n "$(CMD)" || (echo "Error: CMD not set. Usage: make cli-kaya CMD='create test for login'" && exit 1)
	docker compose -f config/docker-compose.yml exec superagent python agent_system/cli.py kaya "$(CMD)"

cli-run: ## Run a test (requires TEST)
	@test -n "$(TEST)" || (echo "Error: TEST not set. Usage: make cli-run TEST=tests/auth.spec.ts" && exit 1)
	docker compose -f config/docker-compose.yml exec superagent python agent_system/cli.py run $(TEST)

cli-review: ## Review a test with Critic (requires TEST)
	@test -n "$(TEST)" || (echo "Error: TEST not set. Usage: make cli-review TEST=tests/auth.spec.ts" && exit 1)
	docker compose -f config/docker-compose.yml exec superagent python agent_system/cli.py review $(TEST)

cli-hitl: ## Show HITL queue
	docker compose -f config/docker-compose.yml exec superagent python agent_system/cli.py hitl list

##@ Testing

test: ## Run all tests
	docker compose -f config/docker-compose.yml exec superagent pytest tests/

test-unit: ## Run unit tests only
	docker compose -f config/docker-compose.yml exec superagent pytest tests/unit/

test-integration: ## Run integration tests only
	docker compose -f config/docker-compose.yml exec superagent pytest tests/integration/

test-cov: ## Run tests with coverage report
	docker compose -f config/docker-compose.yml exec superagent pytest --cov=agent_system --cov-report=html --cov-report=term

test-playwright: ## Run Playwright baseline tests
	docker compose -f config/docker-compose.yml exec superagent npx playwright test

##@ Data Management

backup: ## Backup volumes to data/backups/ directory
	@echo "$(BLUE)Backing up volumes...$(NC)"
	@mkdir -p data/backups
	docker run --rm \
		-v superagent-vector-db:/data \
		-v $(PWD)/data/backups:/backup \
		alpine tar czf /backup/vector_db_$$(date +%Y%m%d_%H%M%S).tar.gz /data
	docker run --rm \
		-v superagent-redis-data:/data \
		-v $(PWD)/data/backups:/backup \
		alpine tar czf /backup/redis_$$(date +%Y%m%d_%H%M%S).tar.gz /data
	@echo "$(GREEN)Backup completed!$(NC)"
	@ls -lh data/backups/

restore-vector: ## Restore vector DB from backup (requires FILE)
	@test -n "$(FILE)" || (echo "Error: FILE not set. Usage: make restore-vector FILE=vector_db_20250114.tar.gz" && exit 1)
	docker run --rm \
		-v superagent-vector-db:/data \
		-v $(PWD)/data/backups:/backup \
		alpine tar xzf /backup/$(FILE) -C /
	@echo "$(GREEN)Vector DB restored$(NC)"

restore-redis: ## Restore Redis from backup (requires FILE)
	@test -n "$(FILE)" || (echo "Error: FILE not set. Usage: make restore-redis FILE=redis_20250114.tar.gz" && exit 1)
	docker run --rm \
		-v superagent-redis-data:/data \
		-v $(PWD)/data/backups:/backup \
		alpine tar xzf /backup/$(FILE) -C /
	@echo "$(GREEN)Redis data restored$(NC)"

##@ Cleanup

clean: ## Remove stopped containers and dangling images
	@echo "$(YELLOW)Cleaning up...$(NC)"
	docker compose -f config/docker-compose.yml down
	docker image prune -f
	@echo "$(GREEN)Cleanup completed$(NC)"

clean-all: ## Remove all containers, images, volumes, and data (DANGEROUS)
	@echo "$(YELLOW)WARNING: This will delete all SuperAgent data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose -f config/docker-compose.yml down -v; \
		docker image rm superagent:latest 2>/dev/null || true; \
		rm -rf build/* data/logs/* data/vector_db/*; \
		echo "$(GREEN)All data removed$(NC)"; \
	else \
		echo "Cancelled"; \
	fi

clean-artifacts: ## Clean test artifacts (screenshots, videos, traces)
	@echo "$(BLUE)Cleaning test artifacts...$(NC)"
	rm -rf build/artifacts/* build/test-results/* build/playwright-reports/*
	@echo "$(GREEN)Artifacts cleaned$(NC)"

##@ Maintenance

rebuild: ## Rebuild images without cache
	@echo "$(BLUE)Rebuilding images...$(NC)"
	docker compose -f config/docker-compose.yml build --no-cache

pull: ## Pull latest base images
	docker compose -f config/docker-compose.yml pull

update: pull rebuild up ## Update and restart services

inspect-app: ## Inspect SuperAgent container
	docker inspect superagent-app

inspect-redis: ## Inspect Redis container
	docker inspect superagent-redis

network: ## Show network information
	docker network inspect superagent-network

volumes: ## List all volumes
	@echo "$(BLUE)Docker Volumes:$(NC)"
	@docker volume ls | grep superagent

##@ Quick Start

setup: ## Initial setup (create .env, build, start)
	@echo "$(BLUE)Setting up SuperAgent...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)Created .env file$(NC)"; \
		echo "$(YELLOW)Please edit .env and add your API keys$(NC)"; \
		exit 1; \
	fi
	@mkdir -p build/artifacts build/test-results build/playwright-reports data/logs data/vector_db data/backups
	@chmod -R 755 build data
	@make build
	@make up
	@echo "$(GREEN)Setup completed!$(NC)"

quick-start: setup ## Alias for setup

##@ Examples

example-status: ## Example: Check system status
	@echo "$(BLUE)Running: superagent status$(NC)"
	@make cli-status

example-route: ## Example: Route a task
	@echo "$(BLUE)Running: superagent route write_test 'Create login test'$(NC)"
	@make cli-route TASK=write_test DESC="Create login test"

example-kaya: ## Example: Run Kaya orchestrator
	@echo "$(BLUE)Running: superagent kaya 'create test for checkout'$(NC)"
	@make cli-kaya CMD="create test for checkout"

##@ Documentation

docs: ## Show quick reference
	@echo "$(BLUE)SuperAgent Docker Quick Reference$(NC)"
	@echo ""
	@echo "$(GREEN)Common Commands:$(NC)"
	@echo "  make up          - Start services"
	@echo "  make down        - Stop services"
	@echo "  make logs        - View logs"
	@echo "  make shell       - Open shell"
	@echo "  make status      - Service status"
	@echo "  make cli-status  - SuperAgent status"
	@echo ""
	@echo "$(GREEN)Testing:$(NC)"
	@echo "  make test        - Run all tests"
	@echo "  make test-unit   - Run unit tests"
	@echo ""
	@echo "$(GREEN)Data:$(NC)"
	@echo "  make backup      - Backup volumes"
	@echo "  make clean       - Cleanup"
	@echo ""
	@echo "For full documentation, see DOCKER_DEPLOYMENT.md"

version: ## Show version information
	@echo "SuperAgent v0.1.0"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$(docker compose version)"
