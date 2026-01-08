import json
import logging
from langchain_core.messages import BaseMessage
from ..state import GraphState
from .config import (
    SUMMARY_PROMPT, 
    INITIAL_SUMMARY, 
    get_summary_llm, 
    should_summarize
)

logger = logging.getLogger(__name__)

def format_messages(messages: list[BaseMessage]) -> str:
    return "\n".join(
        f"{m.type.upper()}: {m.content}" for m in messages
    )

async def summarization_node(state: GraphState):
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    
    if not should_summarize(messages):
        return state # No summarization needed, continue the flow
    
    prompt = SUMMARY_PROMPT.format(
        previous_summary=json.dumps(summary, ensure_ascii=False),
        messages=format_messages(messages)
    )

    try:
        summary_llm = get_summary_llm()
        response = await summary_llm.ainvoke(prompt)
        new_summary = json.loads(response.content)
    except Exception as e:
        logger.error(f"Summarization failed — keeping messages intact")
        return state # Fail safe

    return {
        "summary": new_summary,
        "messages": [] # Messages have been summarized
    }