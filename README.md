# Dyno Agent

docker compose down -v
docker compose up --build

docker compose logs -f fastapi
docker compose logs -f db
docker compose logs -f vllm

### Iniciar o banco
- alembic init migrations

## Toda vez que alterar os models
- alembic revision --autogenerate -m "create vehicles and dynos"
- alembic upgrade head



# Quando der problema de migration
docker compose exec fastapi bash
rm -rf migrations/versions/*

docker-compose exec db psql -U postgres -d dyno_db
DROP TABLE alembic_version;
\q
alembic revision --autogenerate -m "initial migration"
alembic upgrade head


## Entrar nos containers em execução
### FastAPI
docker compose exec fastapi bash

### Postgres (CLI psql)
docker compose exec db psql -U postgres -d dyno_db

### Streamlit
docker compose exec ui bash



docker compose exec fastapi alembic revision --autogenerate -m "mensagem da mudança"
docker compose exec fastapi alembic upgrade head

docker compose exec fastapi python scripts/seed_data.py
docker compose exec fastapi pytest
