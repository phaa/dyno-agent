"""Router utilities for graph branching logic."""

import logging
from agents.state import GraphState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


def handle_retry_logic(state: GraphState, retry_node: str, error_node: str = "error_llm") -> str:
    """
    Encapsulates retry logic for error handling in routing functions.
    
    Args:
        state: Current GraphState
        retry_node: Node to return to for retry
        error_node: Node to route to when retries exhausted (default: "error_llm")
    
    Returns:
        str: Next node name, or None if no error
    """
    error = state.get("error")
    if not error:
        return None
    
    retry_count = state.get("retry_count", 0)
    if retry_count > 0:
        logger.info(
            f"Retrying {retry_node} after error: {error} (attempts left: {retry_count})"
        )
        return retry_node
    
    logger.error(f"Max retries exhausted for error: {error}")
    return error_node


def route_from_schema(state: GraphState) -> str:
    """Routing after DB shema fetching.
    
    Verify if schema was loaded successfully; if not, route to error handling.
    
    Returns:
        str: Next node name ('error_llm', 'llm')
    """
    
    # Uncomment for detailed state logging
    """ logger.critical("STATE SNAPSHOT")
    for k, v in state.items():
        if isinstance(v, list):
            logger.critical(f"{k}: {sum(len(msg.content) for msg in v)} chars in list of {len(v)} items")
        else:
            logger.critical(f"{k}: {v}")
    
    for m in state.get("messages"):
        logger.critical("MSG %s %s", m.type, len(m.content)) """
    
    retry_result = handle_retry_logic(state, "get_schema")
    if retry_result is not None:
        return retry_result
    
    return "llm"  # Proceed to LLM 


def route_from_llm(state: GraphState):
    """Tool routing after LLM processing.
    
    Routing Logic:
    1. Tool Calls: Routes to direct tool execution (schema always loaded at start)
    2. No Tools: Routes to summarization for context management
     
    Returns:
        str: Next node name ('tools', or 'summarize')
    """ 
    
    retry_result = handle_retry_logic(state, "llm")
    if retry_result is not None:
        return retry_result
    
    last = state.get("messages")[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "summarize"


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

    retry_result = handle_retry_logic(state, "tools")
    if retry_result is not None:
        return retry_result

    return "llm"
