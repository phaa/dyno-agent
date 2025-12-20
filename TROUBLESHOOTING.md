# Troubleshooting Guide

## Avisos Importantes

- **Production**: Avoid `docker compose down -v` as it removes volumes and persisted data.
- **Migrations**: These are mounted via volumes, not copied into the image. For faster builds.

---

## Docker Operations

### Rebuild Everything
```bash
make clean        # Remove containers e volumes
make run          # Reconstrói e inicia
```

### View Logs
```bash
make logs                    # Todos os serviços
docker compose logs -f fastapi   # Apenas FastAPI
docker compose logs -f db        # Apenas PostgreSQL
```

---

## Database & Migrations

### Normal Workflow
```bash
make new-migration msg="create vehicles table"
make migrate
make seed
```

### Reset Migrations (Development Only)
```bash
# 1. Enter database container
make db-shell

# 2. Reset database
DROP TABLE alembic_version;
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\q

# 3. Reset migrations
docker compose exec fastapi bash
rm -rf migrations/versions/*
alembic revision --autogenerate -m "initial migration"
alembic upgrade head
```

---

## Container Access

### Quick Access
```bash
make db-shell                           # PostgreSQL CLI
docker compose exec fastapi bash       # FastAPI container
docker compose exec ui bash            # Streamlit container
```

### Database Queries
```bash
# List tables
docker compose exec db psql -U dyno_user -d dyno_db -c '\dt'

# Run query
docker compose exec db psql -U dyno_user -d dyno_db -c "SELECT * FROM dynos;"
```

---

## Testing

```bash
make test         # Run all tests
make test-cov     # With coverage report
```

---

## Common Issues

### Port Already in Use
```bash
# Check what's using port 8000
lsof -i :8000
# Kill process if needed
kill -9 <PID>
```

### Database Connection Issues
```bash
# Check if database is running
docker compose ps
# Restart database
docker compose restart db
```

### Migration Conflicts
```bash
# Check current migration status
docker compose exec fastapi alembic current
# Check migration history
docker compose exec fastapi alembic history
```