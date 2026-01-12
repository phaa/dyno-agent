import json
import logging
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
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
    """
    Production-grade conversation summarization with checkpointer optimization.
    
    Purpose: Prevents context window overflow by condensing conversation history
    into structured summaries while optimizing PostgreSQL checkpointer storage.
    
    Architecture:
    - Trigger Logic: Activates when messages ≥6 or tokens >1800 (configurable)
    - LLM Chain: Uses JsonOutputParser for robust structured output parsing
    - Checkpointer Optimization: Replaces message history with single summary marker
    - Fail-Safe: Graceful degradation - keeps original messages on parsing errors
    
    Summary Schema:
    ```json
    {
        "decisions": ["Vehicle X allocated to Dyno 3"],
        "constraints": ["AWD vehicles only", "Maintenance window 2-4pm"],
        "open_tasks": ["Check dyno availability next week"],
        "context": "User managing vehicle allocations for Q4 testing"
    }
    ```
    
    Error Handling:
    - Parsing Failures: Falls back to original messages, no data loss
    - LLM Timeouts: Graceful degradation with detailed error logging
    - State Corruption: Validates summary structure before committing
    
    Args:
        state: GraphState containing messages and optional existing summary
        
    Returns:
        GraphState: Updated state with new summary and single summary marker message
                   or unchanged state (if summarization not needed/failed)
    """
    messages = state.get("messages", [])
    summary = state.get("summary", INITIAL_SUMMARY)
    conversation_id = state.get("conversation_id", "unknown")
    
    if not should_summarize(messages):
        return state # No summarization needed, continue the flow
    
    logger.info(f"Summarizing {len(messages)} messages")
    
    prompt = SUMMARY_PROMPT.format(
        previous_summary=json.dumps(summary, ensure_ascii=False),
        messages=format_messages(messages)
    )

    try:
        chain = get_summary_llm() | JsonOutputParser()
        new_summary = await chain.ainvoke(prompt)
        
        # Validate summary structure before committing
        required_keys = {"decisions", "constraints", "open_tasks", "context"}
        if not isinstance(new_summary, dict) or not required_keys.issubset(new_summary.keys()):
            raise ValueError(f"Invalid summary structure. Expected keys: {required_keys}")
        
        logger.info(f"Summarization completed successfully for conversation_id: {conversation_id}")
        
        # Checkpointer optimization: Replace all messages with single summary marker
        summary_marker = SystemMessage(
            content=f"[CONVERSATION_SUMMARIZED] \n{json.dumps(new_summary, ensure_ascii=False)}"
        )
        
        return {
            "summary": new_summary,
            "messages": [summary_marker]  # Single message for checkpointer efficiency
        }
        
    except Exception as e:
        logger.exception(
            "Error during summarization_node execution",
            extra={
                "conversation_id": conversation_id,
                "node": "summarization_node"
            }
        )
        return state # Fail safe - preserve original state