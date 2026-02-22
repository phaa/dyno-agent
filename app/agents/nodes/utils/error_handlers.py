"""Error handling utilities for nodes."""

import logging
from agents.state import GraphState
from langchain_core.messages import AIMessage
from agents.nodes.config import INITIAL_SUMMARY

logger = logging.getLogger(__name__)


def get_reset_error_state() -> dict:
    """
    Returns a dictionary with cleared error fields and reset retry count.
    
    Used for successful node executions to clear error state.
    
    Returns:
        dict: Keys to unpack in node return statements:
            - retry_count: Reset to ERROR_RETRY_COUNT
            - error: Set to None
            - error_node: Set to None
    """
    from agents.config import DEFAULT_ERROR_RETRY_COUNT
    return {
        "retry_count": DEFAULT_ERROR_RETRY_COUNT,
        "error": None,
        "error_node": None,
    }


def get_decrement_retry_count(state: GraphState, error_msg: str, error_node: str) -> dict:
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
    retry_count = state.get("retry_count")
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