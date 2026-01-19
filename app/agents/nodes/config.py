import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages.utils import count_tokens_approximately
from core.config import GEMINI_MODEL_ID
from core.prompt_loader import load_prompt
from ..tools import TOOLS
from ..state import AgentSummary

# Load versioned prompts from external files
SYSTEM = load_prompt("llm_node", "system", version="1.0.0")
SUMMARY_PROMPT = load_prompt("summarization_node", "summary", version="1.0.0")
CONVERSATION_SUMMARY_PROMPT = load_prompt("summarization_node", "conversation_summary", version="1.0.0")

INITIAL_SUMMARY: AgentSummary = {
    "decisions": [],
    "constraints": [],
    "open_tasks": [],
    "context": ""
}

# LLM instances - lazy initialization to avoid import errors
def get_summary_llm():
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_ID,
        temperature=0.0,
        max_output_tokens=400,
        max_retries=2,
    )

def get_llm():
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_ID,
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.5,
        max_output_tokens=1024,
        timeout=None,
        max_retries=2,
    )

# Tools setup - lazy initialization
def get_model_with_tools():
    llm = get_llm()
    return llm.bind_tools(TOOLS)

# Helper functions
def should_summarize(messages: list) -> bool:
    return (
        len(messages) >= 10 or
        count_tokens_approximately(messages) > 1800
    )