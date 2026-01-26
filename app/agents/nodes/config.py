from core.prompt_loader import load_prompt
from agents.state import AgentSummary

# Load versioned prompts from external files
SYSTEM = load_prompt("llm_node", "system", version="1.0.2")
SUMMARY_PROMPT = load_prompt("summarization_node", "summary", version="1.0.0")
CONVERSATION_SUMMARY_PROMPT = load_prompt("summarization_node", "conversation_summary", version="1.0.0")
ERROR_PROMPT = load_prompt("error_llm", "system", version="1.0.0")

INITIAL_SUMMARY: AgentSummary = {
    "decisions": [],
    "constraints": [],
    "open_tasks": [],
    "context": ""
}