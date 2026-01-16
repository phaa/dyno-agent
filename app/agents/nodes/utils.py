import logging
from langchain_core.messages import AIMessage
from langgraph.graph import END
from ..state import GraphState, RetryableException, FatalException

logger = logging.getLogger(__name__)

# Routers (branching logic)
def route_from_llm(state: GraphState):
    """Routing with error handling after LLM processing.
    
    Routing Logic:
    - Error State: Routes to error handler based on retry_count
    - Tool Calls: Routes to schema loading or direct tool execution
    - No Tools: Ends conversation normally
    
    Error Handling:
    - retry_count > 0: Routes back to tools for retry
    - retry_count = 0: Routes to graceful error handler
    - No error: Normal tool/schema routing
    
    Returns:
        str: Next node name ('error_handler', 'get_schema', 'tools', or END)
    """
    # Check for error state first
    if state.get("error"):
        if state.get("retry_count", 0) > 0:
            logger.info(f"Retrying after error: {state.get('error')} (attempts left: {state.get('retry_count')})")
            return "tools"  # Retry using same tools node
        else:
            logger.error(f"Max retries exhausted for error: {state.get('error')}")
            return "error_handler"
    
    # Normal routing logic
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        # Check if any tool call is query_database
        if any(tool_call["name"] == "query_database" for tool_call in last.tool_calls):
            return "get_schema"
        return "tools"
    
    return END


def check_db(state: GraphState):
    """Decide whether to continue to summarize or terminate if DB is unavailable."""
    # For now, we'll assume DB is available and let individual tools handle DB errors
    # This is the entry point check - we can add actual DB connectivity check here
    return "summarize"


def db_disabled_node(state: GraphState) -> GraphState:
    """Handles the case where the database is empty or unreachable."""
    error_message = "Apparently our database is not configured. Aborting further operations"
    return {
        "messages": [AIMessage(content=error_message)]
    } 


def graceful_error_handler(state: GraphState) -> GraphState:
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
    
    user_message = "I encountered an issue processing your request. Please try rephrasing your question."
    
    return {
        "messages": [AIMessage(content=user_message)],
        "error": None,  # Clear error state
        "error_node": None,
        "retry_count": 2  # Reset retry count for next operation
    }
