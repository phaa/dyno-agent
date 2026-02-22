import logging
from typing import Literal
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from services.exceptions import FatalException, RetryableException
from agents.state import GraphState
from agents.tools import TOOLS
from .utils import get_reset_error_state, get_decrement_retry_count, set_fatal_error

logger = logging.getLogger(__name__)

base_tool_node = ToolNode(TOOLS)

async def tool_node(state: GraphState) -> Command[Literal["llm", "tools", "error_llm"]]:
    """
    Tool node with intelligent retry mechanism and error classification.
    
    Error Classification Strategy:
    - RetryableException: Network timeouts, temporary service unavailability, rate limits
    - FatalException: Authentication failures, validation errors, malformed requests
    - Unknown Exceptions: Treated as retryable with caution
    
    Routing Logic:
    - Success: Returns to 'llm' for next reasoning step
    - Retryable error with attempts left: Loops back to 'tools' for retry
    - Retries exhausted: Routes to 'error_llm' for graceful error handling
    
    Args:
        state: Current graph state with retry information
        
    Returns:
        Command: State update with next node routing
    """
    try:
        result = await base_tool_node.ainvoke(state.get("messages", []))
        return Command(
            update={
                "messages": result,
                **get_reset_error_state(),
            },
            goto="llm"
        )
        
    except RetryableException as e:
        # Retryable error: Decrement retry count and preserve error info
        logger.warning(f"Retryable error in tools: {str(e)}")
        error_update = get_decrement_retry_count(state, f"Retryable error in tools: {str(e)}", "tools")
        retry_count = error_update.get("retry_count", 0)
        
        next_node = "tools" if retry_count > 0 else "error_llm"
        return Command(update=error_update, goto=next_node)
        
    except FatalException as e:
        # Fatal error: Immediate failure without retry
        logger.error(f"Fatal error in tools: {str(e)}")
        error_update = set_fatal_error(f"Fatal error in tools: {str(e)}", "tools")
        return Command(update=error_update, goto="error_llm")
        
    except Exception as e:
        # Unknown error: Treat as retryable but log for investigation
        logger.error(f"Unknown error in tools (treating as retryable): {str(e)}", exc_info=True)
        error_update = get_decrement_retry_count(state, f"Unexpected error in tools: {str(e)}", "tools")
        retry_count = error_update.get("retry_count", 0)
        
        next_node = "tools" if retry_count > 0 else "error_llm"
        return Command(update=error_update, goto=next_node)
    