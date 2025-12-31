# Dyno-Agent

**MLOps and AI Engineering** project demonstrating an intelligent agent for **vehicle allocation on dynamometers**.  
The system combines **structured data (SQL)** and **unstructured data (technical documentation via RAG)** to suggest intelligent allocations, considering:

- Test type  
- Vehicle weight (<10k lbs or >10k lbs)  
- Traction (2WD or AWD)  
- Dyno availability by date  

## About

This project is inspired by real-world work performed as an AI Engineer at Ford Motor Company's Michigan Proving Grounds (MPG). The original system automated vehicle-to-dynamometer scheduling that was previously done manually through spreadsheets, saving over **100 hours of manual work monthly**.

**Key Impact:**
- Eliminated manual scheduling errors and double-bookings
- Reduced allocation conflicts through intelligent constraint checking
- Enabled natural language queries for occupancy reports and dyno utilization
- Automated allocation updates and vehicle consultations via conversational AI
- Provided real-time insights into dyno capacity and usage patterns

The agentic AI approach allows engineers to interact with the system using natural language, making complex scheduling decisions accessible to non-technical staff while maintaining data integrity and operational efficiency.

---

## Architecture

```
[ External UI ]  <--->  [ FastAPI API ]  <--->  [ PostgreSQL (data) ]
                                |
                                +---> [ LangChain Agent ]
                                       |--> [ SQL Tool (Postgres) ]
                                       |--> [ FAISS (technical docs) ]
                                       |--> [ Cloud LLM APIs ]
```

- **FastAPI** → Data orchestration, LangChain agent, and REST endpoints  
- **PostgreSQL** → Relational database for vehicles, dynos, and allocations  
- **LangChain Agent** → Decision logic and tool orchestration  
- **FAISS** → Semantic search for documentation and manuals  
- **Cloud LLMs** → OpenAI/Anthropic APIs for natural language processing  
- **Docker Compose** → Multi-service local infrastructure  

---

## Tech Stack

- **Infrastructure** → Docker, docker-compose  
- **Backend** → FastAPI, SQLAlchemy, Alembic, Pydantic  
- **Database** → PostgreSQL  
- **AI** → LangChain, OpenAI/Anthropic APIs, FAISS  
- **MLOps** → CI/CD (GitHub Actions), Local Kubernetes (future)  

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/your-user/dyno-agent.git
cd dyno-agent
```

### 2. Build and run containers
```bash
make run
# or
docker compose up --build -d
```

### 3. Verify running services
- FastAPI → http://localhost:8000/docs  
- PostgreSQL → localhost:5432  

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

## Additional Documentation

- **Troubleshooting** → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Infrastructure** → [INFRASTRUCTURE.md](INFRASTRUCTURE.md)
- **CI/CD** → [CICD.md](CICD.md)

---

## 👨💻 Author
**Pedro Henrique Azevedo** — Demonstrating real-world AI Engineering solutions from Ford Motor Company MPG 🚀