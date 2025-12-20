PROJECT_NAME=dyno-agent

# Development (local)
run:
	docker compose up --build -d

stop:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

# Database
db-shell:
	docker compose exec db psql -U postgres -d dyno_db

migrate:
	docker compose exec fastapi alembic upgrade head

new-migration:
	docker compose exec fastapi alembic revision --autogenerate -m "$(msg)"

seed:
	docker compose exec fastapi python scripts/seed_data.py

# Testing
test:
	docker compose exec fastapi pytest

test-cov:
	docker compose exec fastapi pytest --cov=app --cov-report=term --cov-report=html

# Infrastructure (AWS)
infra-init:
	cd infra && terraform init

infra-plan:
	cd infra && terraform plan

infra-apply:
	cd infra && terraform apply

infra-destroy:
	cd infra && terraform destroy

# Cleanup
clean:
	docker compose down -v
	docker system prune -f

# Help
help:
	@echo "Available commands:"
	@echo "  run          - Start all services"
	@echo "  stop         - Stop all services"
	@echo "  logs         - View logs"
	@echo "  test         - Run tests"
	@echo "  migrate      - Run DB migrations"
	@echo "  infra-apply  - Deploy to AWS"
	@echo "  clean        - Clean everything"