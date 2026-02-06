"""Error handling utilities for nodes."""

import logging
from agents.state import GraphState
from langchain_core.messages import AIMessage
from agents.nodes.config import INITIAL_SUMMARY

logger = logging.getLogger(__name__)


def reset_error_state() -> dict:
    """
    Returns a dictionary with cleared error fields and reset retry count.
    
    Used for successful node executions to clear error state.
    
    Returns:
        dict: Keys to unpack in node return statements:
            - retry_count: Reset to ERROR_RETRY_COUNT
            - error: Set to None
            - error_node: Set to None
    """
    from agents.config import ERROR_RETRY_COUNT
    return {
        "retry_count": ERROR_RETRY_COUNT,
        "error": None,
        "error_node": None,
    }


def decrement_retry_count(state: GraphState, error_msg: str, error_node: str) -> dict:
    """
    Returns a dictionary with decremented retry count and error information.
    
    Used for retryable error scenarios to preserve error state for retry logic.
    
    Args:
        state: Current GraphState
        error_msg: The error message to store
        error_node: The node where the error occurred
    
    Returns:
        dict: Keys to unpack in node return statements:
            - retry_count: Decremented by 1 (minimum 0)
            - error: The error message
            - error_node: The node name where error occurred
    """
    retry_count = state.get("retry_count", 0)
    return {
        "retry_count": max(0, retry_count - 1),
        "error": error_msg,
        "error_node": error_node,
    }


def set_fatal_error(error_msg: str, error_node: str) -> dict:
    """
    Returns a dictionary for fatal errors that should not be retried.
    
    Used for non-retryable errors to immediately trigger error handler.
    
    Args:
        error_msg: The error message to store
        error_node: The node where the error occurred
    
    Returns:
        dict: Keys to unpack in node return statements:
            - retry_count: Set to 0 (no retries)
            - error: The error message
            - error_node: The node name where error occurred
    """
    return {
        "retry_count": 0,
        "error": error_msg,
        "error_node": error_node,
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
            "retry_attempts_made": 2 - state.get("retry_count")
        }
    )
    
    message = f"Encountered an issue processing the request at the {error_node} stage."
    
    return {
        "messages": [AIMessage(content=message)],
        "error": None,  # Clear error state
        "error_node": None,
        "retry_count": 2  # Reset retry count for next operation
    }


def cleanup_node(state: GraphState) -> GraphState:
    """Clean up temporary fields from state to prevent leakage.
    
    Persists:
    - conversation_id, user_name (identity)
    - summary (persistent memory)
    
    Does NOT clear messages (persistent conversation history)

    Clears non-reducer ephemeral fields:
    - user_input
    - retry_count, error, error_node
    - schema
    
    Checkpointer will only save identity and summary to DB.
    """
    """ logger.info("Cleaning up state before ending graph.")
    
    return {
        # Identity (required for thread reference)
        "conversation_id": state.get("conversation_id"),
        "user_name": state.get("user_name"),
        # Persistent (saved to checkpointer)
        "summary": state.get("summary", INITIAL_SUMMARY),
        # Note: messages field is NOT cleared (persistent history)
        # Ephemeral
        "user_input": None,
        "retry_count": 2,
        "error": None,
        "error_node": None,
        "schema": None
    }   """ 
    return {}
