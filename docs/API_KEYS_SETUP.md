# API Keys & Environment Setup

This document describes how to configure environment variables required to run the system.
Only the **Gemini API key** is mandatory. All other keys are optional and enable additional
observability and monitoring features.

---

## Environment Variables

Copy the variables below into your `.env` file and set the appropriate values.

```bash
# ===============================
# Required – LLM Provider
# ===============================
# Gemini API Key
# https://makersuite.google.com/app/apikey
GEMINI_API_KEY=your_gemini_key_here


# ===============================
# Optional – AI Observability
# ===============================
# LangSmith enables automatic LangGraph tracing,
# conversation history, token cost tracking,
# and detailed debugging.
#
# https://smith.langchain.com/
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=dyno-agent-production


# ===============================
# Optional – Enterprise Monitoring
# ===============================
# AWS CloudWatch integration for metrics,
# dashboards, alerting, and compliance logging.
#
# https://console.aws.amazon.com/iam/
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1


## Setup
```bash
cp .env.example .env
nano .env
make run
```

## Verification 
```bash
# LangSmith metrics
curl http://localhost:8000/chat/metrics/conversation

# CloudWatch logs
docker logs dyno_fastapi | grep CloudWatch

# System health
curl http://localhost:8000/metrics/health
```