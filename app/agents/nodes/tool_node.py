import logging
from langgraph.prebuilt import ToolNode
from services.exceptions import FatalException, RetryableException
# from services.exceptions import InvalidQueryError # uncomment for error simulation
from agents.state import GraphState
from agents.tools import TOOLS
from .utils import reset_error_state, decrement_retry_count, set_fatal_error

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
    - If coming form LLM detect remaining tool calls
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
        # ToolNode expects 'messages' field
        #tool_input = {"messages": state.get("messages", [])}
        result = await base_tool_node.ainvoke(state.get("messages", []))
        
        # raise InvalidQueryError("Erro ao acessar o banco de dados de veiculos") # uncomment for error simulation
        
        # When successful, clear any previous error state
        return {
            "messages": result,
            **reset_error_state(),
        }
        
    except RetryableException as e:
        # Retryable error: Decrement retry count and preserve error info
        logger.warning(f"Retryable error in tools: {str(e)}")
        return {
            **decrement_retry_count(state, f"Retryable error in tools: {str(e)}", "tools")
        }
        
    except FatalException as e:
        # Fatal error: Immediate failure without retry
        logger.error(f"Fatal error in tools: {str(e)}")
        return {
            **set_fatal_error(f"Fatal error in tools: {str(e)}", "tools")
        }
        
    except Exception as e:
        # Unknown error: Treat as retryable but log for investigation
        logger.error(f"Unknown error in tools (treating as retryable): {str(e)}", exc_info=True)
        return {
            **decrement_retry_count(state, f"Unexpected error in tools: {str(e)}", "tools")
        }
    