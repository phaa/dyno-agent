# Dyno-Agent Makefile with Monitoring

.PHONY: help run stop build clean test migrate seed monitoring

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: ## Start all services (app + monitoring)
	docker-compose up -d

stop: ## Stop all services
	docker-compose down

build: ## Build all containers
	docker-compose build

clean: ## Clean containers and volumes
	docker-compose down -v
	docker system prune -f

test: ## Run tests
	cd app && python -m pytest

migrate: ## Run database migrations
	cd app && alembic upgrade head

seed: ## Seed database with test data
	cd app && python scripts/seed_data.py

monitoring: ## Start only monitoring stack
	docker-compose up -d prometheus grafana

logs: ## Show logs for all services
	docker-compose logs -f

logs-app: ## Show logs for FastAPI app
	docker-compose logs -f fastapi

logs-prometheus: ## Show Prometheus logs
	docker-compose logs -f prometheus

logs-grafana: ## Show Grafana logs
	docker-compose logs -f grafana

metrics: ## Check metrics endpoint
	curl -s http://localhost:8000/metrics/prometheus | head -20

grafana-url: ## Show Grafana URL and credentials
	@echo "Grafana URL: http://localhost:3000"
	@echo "Username: admin"
	@echo "Password: admin"

prometheus-url: ## Show Prometheus URL
	@echo "Prometheus URL: http://localhost:9090"

status: ## Show status of all services
	docker-compose ps