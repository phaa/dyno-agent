from core.prompt_loader import load_prompt
from agents.state import AgentSummary

# Load versioned prompts from external files
SYSTEM = load_prompt("llm_node", "system", version="1.0.0")
SUMMARY_PROMPT = load_prompt("summarization_node", "summary", version="1.0.1")
ERROR_PROMPT = load_prompt("error_llm", "system", version="1.0.0")

INITIAL_SUMMARY: AgentSummary = {
    "actions": []
}

# Sliding Window Configuration

# Token limits for message compression
TOKEN_WINDOW_LIMIT = 4500  # ~4-5K tokens before summarization
TAIL_TOKENS = 800  # Keep this many tokens of recent messages after summarization

# Approximate tokens per message (conservative estimate for token counting)
TOKENS_PER_MESSAGE = 50  # Average tokens per message (used for quick estimation)
