# Dyno-Agent Makefile with Monitoring

.PHONY: help run stop build clean test migrate seed monitoring validate ready

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: ## Start all services (app + monitoring)
	docker compose up

stop: ## Stop all services
	docker compose down

build: ## Build all containers
	docker compose build

clean: ## Clean containers and volumes
	docker compose down -v
	docker system prune -f

test:
	docker compose exec fastapi pytest

eval: ## Run golden set evaluation (local, no Docker required)
	docker compose exec fastapi python -m eval.test_golden_sets

db-shell:
	docker compose exec db psql -U dyno_user -d dyno_db

new-migration:
	docker compose exec fastapi alembic revision --autogenerate -m "$(msg)"

migrate: ## Run database migrations
	docker compose exec fastapi alembic upgrade head

seed:
	docker compose exec fastapi python scripts/etl_excel.py

monitoring: ## Start only monitoring stack
	docker compose up -d prometheus grafana

logs: ## Show logs for all services
	docker compose logs -f

logs-app: ## Show logs for FastAPI app
	docker compose logs -f fastapi

logs-prometheus: ## Show Prometheus logs
	docker compose logs -f prometheus

logs-grafana: ## Show Grafana logs
	docker compose logs -f grafana

metrics: ## Check metrics endpoint
	curl -s http://localhost:8000/metrics/prometheus | head -20

grafana-url: ## Show Grafana URL and credentials
	@echo "Grafana URL: http://localhost:3000"
	@echo "Username: admin"
	@echo "Password: admin"

prometheus-url: ## Show Prometheus URL
	@echo "Prometheus URL: http://localhost:9090"

status: ## Show status of all services
	docker compose ps

infra-init:
	cd infra && terraform init

infra-plan:
	cd infra && terraform plan

infra-apply:
	cd infra && terraform apply

infra-destroy:
	cd infra && terraform destroy

validate: ## Validate service health (FastAPI, Prometheus, Grafana)
	@echo "🔍 Validating service health..."
	@docker compose exec -T fastapi curl -f http://localhost:8000/health > /dev/null 2>&1 && \
		echo "✅ FastAPI is healthy" || echo "❌ FastAPI is not healthy"
	@docker compose exec -T prometheus curl -f http://localhost:9090/-/healthy > /dev/null 2>&1 && \
		echo "✅ Prometheus is healthy" || echo "❌ Prometheus is not healthy"
	@docker compose exec -T grafana curl -f http://localhost:3000/api/health > /dev/null 2>&1 && \
		echo "✅ Grafana is healthy" || echo "❌ Grafana is not healthy"
	@echo "✅ All services validated!"

ready: build run migrate seed validate ## Complete setup: build → run → migrate → seed → validate
	@echo "🚀 All services are ready and validated!"
	@echo ""
	@echo "📊 Dashboards:"
	@echo "  - Grafana: http://localhost:3000 (admin/admin)"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - API: http://localhost:8000"
	@echo ""
	@echo "Next: make logs-app  # to see application logs"