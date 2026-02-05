import os
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
from langchain_google_genai import ChatGoogleGenerativeAI
from .config import (
    VLLM_URL, 
    LOCAL_MODEL_ID, 
    GEMINI_MODEL_ID, 
    AWS_REGION, 
    BEDROCK_MODEL_ID
)

class LLMFactory:
    def __init__(self, provider: str = "bedrock"):
        self._provider = provider

    # Clients
    @staticmethod
    def _get_bedrock_client():
        import boto3
        from botocore.config import Config

        config = Config(
            read_timeout=60,
            retries={"max_attempts": 2},
        )
        return boto3.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
            config=config,
        )

    # Remote 
    def _setup_llm(self, temperature: float, max_tokens: int):
        if self._provider == "local":
            return ChatOpenAI(
                model=LOCAL_MODEL_ID,
                base_url=VLLM_URL,
                api_key="not-needed",
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=60,
                max_retries=2,
            )
        elif self._provider == "bedrock":
            return ChatBedrock(
                model_id=BEDROCK_MODEL_ID,
                region_name=AWS_REGION,
                client=self._get_bedrock_client(),
                model_kwargs={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
        elif self._provider == "gemini":
            return ChatGoogleGenerativeAI(
                model=GEMINI_MODEL_ID,
                api_key=os.getenv("GEMINI_API_KEY"),
                temperature=temperature,
                max_output_tokens=max_tokens,
                timeout=60,
                max_retries=2,
            )

        raise ValueError(f"Unsupported provider: {self._provider}")

    # Public API 
    def get_llm(self):
        if self._provider == "local":
            return self._setup_llm(
                temperature=0.5,
                max_tokens=1500,
            )

        return self._setup_llm(
            temperature=0.0,
            max_tokens=1500,
        )

    def get_summary_llm(self):
        if self._provider == "local":
            # vLLM forces tool calling, so disable tools explicitly for summarization case
            return self._setup_llm(
                temperature=0.0,
                max_tokens=400,
            ).bind_tools([])

        return self._setup_llm(
            temperature=0.0,
            max_tokens=400,
        )

    def get_llm_with_tools(self, tools: list):
        return self.get_llm().bind_tools(tools)