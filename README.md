# Atenção 
Evite docker compose down -v em produção, pois ele remove volumes e dados persistidos.

# Migrations
As migrations não são copiadas no build da imagem para evitar rebuilds desnecessários. Em vez disso, elas são montadas no container via volumes no docker-compose.yml, garantindo que o Alembic continue funcionando normalmente.
- .dockerignore exclui fastapi-app/migrations do build.
- O docker-compose.yml monta ./fastapi-app/migrations:/app/migrations em runtime.
- build mais rápido, imagem mais leve, migrations continuam versionadas no repositório.
- Para rodar migrations: _veja a seção sobre migrations_

# Subir ou reconstruir containers
```bash
# Desliga containers e remove volumes (cuidado: remove dados persistidos em volumes Docker)
docker compose down -v
# Sobe containers e rebuilda imagens
docker compose up --build
```

# Visualizar logs
```bash
docker compose logs -f fastapi   # Logs do FastAPI
docker compose logs -f db        # Logs do Postgres
docker compose logs -f vllm      # Logs do serviço VLLM
```

# Inicializar banco de dados e migrations
```bash
# Inicializa Alembic (apenas na primeira vez)
alembic init migrations
```

# Sempre que alterar os models
```bash
# Gera uma migration automaticamente comparando models x banco
docker compose exec fastapi alembic revision --autogenerate -m "create vehicles and dynos"
# Aplica as migrations no banco
docker compose exec fastapi alembic upgrade head
```

# Quando houver problemas de migration
Use apenas em desenvolvimento. Não recomendado em produção sem cuidado.
```bash
# Entrar no container FastAPI
docker compose exec fastapi bash

# Limpar migrations antigas
rm -rf migrations/versions/*

# Entrar no container do banco para limpar a tabela de controle de migrations
docker-compose exec db psql -U dyno_user -d dyno_db

DROP TABLE alembic_version;

# Para sair do postgree
\q 

# Criar nova migration inicial
alembic revision --autogenerate -m "initial migration"

# Aplicar no banco
alembic upgrade head
```

# Entrar nos containers em execução
```bash
# FastAPI
docker compose exec fastapi bash

# PostgreSQL (CLI psql)
docker-compose exec db psql -U dyno_user -d dyno_db

# Streamlit
docker compose exec ui bash
```

# Executar comandos sem entrar no container
```bash
# Criar nova migration
docker compose exec fastapi alembic revision --autogenerate -m "mensagem da mudança"

# Aplicar migrations
docker compose exec fastapi alembic upgrade head

# Popular banco de dados com seed
docker compose exec fastapi python scripts/seed_data.py

# Rodar testes
docker compose exec fastapi pytest
```

# Container do PostgreSQL
```bash
# Consultar tabelas no PostgreSQL
docker-compose exec db psql -U dyno_user -d dyno_db -c '\dt'

# Executar alguma query dentro do container
docker-compose exec db psql -U dyno_user -d dyno_db -c "SELECT * FROM dynos;"
```