# Dyno-Agent — Executive Overview (For Recruiters)

> **Production-grade AI system for industrial scheduling, designed with cost control, reliability, and observability as first-class concerns.**

This repository demonstrates how I design, build, and operate **AI systems that work in production** — not prompt-only demos or experimental notebooks.

---

## What This Project Is

**Dyno-Agent** is an AI-powered system that automates vehicle-to-dynamometer scheduling, a workflow traditionally managed via Excel and manual coordination.

The system replaces manual allocation with a **conversational AI interface backed by deterministic backend logic**, ensuring correctness, predictability, and auditability.

This project is inspired by real-world industrial workflows similar to those used in automotive testing environments, implemented independently for portfolio purposes.

---

## Business Impact (Projected)

- **100+ engineering hours saved per month**
- **Zero double-booking conflicts by design**
- **Sub-second response times** for most operational queries
- **Natural language access** for non-technical users

All impact metrics are **capability-based projections**, not live production KPIs.

---

## Why This Is Not a Typical “LLM Project”

Many AI demos:
- encode business logic inside prompts  
- have unpredictable inference costs  
- fail under concurrency  
- lack observability and debugging paths  

**Dyno-Agent was explicitly designed to avoid these pitfalls.**

### Core Design Principles
- LLMs assist decision-making — they do not own it
- All scheduling logic is deterministic and database-backed
- PostgreSQL constraints and transactions are the source of truth
- Every AI interaction is observable, measurable, and auditable

---

## Technical Snapshot

- **Backend**: FastAPI (async, SQLAlchemy 2.0)
- **AI Orchestration**: LangGraph with 9 specialized tools
- **Database**: PostgreSQL (array operators, optimized indexes)
- **Concurrency**: Row-level locking (`SELECT ... FOR UPDATE`)
- **Infrastructure**: AWS ECS + RDS (Terraform)
- **Observability**: Prometheus, Grafana, CloudWatch, LangSmith

This system reflects **production engineering standards**, not experimental prototypes.

---

## What This Project Demonstrates

### AI Engineering
- Cost-aware LLM usage
- Deterministic AI architectures
- Tool-based agent design
- Observability-first AI systems

### Software Engineering
- Clean backend architecture
- Strong database modeling
- Explicit concurrency control
- Clear separation of concerns

### Production Readiness
- Infrastructure as Code (Terraform)
- CI/CD and deployment workflows
- Monitoring and metrics by default
- Designed failure modes and debuggability

---

## How to Evaluate This Repository Quickly

If time is limited:

1. Read `README.md` — system overview  
2. Review `docs/TECHNICAL_ARCHITECTURE.md` — architectural depth  
3. Skim `MENTORSHIP_GUIDE_PRODUCTION_WITH_CODE.md` — decision-making rationale  

You do **not** need to read the entire documentation set.

---

## Legal & Portfolio Disclaimer

This is an **independent portfolio project**.

- No proprietary Ford Motor Company code
- No internal data or confidential systems
- All implementations are original
- Industrial workflows are generalized and anonymized

---

## Author

**Pedro Henrique Azevedo**  
AI Engineer — Production & Industrial AI Systems  

- LinkedIn: https://www.linkedin.com/in/pedrohazevedo/  
- GitHub: https://github.com/phaa  
- Email: dev.phazevedo@gmail.com  

---

> *Good AI engineering is not about smarter models —  
> it is about safer, cheaper, and more reliable systems.*
