# Dyno-Agent

**MLOps and AI Engineering** project simulating an intelligent agent for **vehicle allocation on dynamometers**.  
The system combines **structured data (SQL)** and **unstructured data (technical documentation via RAG)** to suggest intelligent allocations, considering:

- Test type  
- Vehicle weight (<10k lbs or >10k lbs)  
- Traction (2WD or AWD)  
- Dyno availability by date  

---

## Architecture

```
[ Streamlit UI ]  <--->  [ FastAPI API ]  <--->  [ PostgreSQL (data) ]
                                 |
                                 +---> [ LangChain Agent ]
                                        |--> [ SQL Tool (Postgres) ]
                                        |--> [ FAISS (technical docs) ]
                                        |--> [ vLLM (GPU LLM) ]
```

- **Streamlit UI** → Interactive user interface  
- **FastAPI** → Data orchestration, LangChain agent, and REST endpoints  
- **PostgreSQL** → Relational database for vehicles, dynos, and allocations  
- **LangChain Agent** → Decision logic and tool orchestration  
- **FAISS** → Semantic search for documentation and manuals  
- **vLLM** → Accelerated GPU inference  
- **Docker Compose** → Multi-service local infrastructure  

---

## Tech Stack

- **Infrastructure** → Docker, docker-compose, NVIDIA Container Toolkit  
- **Backend** → FastAPI, SQLAlchemy, Alembic, Pydantic  
- **Database** → PostgreSQL  
- **AI** → LangChain, vLLM, Hugging Face Models, FAISS  
- **Frontend** → Streamlit  
- **MLOps** → CI/CD (GitHub Actions), Local Kubernetes (future)  

---

## Setup

### 1. Clone the repository
```
git clone https://github.com/your-user/dyno-agent.git
cd dyno-agent
```

### 2. Build and run containers
```
make run
# or
docker compose up --build -d
```

### 3. Verify running services
- FastAPI → http://localhost:8000/docs  
- Streamlit → http://localhost:8501  
- PostgreSQL → localhost:5432  
- vLLM → http://localhost:8001/v1  

---

## Development Commands

### Quick Start
```bash
make run          # Start all services
make logs         # View logs
make stop         # Stop services
```

### Database Operations
```bash
make migrate                    # Run migrations
make new-migration msg="text"   # Create new migration
make seed                       # Populate sample data
make db-shell                   # Access PostgreSQL
```

### Testing
```bash
make test         # Run tests
make test-cov     # Run tests with coverage
```

### Infrastructure (AWS)
```bash
make infra-apply    # Deploy to AWS
make infra-destroy  # Remove from AWS
```

### Utilities
```bash
make clean        # Clean everything
make help         # List all commands
```  

---

## Development Workflow

### Database Migrations
```bash
make new-migration msg="add new table"
make migrate
```

### Populate Database
```bash
make seed
```

### Run Tests
```bash
make test
```

---

## Troubleshooting

### Alembic (broken migrations)
If you encounter revision errors:
```
# Enter container
docker compose exec fastapi bash

# Reset migrations (This deletes migration history)
rm -rf migrations/versions/*
alembic stamp head
alembic revision --autogenerate -m "reset migrations"
alembic upgrade head
```

### Accessing containers
```
# FastAPI
docker compose exec fastapi bash

# PostgreSQL
docker compose exec db psql -U postgres -d dyno_db

# Streamlit
docker compose exec ui bash
```

### vLLM (GPU issues)
1. Verify NVIDIA drivers inside container:
```
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```
2. If not working → reinstall NVIDIA Container Toolkit  
3. Ensure `vllm` service in `docker-compose.yml` has:
```
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

### Docker Compose issues
- Rebuild everything:
```
docker compose down -v
docker compose up --build
```

- View logs for a specific service:
```
docker compose logs -f fastapi
docker compose logs -f db
docker compose logs -f vllm
```

### FastAPI cannot connect to DB
Ensure your `DATABASE_URL` is correctly set:
```
postgresql+psycopg2://postgres:postgres@db:5432/dyno_db
```

### Streamlit UI not loading
- Check logs:
```
docker compose logs -f ui
```
- Verify port availability:
```
lsof -i :8501
```

---

## Next Steps

- [x] Finalize allocation logic and business rules  
- [ ] Integrate LangChain (SQL + FAISS + LLM)  
- [x] Expose agent via FastAPI  
- [ ] Connect Streamlit frontend to API  
- [ ] Add CI/CD pipeline  
- [ ] Implement observability (Prometheus + Grafana)  

---

## 👨💻 Author
**Pedro Henrique Azevedo** — Educational project in MLOps & AI Engineering 🚀