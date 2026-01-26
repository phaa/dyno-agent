import re
import logging
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import AIMessage
from langgraph.graph import END
from ..state import GraphState

logger = logging.getLogger(__name__)

def should_summarize(messages: list) -> bool:
    return (
        len(messages) >= 10 or
        count_tokens_approximately(messages) > 1800
    )
    
# Routers (branching logic)
def route_from_schema(state: GraphState) -> str:
    """Routing after DB shema fetching.
    
    Routing Logic:
    1. Check if summarization is needed before deciding next step
    
    This ensures the history gets compressed before continuing the graph,
    preventing unbounded context growth during multi-turn interactions.
    
    Returns:
        str: Next node name ('summarize', 'llm')
    """
    messages = state.get("messages", [])
    if should_summarize(messages):
        return "summarize"
    return "llm"  


def route_from_llm(state: GraphState):
    """Tool routing after LLM processing.
    
    Routing Logic:
    1. Tool Calls: Routes to direct tool execution (schema always loaded at start)
    2. No Tools: Ends conversation normally
     
    Returns:
        str: Next node name ('tools', or END)
    """ 
    
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        # Schema is always loaded at start, so always route directly to tools
        return "tools"
    return END


def route_from_tools(state: GraphState):
    """Routing after tool execution with retry/error handling.

    - If a retryable error exists and attempts remain, loop back to tools.
    - If retries are exhausted, go to the error handler.
    - On success, continue to the llm node.
    
    Error Handling:
    - retry_count > 0: Routes back to tools for retry
    - retry_count = 0: Routes to graceful error handler
    - No error: Normal tool routing
    """

    if state.get("error"):
        if state.get("retry_count", 0) > 0:
            logger.info(
                f"Retrying tools after error: {state.get('error')} (attempts left: {state.get('retry_count')})"
            )
            return "tools"
        logger.error(f"Max retries exhausted for error: {state.get('error')}")
        return "error_llm" # End graph with graceful error handling and user message

    return "llm"


def db_disabled_node(state: GraphState) -> GraphState:
    """Handles the case where the database is empty or unreachable."""
    error_message = "Apparently our database is not configured. Aborting further operations"
    return {
        "messages": [AIMessage(content=error_message)]
    } 

# Deprecated in favor of error_llm node
def error_handler_node(state: GraphState) -> GraphState:
    """
    Production-grade error handler for exhausted retries and fatal errors.
    
    Error Recovery Strategy:
    - Provides user-friendly error message based on error type
    - Clears error state to prevent error propagation
    - Maintains conversation flow with graceful degradation
    - Logs detailed error information for debugging
    
    Args:
        state: GraphState containing error information
        
    Returns:
        GraphState: Updated state with error message and cleared error fields
    """
    error_msg = state.get("error", "Unknown error occurred")
    error_node = state.get("error_node", "unknown")
    
    logger.error(
        f"Graceful error handling triggered",
        extra={
            "error_message": error_msg,
            "failed_node": error_node,
            "retry_attempts_made": 2 - state.get("retry_count", 0)
        }
    )
    
    message = f"Encountered an issue processing the request at the {error_node} stage."
    
    return {
        "messages": [AIMessage(content=message)],
        "error": None,  # Clear error state
        "error_node": None,
        "retry_count": 2  # Reset retry count for next operation
    }



def strip_thinking_tags(content: str) -> str:
    """
    Remove all <thinking>...</thinking> segments from content.
    Handles multiple thinking blocks in a single pass for performance.

    Args:
        content: The message content that may contain thinking tags

    Returns:
        Content with thinking tags removed, or empty string if nothing remains
    """
    if not content:
        return ""

    # Fast path: no thinking tags present
    if "<thinking>" not in content:
        cleaned = '\n'.join(line.rstrip() for line in content.split('\n'))
        return re.sub(r'\n\s*\n+', '\n\n', cleaned).strip()

    # Single-pass removal of all segments between <thinking> and </thinking>
    # Avoids regex backtracking overhead on long messages
    result_chars = []
    i = 0
    n = len(content)
    in_thinking = False
    open_tag = "<thinking>"
    close_tag = "</thinking>"

    while i < n:
        if not in_thinking and content.startswith(open_tag, i):
            in_thinking = True
            i += len(open_tag)
            continue
        if in_thinking and content.startswith(close_tag, i):
            in_thinking = False
            i += len(close_tag)
            continue
        if not in_thinking:
            result_chars.append(content[i])
        i += 1

    cleaned = ''.join(result_chars)
    cleaned = '\n'.join(line.rstrip() for line in cleaned.split('\n'))
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned).strip()
    return cleaned
    return cleaned