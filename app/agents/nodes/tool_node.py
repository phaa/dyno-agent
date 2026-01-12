import logging
from langgraph.prebuilt import ToolNode

from agents.exceptions import FatalException, RetryableException
from ..state import GraphState
from ..tools import TOOLS

logger = logging.getLogger(__name__)

base_tool_node = ToolNode(TOOLS)

async def tool_node(state: GraphState) -> GraphState:
    """
    Tool node with intelligent retry mechanism and error classification.
    
    Error Classification Strategy:
    - RetryableException: Network timeouts, temporary service unavailability, rate limits
    - FatalException: Authentication failures, validation errors, malformed requests
    - Unknown Exceptions: Treated as retryable with caution
    
    Retry Logic:
    - Decrements retry_count on retryable errors
    - Preserves error context for debugging and user feedback
    - Resets error state on successful execution
    - Routes to graceful error handler when retries exhausted
    
    Args:
        state: Current graph state with retry information
        
    Returns:
        GraphState: Updated state with results or error information
    """
    try:
        # Execute tools using base ToolNode
        result = await base_tool_node.ainvoke(state)
        
        # Success: Clear any previous error state
        return {
            **result,
            "error": None,
            "error_node": None,
            "retry_count": 2  # Reset retry count for next operation
        }
        
    except RetryableException as e:
        # Retryable error: Decrement retry count and preserve error info
        logger.warning(f"Retryable error in tools: {str(e)}")
        return {
            "retry_count": max(0, state.get("retry_count", 2) - 1),
            "error": str(e),
            "error_node": "tools"
        }
        
    except FatalException as e:
        # Fatal error: Immediate failure without retry
        logger.error(f"Fatal error in tools: {str(e)}")
        return {
            "retry_count": 0,  # Force immediate error handling
            "error": str(e),
            "error_node": "tools"
        }
        
    except Exception as e:
        # Unknown error: Treat as retryable but log for investigation
        logger.error(f"Unknown error in tools (treating as retryable): {str(e)}", exc_info=True)
        return {
            "retry_count": max(0, state.get("retry_count", 2) - 1),
            "error": f"Unexpected error: {str(e)}",
            "error_node": "tools"
        }
    