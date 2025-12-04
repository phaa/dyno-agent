PROJECT_NAME=juris-llm

run:
	docker-compose -f infra/docker-compose.yml up --build

test:
	pytest --cov=app --cov-report=term --cov-report=html

test-fast:
	pytest

build:
	docker-compose -f infra/docker-compose.yml build

stop:
	docker-compose -f infra/docker-compose.yml down