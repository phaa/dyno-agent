import os

GEMINI_MODEL_ID = "gemini-2.5-flash" # gemini-2.5-flash-lite
VLLM_URL = "http://vllm:8000/v1"
LOCAL_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct-AWQ" # local model
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BEDROCK_MODEL_ID = "amazon.nova-micro-v1:0"