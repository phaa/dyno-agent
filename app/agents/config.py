import os

LOCAL_INFERENCE = True
PROVIDER = "local" if LOCAL_INFERENCE else "bedrock" # bedrock | gemini | local

ENABLE_STREAM_WRITER = True

# Model IDs
GEMINI_MODEL_ID = "gemini-2.5-flashhhh" # gemini-2.5-flash-lite
BEDROCK_MODEL_ID = "amazon.nova-micro-v1:0"
LOCAL_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct-AWQ" # local model

# AWS Region (when needed)
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Local inference server URL
VLLM_URL = "http://vllm:8000/v1"

# Default state values
ERROR_RETRY_COUNT = 2  # Number of retries for retryable errors