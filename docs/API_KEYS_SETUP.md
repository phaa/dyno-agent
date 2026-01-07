# API Keys Setup Guide

## Required API Keys

### 1. **Gemini API Key** (Required)
```bash
# Get your key from Google AI Studio
# https://makersuite.google.com/app/apikey

GEMINI_API_KEY=AIzaSyB0MU5TnwEg_YNlAECwkfrcthL3PFNflSo
```

### 2. **LangSmith API Key** (Optional - AI Observability)
```bash
# Get your key from LangSmith
# https://smith.langchain.com/

LANGSMITH_API_KEY=ls__your_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=dyno-agent-production
```

**Benefits of LangSmith:**
- **Auto-tracing** - LangGraph traces automatically (no decorators needed)
- **Conversation tracking** - Every chat logged automatically
- **Cost monitoring** - Token usage per conversation
- **Performance analytics** - Response times, success rates
- **Debugging** - Detailed error analysis and tool execution traces

### 3. **AWS Credentials** (Optional - Enterprise Monitoring)
```bash
# For CloudWatch integration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

**Benefits of CloudWatch:**
- **Enterprise monitoring** - Metrics in AWS console
- **Alerting** - Automated notifications on issues
- **Compliance** - Enterprise-grade logging and audit trails

## Setup Instructions

### Step 1: Copy Environment File
```bash
cp .env.example .env
```

### Step 2: Edit Configuration
```bash
# Edit .env file with your keys
nano .env

# Required:
GEMINI_API_KEY=your_gemini_key_here

# Optional (but recommended):
LANGSMITH_API_KEY=your_langsmith_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=dyno-agent-production
```

### Step 3: Start System
```bash
make run
```

## What Works Without Optional Keys

### ✅ **With Only Gemini API Key:**
- Full AI agent functionality
- All allocation features
- Basic system metrics (Prometheus + Grafana)
- Database logging

### ✅ **With LangSmith Added:**
- **+ Conversation analytics**
- **+ Token cost tracking**
- **+ AI performance monitoring**
- **+ Advanced debugging**

### ✅ **With AWS Added:**
- **+ Enterprise monitoring**
- **+ CloudWatch dashboards**
- **+ Automated alerting**
- **+ Compliance logging**

## Getting API Keys

### Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key to your `.env` file

### LangSmith API Key
1. Go to [LangSmith](https://smith.langchain.com/)
2. Sign up/login
3. Go to Settings → API Keys
4. Create new key
5. Copy to your `.env` file

### AWS Credentials
1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Create new user with CloudWatch permissions
3. Generate access key
4. Copy credentials to `.env` file

## Verification

```bash
# Check if LangSmith is working
curl http://localhost:8000/chat/metrics/conversation

# Check if CloudWatch is configured
docker logs dyno_fastapi | grep "CloudWatch"

# Check system health
curl http://localhost:8000/metrics/health
```
